from __future__ import annotations

import pytest

from schemas.enums import ContentSource, PriorityLevel, SeniorityLevel, SkillCategory
from schemas.input_models import JobInput
from schemas.market_models import JobAnalysis, JobRequirement, MarketKeyword, TargetMarketAnalysis
from services.job_analysis_audit_service import audit_target_market_analysis


def test_valid_market_analysis_passes():
    result = audit_target_market_analysis(_market_analysis(), _jobs())

    assert result.passed


def test_missing_extra_and_duplicate_indices_are_detected():
    jobs = _jobs()
    missing = _market_analysis(job_analyses=_market_analysis().job_analyses[:2])
    missing_result = audit_target_market_analysis(missing, jobs)
    assert not missing_result.passed
    assert any("Falta el análisis" in finding.message for finding in missing_result.findings)

    extra = _market_analysis(
        job_analyses=[
            *_market_analysis().job_analyses,
            _market_analysis().job_analyses[0].model_copy(update={"job_index": 4}),
        ]
    )
    extra_result = audit_target_market_analysis(extra, jobs)
    assert not extra_result.passed
    assert any("vacante no recibida" in finding.message for finding in extra_result.findings)

    duplicate = _market_analysis()
    duplicate = duplicate.model_copy(update={"job_analyses": [*duplicate.job_analyses[:2], duplicate.job_analyses[1]]})
    duplicate_result = audit_target_market_analysis(duplicate, jobs)
    assert not duplicate_result.passed
    assert any("únicos" in finding.message for finding in duplicate_result.findings)


def test_title_and_company_mismatch_block_result():
    analysis = _market_analysis()
    analysis.job_analyses[0].title = "Chief Financial Officer"
    analysis.job_analyses[1].company = "Otra Empresa"

    result = audit_target_market_analysis(analysis, _jobs())

    assert not result.passed
    assert any("título" in finding.message for finding in result.findings)
    assert any("empresa" in finding.message for finding in result.findings)


def test_keyword_frequency_indices_and_evidence_are_audited():
    analysis = _market_analysis()
    analysis.keywords[0] = analysis.keywords[0].model_copy(update={"frequency": 2})
    frequency_result = audit_target_market_analysis(analysis, _jobs())
    assert not frequency_result.passed
    assert any("frequency" in finding.message for finding in frequency_result.findings)

    analysis = _market_analysis()
    analysis.keywords[0] = analysis.keywords[0].model_construct(
        keyword="Agile",
        normalized_keyword="agile",
        frequency=3,
        job_indices=[1, 1, 2],
        category=SkillCategory.BUSINESS,
        priority=PriorityLevel.HIGH,
    )
    duplicate_result = audit_target_market_analysis(analysis, _jobs())
    assert not duplicate_result.passed
    assert any("frequency" in finding.message for finding in duplicate_result.findings)

    analysis = _market_analysis()
    analysis.keywords[0] = analysis.keywords[0].model_copy(update={"job_indices": [1, 2, 6], "frequency": 3})
    missing_index_result = audit_target_market_analysis(analysis, _jobs())
    assert not missing_index_result.passed
    assert any("índice inexistente" in finding.message for finding in missing_index_result.findings)

    analysis = _market_analysis()
    analysis.keywords.append(
        MarketKeyword(
            keyword="OpenAI",
            normalized_keyword="openai",
            frequency=1,
            job_indices=[1],
            category=SkillCategory.TOOL,
            priority=PriorityLevel.HIGH,
        )
    )
    invented_result = audit_target_market_analysis(analysis, _jobs())
    assert invented_result.passed
    assert any("keyword no aparece" in finding.message for finding in invented_result.findings)
    assert all(finding.severity == "warning" for finding in invented_result.findings)


def test_duplicate_normalized_keyword_blocks_result():
    analysis = _market_analysis()
    analysis.keywords.append(
        MarketKeyword(
            keyword="agile",
            normalized_keyword="agile",
            frequency=3,
            job_indices=[1, 2, 3],
            category=SkillCategory.BUSINESS,
            priority=PriorityLevel.HIGH,
        )
    )

    result = audit_target_market_analysis(analysis, _jobs())

    assert not result.passed
    assert any("duplicada" in finding.message for finding in result.findings)


