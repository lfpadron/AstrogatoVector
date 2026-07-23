"""Local DOCX and PDF text extraction utilities."""

from __future__ import annotations

from io import BytesIO
import re
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from schemas.models import DocumentParseResult
from utils.constants import (
    MIN_EXTRACTED_CV_CHARS,
    MIN_PDF_TEXT_CHARS,
    SCANNED_PDF_AVG_CHARS_PER_PAGE,
    SCANNED_PDF_EMPTY_PAGE_RATIO,
)

LOW_TEXT_WARNING = (
    "El archivo contiene muy poco texto para realizar un análisis confiable. "
    "Revisa el documento o pega el contenido manualmente."
)
DOCX_ERROR = (
    "No fue posible extraer texto del archivo DOCX. Verifica que no esté dañado "
    "o pega el contenido manualmente."
)
PDF_OPEN_ERROR = "No fue posible abrir el PDF. Verifica que el archivo no esté dañado."
PDF_PASSWORD_ERROR = "El PDF está protegido con contraseña y no puede procesarse."
PDF_SCANNED_ERROR = (
    "El PDF parece estar compuesto principalmente por imágenes. Esta versión todavía "
    "no incorpora OCR. Pega el contenido del CV como texto para continuar."
)
PDF_TEXT_ERROR = (
    "No fue posible extraer texto suficiente del PDF. Utiliza un PDF con texto "
    "seleccionable o pega el contenido manualmente."
)
UNSUPPORTED_FILE_ERROR = "El archivo debe tener extensión DOCX o PDF."


def extract_docx_text(file_bytes: bytes, filename: str = "documento.docx") -> DocumentParseResult:
    """Extract paragraphs and tables from a DOCX file in memory."""
    if not file_bytes:
        return _result(filename, "docx", errors=[DOCX_ERROR])

    try:
        document = Document(BytesIO(file_bytes))
    except (BadZipFile, PackageNotFoundError, ValueError, OSError):
        return _result(filename, "docx", errors=[DOCX_ERROR])

    blocks: list[str] = []
    paragraph_count = 0

    for block in _iter_docx_blocks(document):
        if isinstance(block, Paragraph):
            text = _clean_docx_text(block.text)
            if text:
                blocks.append(text)
                paragraph_count += 1
        elif isinstance(block, Table):
            rows = _extract_table_rows(block)
            blocks.extend(rows)

    extracted_text = "\n\n".join(blocks)
    normalized_text = normalize_extracted_text(extracted_text)
    warnings: list[str] = []
    errors: list[str] = []

    if not normalized_text:
        errors.append(DOCX_ERROR)
    elif len(normalized_text) < MIN_EXTRACTED_CV_CHARS:
        warnings.append(LOW_TEXT_WARNING)

    return _result(
        filename,
        "docx",
        extracted_text=extracted_text,
        normalized_text=normalized_text,
        paragraph_count=paragraph_count,
        warnings=warnings,
        errors=errors,
    )


def extract_pdf_text(file_bytes: bytes, filename: str = "documento.pdf") -> DocumentParseResult:
    """Extract selectable text from a digital PDF in memory."""
    if not file_bytes:
        return _result(filename, "pdf", errors=[PDF_OPEN_ERROR])

    try:
        reader = PdfReader(BytesIO(file_bytes))
    except (PdfReadError, ValueError, OSError, TypeError):
        return _result(filename, "pdf", errors=[PDF_OPEN_ERROR])

    if reader.is_encrypted:
        try:
            decrypt_result = reader.decrypt("")
        except Exception:
            return _result(filename, "pdf", errors=[PDF_PASSWORD_ERROR])

        if not decrypt_result:
            return _result(filename, "pdf", errors=[PDF_PASSWORD_ERROR])

    try:
        page_count = len(reader.pages)
    except (PdfReadError, ValueError, TypeError):
        return _result(filename, "pdf", errors=[PDF_OPEN_ERROR])

    page_texts: list[str] = []
    empty_pages = 0
    extraction_errors = 0

    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
            extraction_errors += 1

        if not page_text.strip():
            empty_pages += 1
        page_texts.append(page_text)

    extracted_text = "\n\n".join(page_texts)
    normalized_text = normalize_extracted_text(extracted_text)
    character_count = len(normalized_text)
    likely_scanned = _is_likely_scanned_pdf(character_count, page_count, empty_pages)
    warnings: list[str] = []
    errors: list[str] = []

    if extraction_errors:
        warnings.append(
            f"{extraction_errors} página(s) no pudieron leerse completamente."
        )

    if empty_pages and not likely_scanned:
        warnings.append(
            f"{empty_pages} página(s) no devolvieron texto seleccionable."
        )

    if page_count == 0:
        errors.append(PDF_OPEN_ERROR)
    elif likely_scanned:
        errors.append(PDF_SCANNED_ERROR)
    elif character_count < MIN_PDF_TEXT_CHARS:
        errors.append(PDF_TEXT_ERROR)

    return _result(
        filename,
        "pdf",
        extracted_text=extracted_text,
        normalized_text=normalized_text,
        page_count=page_count,
        warnings=warnings,
        errors=errors,
        likely_scanned=likely_scanned,
    )


