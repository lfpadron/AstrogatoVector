"""Resolve raw form inputs into final safe candidate input."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from schemas.models import CandidateInput, JobInput, LinkReadResult, LinkReadSummary
from services.candidate_input_service import CandidatePreparationResult
from services.link_reader import fetch_url_content, normalize_web_text
from utils.constants import LINK_PREVIEW_CHARS
from utils.validators import JobFormInput, ValidationMessage

ProfileSource = Literal["text", "url", "generated"]
JobSource = Literal["text", "url"]
FetchLink = Callable[[str], LinkReadResult]
StatusCallback = Callable[[str], None]

TEXT_PROFILE_PRIORITY_MESSAGE = (
    "Se utilizará el texto pegado como fuente principal. El enlace no fue necesario para continuar."
)
TEXT_JOB_PRIORITY_MESSAGE = (
    "Se utilizará la descripción pegada como fuente principal. El enlace no fue necesario para continuar."
)
LINK_FAILURE_TITLE = "No fue posible leer el enlace"


@dataclass(frozen=True)
class ResolvedLinkedinInput:
    """Resolved optional LinkedIn profile state."""

    text: str | None
    source: ProfileSource
    url: str | None = None
    summary: LinkReadSummary | None = None
    preview: str | None = None
    recovered_text: str | None = None
    messages: list[ValidationMessage] = field(default_factory=list)
    link_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.link_error is None


@dataclass(frozen=True)
class ResolvedJobInputs:
    """Resolved target job state."""

    jobs: list[JobInput] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)
    previews: dict[str, str] = field(default_factory=dict)
    recovered_texts: dict[str, str] = field(default_factory=dict)
    messages: list[ValidationMessage] = field(default_factory=list)
    link_error: str | None = None
    failed_link_index: int | None = None

    @property
    def is_valid(self) -> bool:
        return self.link_error is None


@dataclass(frozen=True)
class InputResolutionResult:
    """Final resolution result ready for Streamlit session storage."""

    candidate_input: CandidateInput | None = None
    messages: list[ValidationMessage] = field(default_factory=list)
    linkedin_diagnostic: dict | None = None
    job_diagnostics: list[dict] = field(default_factory=list)
    link_previews: dict[str, str] = field(default_factory=dict)
    recovered_link_texts: dict[str, str] = field(default_factory=dict)
    link_error: str | None = None
    failed_link_index: int | None = None
    link_reading_completed: bool = False

    @property
    def is_valid(self) -> bool:
        return self.candidate_input is not None and self.link_error is None


def resolve_linkedin_input(
    linkedin_text: str,
    linkedin_url: str,
    *,
    fetcher: FetchLink = fetch_url_content,
) -> ResolvedLinkedinInput:
    """Resolve the optional LinkedIn profile with pasted text priority."""
    normalized_text = normalize_web_text(linkedin_text)
    normalized_url = linkedin_url.strip() or None
    messages: list[ValidationMessage] = []

    if normalized_text:
        if normalized_url:
            messages.append(ValidationMessage("info", "linkedin", TEXT_PROFILE_PRIORITY_MESSAGE))
        return ResolvedLinkedinInput(
            text=normalized_text,
            source="text",
            url=normalized_url,
            preview=normalized_text[:LINK_PREVIEW_CHARS],
            messages=messages,
        )

    if not normalized_url:
        return ResolvedLinkedinInput(text=None, source="generated")

    result = fetcher(normalized_url)
    summary = result.to_summary()
    if not result.success:
        message = result.errors[0] if result.errors else LINK_FAILURE_TITLE
        return ResolvedLinkedinInput(
            text=None,
            source="url",
            url=normalized_url,
            summary=summary,
            preview=_preview(result.normalized_text),
            recovered_text=result.normalized_text or None,
            messages=_link_failure_messages("linkedin_url", "perfil de LinkedIn", normalized_url, message),
            link_error=f"Perfil de LinkedIn: {message}",
        )

    return ResolvedLinkedinInput(
        text=result.normalized_text,
        source="url",
        url=normalized_url,
        summary=summary,
        preview=_preview(result.normalized_text),
        recovered_text=result.normalized_text,
    )


def resolve_job_inputs(
    jobs: Sequence[JobFormInput],
    *,
    fetcher: FetchLink = fetch_url_content,
) -> ResolvedJobInputs:
    """Resolve target jobs in order and stop at the first mandatory link failure."""
    resolved_jobs: list[JobInput] = []
    diagnostics: list[dict] = []
    previews: dict[str, str] = {}
    recovered_texts: dict[str, str] = {}
    messages: list[ValidationMessage] = []

    for job in jobs:
        normalized_description = normalize_web_text(job.description)
        normalized_url = job.url.strip() or None
        company = job.company.strip() or None

        if normalized_description:
            if normalized_url:
                messages.append(ValidationMessage("info", f"job_{job.index}", TEXT_JOB_PRIORITY_MESSAGE))
            resolved_jobs.append(
                JobInput(
                    index=job.index,
                    title=job.title,
                    company=company,
                    description=normalized_description,
                    url=normalized_url,
                    source="text",
                    link_summary=None,
                )
            )
            diagnostics.append(
                {
                    "index": job.index,
                    "title": job.title.strip(),
                    "source": "text",
                    "url": normalized_url,
                    "message": "Se utilizó la descripción pegada.",
                    "link_summary": None,
                }
            )
            continue

        if not normalized_url:
            return ResolvedJobInputs(
                jobs=resolved_jobs,
                diagnostics=diagnostics,
                previews=previews,
                recovered_texts=recovered_texts,
                messages=messages
                + [
                    ValidationMessage(
                        "error",
                        f"job_{job.index}",
                        f"La Vacante {job.index} necesita una descripción o un enlace.",
                    )
                ],
                link_error=f"Vacante {job.index}: falta descripción o enlace.",
                failed_link_index=job.index,
            )

        result = fetcher(normalized_url)
        summary = result.to_summary()
        diagnostics.append(
            {
                "index": job.index,
                "title": job.title.strip(),
                "source": "url",
                "url": normalized_url,
                "message": "Lectura de enlace completada." if result.success else "No fue posible leer el enlace.",
                "link_summary": summary.model_dump(),
            }
        )
        if result.normalized_text:
            key = _job_preview_key(job.index)
            previews[key] = _preview(result.normalized_text)
            recovered_texts[key] = result.normalized_text

        if not result.success:
            message = result.errors[0] if result.errors else LINK_FAILURE_TITLE
            return ResolvedJobInputs(
                jobs=resolved_jobs,
                diagnostics=diagnostics,
                previews=previews,
                recovered_texts=recovered_texts,
                messages=messages
                + _link_failure_messages(
                    f"job_{job.index}_url",
                    f"Vacante {job.index}",
                    normalized_url,
                    message,
                ),
                link_error=f"Vacante {job.index}: {message}",
                failed_link_index=job.index,
            )

        resolved_jobs.append(
            JobInput(
                index=job.index,
                title=job.title,
                company=company,
                description=result.normalized_text,
                url=normalized_url,
                source="url",
                link_summary=summary,
            )
        )

    return ResolvedJobInputs(
        jobs=resolved_jobs,
        diagnostics=diagnostics,
        previews=previews,
        recovered_texts=recovered_texts,
        messages=messages,
    )


def resolve_all_inputs(
    prepared_cv: CandidatePreparationResult,
    *,
    linkedin_text: str,
    linkedin_url: str,
    jobs: Sequence[JobFormInput],
    output_language: str,
    fetcher: FetchLink = fetch_url_content,
    status_callback: StatusCallback | None = None,
) -> InputResolutionResult:
    """Resolve all non-CV inputs and build the final CandidateInput."""
    if not prepared_cv.is_valid or not prepared_cv.cv_text or not prepared_cv.cv_source or not prepared_cv.cv_summary:
        return InputResolutionResult(
            messages=prepared_cv.messages,
            link_error="No fue posible preparar el CV.",
        )

    messages: list[ValidationMessage] = []

    if not linkedin_text.strip() and linkedin_url.strip() and status_callback:
        status_callback("Leyendo perfil de LinkedIn...")
    profile = resolve_linkedin_input(linkedin_text, linkedin_url, fetcher=fetcher)
    messages.extend(profile.messages)

    profile_diagnostic = _profile_diagnostic(profile)
    link_previews: dict[str, str] = {}
    recovered_texts: dict[str, str] = {}
    if profile.preview:
        link_previews["linkedin"] = profile.preview
    if profile.recovered_text:
        recovered_texts["linkedin"] = profile.recovered_text

    if not profile.is_valid:
        return InputResolutionResult(
            messages=messages,
            linkedin_diagnostic=profile_diagnostic,
            link_previews=link_previews,
            recovered_link_texts=recovered_texts,
            link_error=profile.link_error,
            link_reading_completed=False,
        )

    job_messages: list[ValidationMessage] = []
    resolved_jobs: list[JobInput] = []
    job_diagnostics: list[dict] = []
    job_previews: dict[str, str] = {}
    job_recovered_texts: dict[str, str] = {}

    for job in jobs:
        if not job.description.strip() and job.url.strip() and status_callback:
            status_callback(f"Leyendo Vacante {job.index}...")

        partial = resolve_job_inputs([job], fetcher=fetcher)
        job_messages.extend(partial.messages)
        resolved_jobs.extend(partial.jobs)
        job_diagnostics.extend(partial.diagnostics)
        job_previews.update(partial.previews)
        job_recovered_texts.update(partial.recovered_texts)

        if not partial.is_valid:
            messages.extend(job_messages)
            return InputResolutionResult(
                messages=messages,
                linkedin_diagnostic=profile_diagnostic,
                job_diagnostics=job_diagnostics,
                link_previews={**link_previews, **job_previews},
                recovered_link_texts={**recovered_texts, **job_recovered_texts},
                link_error=partial.link_error,
                failed_link_index=partial.failed_link_index,
                link_reading_completed=False,
            )

    messages.extend(job_messages)
    candidate_input = CandidateInput(
        cv_text=prepared_cv.cv_text,
        cv_source=prepared_cv.cv_source,
        cv_filename=prepared_cv.cv_filename,
        cv_file_size=prepared_cv.cv_file_size,
        cv_parse_summary=prepared_cv.cv_summary,
        linkedin_text=profile.text,
        linkedin_source=profile.source,
        linkedin_url=profile.url,
        linkedin_link_summary=profile.summary,
        output_language=output_language,
        jobs=resolved_jobs,
    )

    return InputResolutionResult(
        candidate_input=candidate_input,
        messages=messages,
        linkedin_diagnostic=profile_diagnostic,
        job_diagnostics=job_diagnostics,
        link_previews={**link_previews, **job_previews},
        recovered_link_texts={**recovered_texts, **job_recovered_texts},
        link_reading_completed=True,
    )


def _profile_diagnostic(profile: ResolvedLinkedinInput) -> dict:
    return {
        "source": profile.source,
        "url": profile.url,
        "message": _profile_message(profile),
        "link_summary": profile.summary.model_dump() if profile.summary else None,
    }


def _profile_message(profile: ResolvedLinkedinInput) -> str:
    if profile.link_error:
        return "No fue posible leer el enlace."
    if profile.source == "text":
        return "Se utilizó el texto pegado."
    if profile.source == "url":
        return "Perfil de LinkedIn recuperado."
    return "Se generará desde cero en un incremento posterior."


def _link_failure_messages(field: str, label: str, url: str, detail: str) -> list[ValidationMessage]:
    return [
        ValidationMessage("error", field, LINK_FAILURE_TITLE),
        ValidationMessage("error", field, f"El sistema no pudo recuperar contenido suficiente de:\n{url}"),
        ValidationMessage("error", field, f"{label}: {detail}"),
        ValidationMessage(
            "error",
            field,
            "Esto puede ocurrir porque la página requiere iniciar sesión, restringe el acceso automatizado, "
            "depende de JavaScript, fue eliminada o no permite consultar su contenido directamente.",
        ),
        ValidationMessage(
            "error",
            field,
            "Para continuar:\n"
            "1. Abre el enlace en tu navegador.\n"
            "2. Copia el contenido completo.\n"
            "3. Pégalo en el campo de texto correspondiente.\n"
            "4. Presiona nuevamente Procesar.",
        ),
        ValidationMessage(
            "error",
            field,
            "No se realizó el análisis ni se generaron resultados con información incompleta.",
        ),
    ]


def _preview(text: str) -> str | None:
    normalized = normalize_web_text(text)
    return normalized[:LINK_PREVIEW_CHARS] if normalized else None


def _job_preview_key(index: int) -> str:
    return f"job_{index}"