def test_tool_valid_and_invented_tool_blocks_result():
    valid = audit_target_market_analysis(_market_analysis(), _jobs())
    assert valid.passed

    analysis = _market_analysis()
    analysis.tools_and_technologies.append("Azure")

    result = audit_target_market_analysis(analysis, _jobs())

    assert not result.passed
    assert any("herramienta" in finding.message for finding in result.findings)


def test_required_requirement_without_required_signal_warns_without_blocking_result():
    jobs = _jobs()
    jobs[0] = jobs[0].model_copy(update={"description": "Senior Project Manager con Agile deseable y comunicación."})

    result = audit_target_market_analysis(_market_analysis(), jobs)

    assert result.passed
    assert any("required=true" in finding.message for finding in result.findings)
    assert all(finding.severity == "warning" for finding in result.findings)


def test_common_responsibility_or_requirement_from_one_job_warns_without_blocking_result():
    analysis = _market_analysis()
    analysis.common_responsibilities = ["Jira"]
    result = audit_target_market_analysis(analysis, _jobs())
    assert result.passed
    assert any("responsabilidad común" in finding.message for finding in result.findings)
    assert all(finding.severity == "warning" for finding in result.findings)

    analysis = _market_analysis()
    analysis.common_requirements = [
        JobRequirement(
            name="Jira",
            normalized_name="jira",
            category=SkillCategory.TOOL,
            description="Experiencia con Jira.",
            required=True,
            importance=PriorityLevel.MEDIUM,
            exact_keywords=["Jira"],
        )
    ]
    req_result = audit_target_market_analysis(analysis, _jobs())
    assert req_result.passed
    assert any("requisito común" in finding.message for finding in req_result.findings)
    assert all(finding.severity == "warning" for finding in req_result.findings)


def test_requirement_supported_by_exact_keyword_does_not_warn_as_unsupported():
    analysis = _market_analysis()
    analysis.job_analyses[0].requirements = [
        JobRequirement(
            name="Marcos ágiles empresariales",
            normalized_name="marcos agiles empresariales",
            category=SkillCategory.BUSINESS,
            description="Experiencia con Agile.",
            required=True,
            importance=PriorityLevel.HIGH,
            exact_keywords=["Agile"],
        )
    ]

    result = audit_target_market_analysis(analysis, _jobs())

    assert result.passed
    assert not any("no está respaldado" in finding.message for finding in result.findings)


def test_seniority_absurdity_blocks_result():
    jobs = [
        JobInput(
            index=1,
            title="Intern Project Assistant",
            description=(
                "Intern Project Assistant se requiere apoyo a proyectos Agile, seguimiento de actividades, "
                "documentacion de avances y coordinacion operativa del equipo."
            ),
            source=ContentSource.TEXT,
        ),
        JobInput(
            index=2,
            title="Director of Programs",
            description=(
                "Director of Programs requiere liderazgo de programas Agile, gestion ejecutiva de portafolios, "
                "gobernanza, comunicacion con stakeholders y toma de decisiones."
            ),
            source=ContentSource.TEXT,
        ),
    ]
    analysis = _market_analysis(job_analyses=[
        _market_analysis().job_analyses[0].model_copy(
            update={"job_index": 1, "title": "Intern Project Assistant", "company": None, "inferred_seniority": SeniorityLevel.EXECUTIVE}
        ),
        _market_analysis().job_analyses[1].model_copy(
            update={"job_index": 2, "title": "Director of Programs", "company": None, "inferred_seniority": SeniorityLevel.ENTRY}
        ),
    ])
    analysis.keywords[0] = analysis.keywords[0].model_copy(update={"frequency": 2, "job_indices": [1, 2]})
    analysis.common_requirements = [
        JobRequirement(
            name="Agile",
            normalized_name="agile",
            category=SkillCategory.BUSINESS,
            description="Experiencia con Agile.",
            required=True,
            importance=PriorityLevel.HIGH,
            exact_keywords=["Agile"],
        )
    ]

    result = audit_target_market_analysis(analysis, jobs)

    assert not result.passed
    assert any("absurdo" in finding.message for finding in result.findings)


