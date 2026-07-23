"""Run candidate extraction with fictitious data and safe console output."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.enums import ContentSource, OutputLanguage  # noqa: E402
from schemas.input_models import CandidateInput, DocumentParseSummary, JobInput  # noqa: E402
from services.candidate_extraction_service import CandidateExtractionService  # noqa: E402
from services.openai_config import OpenAIConfigurationError  # noqa: E402
from services.openai_service import create_openai_service  # noqa: E402

FICTITIOUS_CV = """María Ejemplo

Project Manager con experiencia en implementación de sistemas empresariales.

Empresa Demostración
Senior Project Manager
2018-2025

Responsable de coordinar proyectos de transformación digital, gestionar riesgos y colaborar con equipos de tecnología y negocio.

Lideró la implementación de una nueva plataforma interna entregada dentro del calendario aprobado.

Educación:
Maestría en Administración de Tecnologías.

Idiomas:
Español nativo.
Inglés intermedio.
"""

FICTITIOUS_JOB = (
    "Vacante ficticia usada solo para cumplir el contrato de entrada. No debe enviarse a la extracción "
    "del candidato ni atribuir requisitos al perfil profesional."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a safe fictitious candidate extraction test.")
    parser.add_argument("--show-profile", action="store_true", help="Print the parsed profile JSON.")
    args = parser.parse_args()

    try:
        service = CandidateExtractionService(create_openai_service())
    except OpenAIConfigurationError:
        print("Candidate extraction: configuration incomplete")
        return 0

    result = service.extract_candidate_profile(_candidate_input())
    if result.success:
        print("Candidate extraction: OK")
        print(f"Model: {result.model_used or 'unknown'}")
        print(f"Evidence audit passed: {'yes' if result.evidence_audit_passed else 'no'}")
        print(f"Latency: {result.latency_ms if result.latency_ms is not None else 'unknown'} ms")
        print(f"Tokens: {result.total_tokens if result.total_tokens is not None else 'unknown'}")
        if args.show_profile and result.profile is not None:
            print(result.profile.model_dump_json(indent=2))
        return 0

    print("Candidate extraction: FAILED")
    print(f"Model: {result.model_used or 'unknown'}")
    print(f"Category: {result.error_category or 'unknown'}")
    print(f"Retryable: {'yes' if result.retryable else 'no'}")
    print(result.user_message or "No fue posible extraer el perfil profesional.")
    return 1


def _candidate_input() -> CandidateInput:
    return CandidateInput(
        cv_text=FICTITIOUS_CV,
        cv_source=ContentSource.TEXT,
        cv_parse_summary=DocumentParseSummary(
            source=ContentSource.TEXT,
            character_count=len(FICTITIOUS_CV),
            word_count=len(FICTITIOUS_CV.split()),
        ),
        linkedin_text=None,
        linkedin_source=ContentSource.GENERATED,
        output_language=OutputLanguage.ES,
        jobs=[
            JobInput(index=1, title="Project Manager", description=FICTITIOUS_JOB, source=ContentSource.TEXT),
            JobInput(index=2, title="Program Manager", description=FICTITIOUS_JOB, source=ContentSource.TEXT),
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
