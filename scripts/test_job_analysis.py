"""Run target job analysis with fictitious job postings and safe output."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.enums import ContentSource, OutputLanguage  # noqa: E402
from schemas.input_models import JobInput  # noqa: E402
from services.job_analysis_service import JobAnalysisService  # noqa: E402
from services.openai_config import OpenAIConfigurationError  # noqa: E402
from services.openai_service import create_openai_service  # noqa: E402


def main() -> int:
    """Run a safe fictitious target jobs analysis."""
    try:
        service = JobAnalysisService(create_openai_service())
    except OpenAIConfigurationError:
        print("Job analysis: configuration incomplete")
        return 0

    result = service.analyze_jobs(_jobs(), OutputLanguage.ES)
    if result.success and result.market_analysis is not None:
        print("Job analysis: OK")
        print(f"Model: {result.model_used or 'unknown'}")
        print(f"Jobs analyzed: {len(result.market_analysis.job_analyses)}")
        print(f"Audit passed: {'yes' if result.audit_passed else 'no'}")
        print(f"Latency: {result.latency_ms if result.latency_ms is not None else 'unknown'} ms")
        print(f"Tokens: {result.total_tokens if result.total_tokens is not None else 'unknown'}")
        top_keywords = result.market_analysis.keywords[:5]
        if top_keywords:
            print("Top keywords:")
            for keyword in top_keywords:
                print(f"- {keyword.keyword}: {keyword.frequency}")
        return 0

    print("Job analysis: FAILED")
    print(f"Model: {result.model_used or 'unknown'}")
    print(f"Category: {result.error_category or 'unknown'}")
    print(f"Retryable: {'yes' if result.retryable else 'no'}")
    print(result.user_message or "No fue posible analizar las vacantes objetivo.")
    return 1


def _jobs() -> list[JobInput]:
    return [
        JobInput(
            index=1,
            title="Senior Project Manager",
            company="Empresa Ficticia Uno",
            description=(
                "Senior Project Manager responsable de liderar proyectos de transformación digital, gestionar "
                "riesgos, presupuesto, stakeholders y equipos multidisciplinarios. Se requiere experiencia con "
                "metodologías Agile y comunicación ejecutiva. Inglés avanzado deseable."
            ),
            source=ContentSource.TEXT,
        ),
        JobInput(
            index=2,
            title="IT Program Manager",
            company="Empresa Ficticia Dos",
            description=(
                "IT Program Manager encargado de coordinar programas tecnológicos, gobernanza, seguimiento "
                "financiero, gestión de proveedores y reportes ejecutivos. Requiere experiencia en Agile, "
                "gestión de riesgos y liderazgo de equipos."
            ),
            source=ContentSource.TEXT,
        ),
        JobInput(
            index=3,
            title="Technology Project Lead",
            company="Empresa Ficticia Tres",
            description=(
                "Technology Project Lead para implementación de plataformas empresariales, coordinación entre "
                "negocio y tecnología, planificación, dependencias y calidad. Experiencia con Jira y metodologías "
                "ágiles es indispensable."
            ),
            source=ContentSource.TEXT,
        ),
    ]


if __name__ == "__main__":
    raise SystemExit(main())