def test_duplicate_job_indices_blocked_by_pydantic():
    with pytest.raises(ValueError):
        TargetMarketAnalysis(
            **{
                **_market_analysis().model_dump(),
                "job_analyses": [_market_analysis().job_analyses[0], _market_analysis().job_analyses[0]],
            }
        )


def _jobs() -> list[JobInput]:
    return [
        JobInput(
            index=1,
            title="Senior Project Manager",
            company="Empresa Uno",
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
            company="Empresa Dos",
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
            company="Empresa Tres",
            description=(
                "Technology Project Lead para implementación de plataformas empresariales, coordinación entre "
                "negocio y tecnología, planificación, dependencias y calidad. Experiencia con Jira y metodologías "
                "ágiles es indispensable."
            ),
            source=ContentSource.TEXT,
        ),
    ]


def _market_analysis(job_analyses: list[JobAnalysis] | None = None) -> TargetMarketAnalysis:
    agile = JobRequirement(
        name="Agile",
        normalized_name="agile",
        category=SkillCategory.BUSINESS,
        description="Experiencia con metodologías Agile.",
        required=True,
        importance=PriorityLevel.HIGH,
        exact_keywords=["Agile"],
    )
    risk = JobRequirement(
        name="gestión de riesgos",
        normalized_name="gestion de riesgos",
        category=SkillCategory.BUSINESS,
        description="Gestión de riesgos en proyectos o programas.",
        required=True,
        importance=PriorityLevel.HIGH,
        exact_keywords=["gestión de riesgos"],
    )
    analyses = job_analyses or [
        JobAnalysis(
            job_index=1,
            title="Senior Project Manager",
            company="Empresa Uno",
            inferred_seniority=SeniorityLevel.MANAGER,
            role_summary="Rol para liderar proyectos de transformación digital con riesgos y stakeholders.",
            responsibilities=["gestionar riesgos"],
            requirements=[agile],
            leadership_skills=["liderar equipos multidisciplinarios"],
            exact_keywords=["Agile"],
        ),
        JobAnalysis(
            job_index=2,
            title="IT Program Manager",
            company="Empresa Dos",
            inferred_seniority=SeniorityLevel.MANAGER,
            role_summary="Rol para coordinar programas tecnológicos, proveedores, riesgos y reportes ejecutivos.",
            responsibilities=["gestión de riesgos"],
            requirements=[risk],
            leadership_skills=["liderazgo de equipos"],
            exact_keywords=["Agile", "gestión de riesgos"],
        ),
        JobAnalysis(
            job_index=3,
            title="Technology Project Lead",
            company="Empresa Tres",
            inferred_seniority=SeniorityLevel.LEAD,
            role_summary="Rol para implementar plataformas empresariales y coordinar negocio y tecnología.",
            responsibilities=["implementación de plataformas empresariales"],
            requirements=[agile],
            tools_and_technologies=["Jira"],
            exact_keywords=["Jira", "metodologías ágiles"],
        ),
    ]
    return TargetMarketAnalysis(
        target_role_family="Gestión de proyectos tecnológicos",
        suggested_target_titles=["Project Manager", "Program Manager", "Project Lead"],
        dominant_seniority=SeniorityLevel.MANAGER,
        market_summary="Mercado ficticio orientado a gestión de proyectos tecnológicos.",
        common_responsibilities=["gestión de riesgos"],
        common_requirements=[agile],
        keywords=[
            MarketKeyword(
                keyword="Agile",
                normalized_keyword="agile",
                frequency=3,
                job_indices=[1, 2, 3],
                category=SkillCategory.BUSINESS,
                priority=PriorityLevel.HIGH,
            )
        ],
        business_skills=["gestión de riesgos"],
        tools_and_technologies=["Jira"],
        industries=["Tecnología"],
        differentiators=["seguimiento financiero", "Jira"],
        job_analyses=analyses,
    )
