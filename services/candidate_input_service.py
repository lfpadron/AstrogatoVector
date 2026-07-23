"""Prepare validated candidate input without calling external services."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from schemas.models import DocumentParseResult, DocumentParseSummary
from services.document_parser import (
    LOW_TEXT_WARNING,
    normalize_extracted_text,
    parse_uploaded_document,
    count_words,
)
from utils.constants import MIN_EXTRACTED_CV_CHARS
from utils.validators import ValidationMessage


@dataclass(frozen=True)
class CandidatePreparationResult:
    """Result of preparing the CV portion before link resolution."""

    cv_text: str | None = None
    cv_source: Literal["text", "docx", "pdf"] | None = None
    cv_filename: str | None = None
    cv_file_size: int | None = None
    cv_preview: str | None = None
    cv_parse_result: DocumentParseResult | None = None
    cv_summary: DocumentParseSummary | None = None
    messages: list[ValidationMessage] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(message.level == "error" for message in self.messages)


def prepare_candidate_input(
    cv_text: str,
    cv_file_name: str | None,
    cv_file_size: int | None,
    cv_file_bytes: bytes | None,
    linkedin_text: str,
    linkedin_url: str,
    jobs: object,
    output_language: str,
) -> CandidatePreparationResult:
    """Prepare normalized CV input after form validation succeeds."""
    messages: list[ValidationMessage] = []
    cv_text = cv_text.strip()

    if cv_text:
        normalized_cv_text = normalize_extracted_text(cv_text)
        if len(normalized_cv_text) < MIN_EXTRACTED_CV_CHARS:
            messages.append(
                ValidationMessage(
                    "error",
                    "cv",
                    LOW_TEXT_WARNING,
                )
            )
            return CandidatePreparationResult(messages=messages)

        if cv_file_name:
            messages.append(
                ValidationMessage(
                    "info",
                    "cv",
                    "Se utilizará el texto pegado como fuente principal. El archivo no fue necesario para continuar.",
                )
            )

        cv_summary = DocumentParseSummary(
            source="text",
            character_count=len(normalized_cv_text),
            word_count=count_words(normalized_cv_text),
            warnings=[],
        )
        return _build_preparation_result(
            normalized_cv_text,
            "text",
            cv_file_name,
            cv_file_size,
            cv_summary,
            None,
            messages,
        )

    if not cv_file_name or cv_file_bytes is None:
        messages.append(
            ValidationMessage(
                "error",
                "cv",
                "Agrega tu CV pegando el texto o cargando un archivo DOCX o PDF.",
            )
        )
        return CandidatePreparationResult(messages=messages)

    parse_result = parse_uploaded_document(cv_file_name, cv_file_bytes)
    messages.extend(
        ValidationMessage("warning", "cv_file", warning)
        for warning in parse_result.warnings
    )
    messages.extend(
        ValidationMessage("error", "cv_file", error)
        for error in parse_result.errors
    )

    if not parse_result.success:
        return CandidatePreparationResult(
            cv_parse_result=parse_result,
            messages=messages,
        )

    cv_source = parse_result.file_type
    if cv_source not in {"docx", "pdf"}:
        messages.append(
            ValidationMessage(
                "error",
                "cv_file",
                "El archivo debe tener extensión DOCX o PDF.",
            )
        )
        return CandidatePreparationResult(
            cv_parse_result=parse_result,
            messages=messages,
        )

    cv_summary = DocumentParseSummary(
        source=cv_source,
        filename=parse_result.filename,
        file_type=cv_source,
        character_count=parse_result.character_count,
        word_count=parse_result.word_count,
        page_count=parse_result.page_count,
        paragraph_count=parse_result.paragraph_count,
        warnings=parse_result.warnings,
        likely_scanned=parse_result.likely_scanned,
    )
    return _build_preparation_result(
        parse_result.normalized_text,
        cv_source,
        cv_file_name,
        cv_file_size,
        cv_summary,
        parse_result,
        messages,
    )


def _build_preparation_result(
    normalized_cv_text: str,
    cv_source: Literal["text", "docx", "pdf"],
    cv_file_name: str | None,
    cv_file_size: int | None,
    cv_summary: DocumentParseSummary,
    parse_result: DocumentParseResult | None,
    messages: list[ValidationMessage],
) -> CandidatePreparationResult:
    return CandidatePreparationResult(
        cv_text=normalized_cv_text,
        cv_source=cv_source,
        cv_filename=cv_file_name,
        cv_file_size=cv_file_size,
        cv_preview=normalized_cv_text,
        cv_parse_result=parse_result,
        cv_summary=cv_summary,
        messages=messages,
    )