def parse_uploaded_document(
    filename: str,
    file_bytes: bytes,
    mime_type: str | None = None,
) -> DocumentParseResult:
    """Route an uploaded document to the correct local parser."""
    file_type = _detect_file_type(filename, mime_type)
    if file_type == "docx":
        return extract_docx_text(file_bytes, filename)
    if file_type == "pdf":
        return extract_pdf_text(file_bytes, filename)

    return _result(filename, "unknown", errors=[UNSUPPORTED_FILE_ERROR])


def normalize_extracted_text(text: str) -> str:
    """Normalize extracted document text without aggressive rewriting."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = []
    for line in normalized.split("\n"):
        compact_line = re.sub(r"[ \t\f\v]+", " ", line).strip()
        lines.append(compact_line)

    normalized = "\n".join(lines).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def count_words(text: str) -> int:
    """Return an approximate word count for normalized text."""
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def _iter_docx_blocks(document: Document):
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _extract_table_rows(table: Table) -> list[str]:
    rows = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            cell_text = normalize_extracted_text(
                " ".join(_clean_docx_text(paragraph.text) for paragraph in cell.paragraphs)
            )
            cells.append(cell_text)

        row_text = " | ".join(cell for cell in cells if cell)
        if row_text:
            rows.append(row_text)
    return rows


def _clean_docx_text(text: str) -> str:
    return re.sub(r"[ \t\f\v]+", " ", text.replace("\x00", "")).strip()


def _detect_file_type(filename: str, mime_type: str | None = None) -> str:
    lower_name = filename.strip().lower()
    if lower_name.endswith(".docx"):
        return "docx"
    if lower_name.endswith(".pdf"):
        return "pdf"

    if mime_type:
        lower_mime = mime_type.lower()
        if lower_mime == "application/pdf":
            return "pdf"
        if "wordprocessingml.document" in lower_mime:
            return "docx"

    return "unknown"


def _is_likely_scanned_pdf(character_count: int, page_count: int, empty_pages: int) -> bool:
    if page_count <= 0:
        return False

    empty_page_ratio = empty_pages / page_count
    average_chars_per_page = character_count / page_count
    return (
        character_count < MIN_PDF_TEXT_CHARS
        and (
            empty_page_ratio >= SCANNED_PDF_EMPTY_PAGE_RATIO
            or average_chars_per_page < SCANNED_PDF_AVG_CHARS_PER_PAGE
        )
    )


def _result(
    filename: str,
    file_type: str,
    extracted_text: str = "",
    normalized_text: str = "",
    page_count: int | None = None,
    paragraph_count: int | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    likely_scanned: bool = False,
) -> DocumentParseResult:
    warnings = warnings or []
    errors = errors or []
    return DocumentParseResult(
        success=not errors,
        filename=filename,
        file_type=file_type,
        extracted_text=extracted_text,
        normalized_text=normalized_text,
        character_count=len(normalized_text),
        word_count=count_words(normalized_text),
        page_count=page_count,
        paragraph_count=paragraph_count,
        warnings=warnings,
        errors=errors,
        likely_scanned=likely_scanned,
    )
