"""Pure validation helpers for Astrogato Vector form inputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Sequence
from urllib.parse import urlparse, urlunparse

from utils.constants import (
    MAX_CV_FILE_SIZE_MB,
    MAX_JOB_POSTINGS,
    MIN_JOB_DESCRIPTION_CHARS,
    MIN_JOB_POSTINGS,
    OUTPUT_LANGUAGES,
    UPLOAD_TYPES,
)

MessageLevel = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class ValidationMessage:
    """One validation message to present to the user."""

    level: MessageLevel
    field: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    """Structured result for one or more validation checks."""

    is_valid: bool
    messages: list[ValidationMessage] = field(default_factory=list)


@dataclass(frozen=True)
class JobFormInput:
    """Raw job input captured from the Streamlit form."""

    index: int
    title: str = ""
    company: str = ""
    description: str = ""
    url: str = ""


def is_valid_http_url(value: str) -> bool:
    """Return whether the value is a basic HTTP or HTTPS URL."""
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_url(value: str) -> str:
    """Normalize a URL enough to detect obvious duplicates."""
    parsed = urlparse(value.strip())
    path = parsed.path.rstrip("/")
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            parsed.query,
            "",
        )
    )


def is_probable_linkedin_url(value: str) -> bool:
    """Return whether the URL appears to belong to LinkedIn."""
    if not is_valid_http_url(value):
        return False

    domain = urlparse(value.strip()).netloc.lower()
    return domain == "linkedin.com" or domain.endswith(".linkedin.com")


def validate_cv_input(
    cv_text: str,
    file_name: str | None = None,
    file_size: int | None = None,
) -> ValidationResult:
    """Validate CV text and uploaded file metadata."""
    messages: list[ValidationMessage] = []
    has_text = bool(cv_text.strip())
    has_file = bool(file_name)

    if not has_text and not has_file:
        messages.append(
            ValidationMessage(
                "error",
                "cv",
                "Agrega tu CV pegando el texto o cargando un archivo DOCX o PDF.",
            )
        )

    if has_file:
        _validate_file_metadata(file_name or "", file_size, messages)

    if has_text and has_file:
        messages.append(
            ValidationMessage(
                "info",
                "cv",
                "Se utilizará el texto pegado como fuente principal. El archivo permanecerá disponible como referencia.",
            )
        )

    return _build_result(messages)


def validate_linkedin_input(linkedin_text: str, linkedin_url: str) -> ValidationResult:
    """Validate optional LinkedIn profile text and URL."""
    messages: list[ValidationMessage] = []
    has_text = bool(linkedin_text.strip())
    has_url = bool(linkedin_url.strip())

    if not has_text and not has_url:
        messages.append(
            ValidationMessage(
                "info",
                "linkedin",
                "No proporcionaste un perfil actual. Se generará una propuesta desde cero en un incremento posterior.",
            )
        )
        return _build_result(messages)

    if has_url:
        if not is_valid_http_url(linkedin_url):
            messages.append(
                ValidationMessage(
                    "error",
                    "linkedin_url",
                    "El enlace del perfil no tiene un formato válido. Revisa que comience con http:// o https://.",
                )
            )
        elif not is_probable_linkedin_url(linkedin_url):
            messages.append(
                ValidationMessage(
                    "warning",
                    "linkedin_url",
                    "El enlace no parece corresponder a LinkedIn. Revisa que sea el perfil correcto.",
                )
            )

    if has_text and has_url:
        messages.append(
            ValidationMessage(
                "info",
                "linkedin",
                "Se utilizará el texto pegado como fuente principal. El enlace no fue necesario para continuar.",
            )
        )

    return _build_result(messages)


def validate_job_input(job: JobFormInput) -> ValidationResult:
    """Validate one target job posting."""
    messages: list[ValidationMessage] = []
    title = job.title.strip()
    description = job.description.strip()
    url = job.url.strip()
    has_description = bool(description)
    has_url = bool(url)
    has_valid_url = is_valid_http_url(url) if has_url else False

    if not title:
        messages.append(
            ValidationMessage(
                "error",
                f"job_{job.index}_title",
                f"Indica el nombre o título de la Vacante {job.index}.",
            )
        )

    if not has_description and not has_url:
        messages.append(
            ValidationMessage(
                "error",
                f"job_{job.index}",
                f"La Vacante {job.index} necesita una descripción o un enlace.",
            )
        )

    if has_url:
        if not has_valid_url:
            messages.append(
                ValidationMessage(
                    "error",
                    f"job_{job.index}_url",
                    f"El enlace de la Vacante {job.index} no tiene un formato válido. Debe comenzar con http:// o https://.",
                )
            )
        elif not is_probable_linkedin_url(url):
            messages.append(
                ValidationMessage(
                    "warning",
                    f"job_{job.index}_url",
                    f"El enlace de la Vacante {job.index} no parece corresponder a LinkedIn. Se conservará, pero conviene verificarlo.",
                )
            )

    if has_description and len(description) < MIN_JOB_DESCRIPTION_CHARS:
        if has_valid_url:
            messages.append(
                ValidationMessage(
                    "warning",
                    f"job_{job.index}_description",
                    f"La descripción de la Vacante {job.index} es demasiado breve. Pega al menos los primeros párrafos relevantes o utiliza el enlace.",
                )
            )
        else:
            messages.append(
                ValidationMessage(
                    "error",
                    f"job_{job.index}_description",
                    f"La descripción de la Vacante {job.index} es demasiado breve. Pega al menos los primeros párrafos relevantes o utiliza el enlace.",
                )
            )

    if has_description and has_url:
        messages.append(
            ValidationMessage(
                "info",
                f"job_{job.index}",
                "Se utilizará la descripción pegada como fuente principal. El enlace no fue necesario para continuar.",
            )
        )

    return _build_result(messages)


def find_duplicate_jobs(jobs: Sequence[JobFormInput]) -> list[ValidationMessage]:
    """Find obvious duplicate job postings without blocking processing."""
    messages: list[ValidationMessage] = []
    seen_urls: dict[str, int] = {}
    seen_title_company: dict[tuple[str, str], int] = {}
    reported_pairs: set[tuple[int, int]] = set()

    for job in jobs:
        if job.url.strip() and is_valid_http_url(job.url):
            normalized = normalize_url(job.url)
            if normalized in seen_urls:
                _add_duplicate_warning(seen_urls[normalized], job.index, messages, reported_pairs)
            else:
                seen_urls[normalized] = job.index

        normalized_title = _normalize_text(job.title)
        normalized_company = _normalize_text(job.company)
        title_company_key = (normalized_title, normalized_company)
        if normalized_title:
            if title_company_key in seen_title_company:
                _add_duplicate_warning(
                    seen_title_company[title_company_key],
                    job.index,
                    messages,
                    reported_pairs,
                )
            else:
                seen_title_company[title_company_key] = job.index

    return messages


def validate_complete_form(
    consent_accepted: bool,
    cv_text: str,
    cv_file_name: str | None,
    cv_file_size: int | None,
    linkedin_text: str,
    linkedin_url: str,
    jobs: Sequence[JobFormInput],
    output_language: str,
) -> ValidationResult:
    """Validate the complete form without mutating Streamlit state."""
    messages: list[ValidationMessage] = []

    if not consent_accepted:
        messages.append(
            ValidationMessage(
                "error",
                "consent",
                "Debes leer y aceptar el aviso antes de procesar la información.",
            )
        )

    if output_language not in OUTPUT_LANGUAGES:
        messages.append(
            ValidationMessage(
                "error",
                "output_language",
                "Selecciona un idioma de salida válido.",
            )
        )

    if len(jobs) < MIN_JOB_POSTINGS:
        messages.append(
            ValidationMessage(
                "error",
                "jobs",
                f"Debes incluir al menos {MIN_JOB_POSTINGS} vacantes objetivo.",
            )
        )
    elif len(jobs) > MAX_JOB_POSTINGS:
        messages.append(
            ValidationMessage(
                "error",
                "jobs",
                f"No puedes incluir más de {MAX_JOB_POSTINGS} vacantes objetivo.",
            )
        )

    messages.extend(validate_cv_input(cv_text, cv_file_name, cv_file_size).messages)
    messages.extend(validate_linkedin_input(linkedin_text, linkedin_url).messages)

    for job in jobs:
        messages.extend(validate_job_input(job).messages)

    messages.extend(find_duplicate_jobs(jobs))
    return _build_result(messages)


def _validate_file_metadata(
    file_name: str,
    file_size: int | None,
    messages: list[ValidationMessage],
) -> None:
    if not file_name.strip():
        messages.append(
            ValidationMessage(
                "error",
                "cv_file",
                "El archivo del CV no tiene un nombre válido.",
            )
        )
        return

    if "." not in file_name:
        messages.append(
            ValidationMessage(
                "error",
                "cv_file",
                "El archivo del CV debe tener extensión DOCX o PDF.",
            )
        )
    else:
        extension = file_name.rsplit(".", 1)[-1].lower()
        if extension not in UPLOAD_TYPES:
            messages.append(
                ValidationMessage(
                    "error",
                    "cv_file",
                    "El archivo del CV debe tener extensión DOCX o PDF.",
                )
            )

    if file_size is not None:
        if file_size <= 0:
            messages.append(
                ValidationMessage(
                    "error",
                    "cv_file",
                    "El archivo del CV está vacío. Carga un archivo válido o pega el contenido como texto.",
                )
            )
        elif file_size > MAX_CV_FILE_SIZE_MB * 1024 * 1024:
            messages.append(
                ValidationMessage(
                    "error",
                    "cv_file",
                    f"El archivo supera el límite de {MAX_CV_FILE_SIZE_MB} MB. Reduce su tamaño o pega el contenido como texto.",
                )
            )


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _add_duplicate_warning(
    first_index: int,
    second_index: int,
    messages: list[ValidationMessage],
    reported_pairs: set[tuple[int, int]],
) -> None:
    pair = tuple(sorted((first_index, second_index)))
    if pair in reported_pairs:
        return

    reported_pairs.add(pair)
    messages.append(
        ValidationMessage(
            "warning",
            "jobs",
            f"Las Vacantes {pair[0]} y {pair[1]} parecen duplicadas. Revisa si deseas conservar ambas.",
        )
    )


def _build_result(messages: list[ValidationMessage]) -> ValidationResult:
    return ValidationResult(
        is_valid=not any(message.level == "error" for message in messages),
        messages=messages,
    )
