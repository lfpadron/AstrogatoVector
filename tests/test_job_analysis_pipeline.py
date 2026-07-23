from __future__ import annotations

from pydantic import SecretStr

from schemas.enums import ContentSource, OutputLanguage, PriorityLevel, SeniorityLevel, SkillCategory
from schemas.input_models import JobInput
from schemas.job_analysis_models import JobAnalysisResult
from schemas.market_models import JobAnalysis, JobRequirement, MarketKeyword, TargetMarketAnalysis
from services.job_analysis_pipeline import run_job_analysis_pipeline
from services.job_analysis_service import build_jobs_analysis_fingerprint
from services.openai_config import OpenAIConfigurationError, OpenAISettings
from services.openai_service import OpenAIService


class FakeSDKResponse:
    def __init__(self, output_parsed=None, model: str = "quality-model") -> None:
        self.output_parsed = output_parsed
        self._request_id = "req_pipeline"
        self.model = model
        self.usage = None


class FakeResponses:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeClient:
    def __init__(self, result) -> None:
        self.responses = FakeResponses(result)


def test_pipeline_reuses_successful_result_for_same_fingerprint():
    jobs = _jobs()
    previous = JobAnalysisResult(
        success=True,
        market_analysis=_market_analysis(),
        model_used="quality-model",
        audit_passed=True,
    )
    fingerprint = build_jobs_analysis_fingerprint(jobs, OutputLanguage.ES, model_name="quality-model")
    calls = {"count": 0}

    def factory():
        calls["count"] += 1
        return OpenAIService(_settings(), client=FakeClient(FakeSDKResponse(_market_analysis())))

    run = run_job_analysis_pipeline(
        jobs,
        OutputLanguage.ES,
        existing_result=previous,
        existing_fingerprint=fingerprint,
        openai_service_factory=factory,
    )

    assert run.reused
    assert run.result.reused_from_session
    assert calls["count"] == 1


def test_pipeline_force_reprocess_calls_model_again():
    jobs = _jobs()
    previous = JobAnalysisResult(
        success=True,
        market_analysis=_market_analysis(),
        model_used="quality-model",
        audit_passed=True,
    )
    fingerprint = build_jobs_analysis_fingerprint(jobs, OutputLanguage.ES, model_name="quality-model")
    client = FakeClient(FakeSDKResponse(_market_analysis()))

    run = run_job_analysis_pipeline(
        jobs,
        OutputLanguage.ES,
        existing_result=previous,
        existing_fingerprint=fingerprint,
        force=True,
        openai_service_factory=lambda: OpenAIService(_settings(), client=client),
    )

    assert not run.reused
    assert len(client.responses.calls) == 1
    assert run.fingerprint == fingerprint


def test_pipeline_configuration_error_is_safe():
    def factory():
        raise OpenAIConfigurationError(errors=["OPENAI_API_KEY no está definida."])

    run = run_job_analysis_pipeline(_jobs(), OutputLanguage.ES, openai_service_factory=factory)

    assert not run.result.success
    assert run.result.error_category == "configuration_error"
    assert run.result.market_analysis is None


def test_fingerprint_changes_with_job_content_language_model_or_prompt_version():
    jobs = _jobs()
    base = build_jobs_analysis_fingerprint(jobs, OutputLanguage.ES, model_name="quality-model")
    changed_jobs = [jobs[0].model_copy(update={"description": jobs[0].description + " Jira"}), jobs[1]]

    assert base != build_jobs_analysis_fingerprint(jobs, OutputLanguage.EN, model_name="quality-model")
    assert base != build_jobs_analysis_fingerprint(jobs, OutputLanguage.ES, model_name="other-model")
    assert base != build_jobs_analysis_fingerprint(
        jobs,
        OutputLanguage.ES,
        model_name="quality-model",
        prompt_version="2.0",
    )
    assert base != build_jobs_analysis_fingerprint(changed_jobs, OutputLanguage.ES, model_name="quality-model")


def _settings() -> OpenAISettings:
    return OpenAISettings(
        api_key=SecretStr("unit-test-secret"),
        model_fast="fast-model",
        model_quality="quality-model",
        timeout_seconds=30,
        max_retries=1,
        diagnostic_enabled=True,
    )


def _jobs() -> list[JobInput]:
    return [
        JobInput(
            index=1,
            title="Senior Project Manager",
            company="Empresa Uno",
            description=(
                "Senior Project Manager se requiere Agile y gestión de riesgos. Liderar proyectos, "
                "coordinar equipos multidisciplinarios y reportar avances ejecutivos."
            ),
            source=ContentSource.TEXT,
        ),
        JobInput(
            index=2,
            title="IT Program Manager",
            company="Empresa Dos",
            description=(
                "IT Program Manager requiere Agile y gestión de riesgos. Coordinar programas, proveedores, "
                "presupuestos y seguimiento ejecutivo de iniciativas tecnologicas."
            ),
            source=ContentSource.TEXT,
        ),
    ]


def _market_analysis() -> TargetMarketAnalysis:
    agile = JobRequirement(
        name="Agile",
        normalized_name="agile",
        category=SkillCategory.BUSINESS,
        description="Experiencia con Agile.",
        required=True,
        importance=PriorityLevel.HIGH,
        exact_keywords=["Agile"],
    )
    return TargetMarketAnalysis(
        target_role_family="Gestión de proyectos",
        suggested_target_titles=["Project Manager", "Program Manager"],
        dominant_seniority=SeniorityLevel.MANAGER,
        market_summary="Mercado ficticio de gestión de proyectos y programas con Agile.",
        common_responsibilities=["gestión de riesgos"],
        common_requirements=[agile],
        keywords=[
            MarketKeyword(
                keyword="Agile",
                normalized_keyword="agile",
                frequency=2,
                job_indices=[1, 2],
                category=SkillCategory.BUSINESS,
                priority=PriorityLevel.HIGH,
            )
        ],
        business_skills=["gestión de riesgos"],
        job_analyses=[
            JobAnalysis(
                job_index=1,
                title="Senior Project Manager",
                company="Empresa Uno",
                inferred_seniority=SeniorityLevel.MANAGER,
                role_summary="Rol para liderar proyectos con Agile y gestión de riesgos.",
                responsibilities=["gestión de riesgos"],
                requirements=[agile],
                exact_keywords=["Agile"],
            ),
            JobAnalysis(
                job_index=2,
                title="IT Program Manager",
                company="Empresa Dos",
                inferred_seniority=SeniorityLevel.MANAGER,
                role_summary="Rol para coordinar programas con Agile y gestión de riesgos.",
                responsibilities=["gestión de riesgos"],
                requirements=[agile],
                exact_keywords=["Agile"],
            ),
        ],
    )
