from __future__ import annotations

from datetime import datetime

from schemas.editorial_plan_models import (
    EditorialCalendar,
    EditorialCalendarWeek,
    EditorialDay,
    EditorialObjective,
    LinkedInPostFormat,
    LinkedInPostPlan,
    LinkedInPostType,
    ProfessionalBrandPlan,
)
from schemas.enums import OutputLanguage
from schemas.examples import build_example_audit_report
from tests.targeted_cv_helpers import build_targeted_cv_inputs


def build_editorial_plan_inputs():
    profile, market, compatibility = build_targeted_cv_inputs()
    audit_report = build_example_audit_report()
    return profile, market, compatibility, audit_report


def build_editorial_plan() -> ProfessionalBrandPlan:
    themes = [
        "Gestión Agile con acuerdos visibles",
        "Comunicación con stakeholders",
        "Seguimiento operativo en Jira",
        "Priorización en proyectos digitales",
        "Liderazgo práctico sin exagerar",
        "Aprendizaje desde brechas técnicas",
        "Método para convertir ambigüedad en próximos pasos",
        "Innovación aplicada a la coordinación",
        "Reflexión sobre evidencia profesional",
        "Networking con criterio",
        "Tutorial breve de visibilidad operativa",
        "Opinión profesional sobre colaboración tecnológica",
    ]
    objectives = [
        EditorialObjective.AUTHORITY,
        EditorialObjective.EXPERIENCE,
        EditorialObjective.METHODOLOGY,
        EditorialObjective.LEADERSHIP,
        EditorialObjective.LEARNING,
        EditorialObjective.REFLECTION,
        EditorialObjective.METHODOLOGY,
        EditorialObjective.INNOVATION,
        EditorialObjective.EXPERIENCE,
        EditorialObjective.NETWORKING,
        EditorialObjective.METHODOLOGY,
        EditorialObjective.AUTHORITY,
    ]
    post_types = [
        LinkedInPostType.PROFESSIONAL_STORY,
        LinkedInPostType.LESSON_LEARNED,
        LinkedInPostType.TECHNICAL_EXPLANATION,
        LinkedInPostType.METHODOLOGY,
        LinkedInPostType.REFLECTION,
        LinkedInPostType.ERROR_TO_LEARNING,
        LinkedInPostType.MINI_TUTORIAL,
        LinkedInPostType.MARKET_TREND,
        LinkedInPostType.SUCCESS_CASE,
        LinkedInPostType.PROFESSIONAL_OPINION,
        LinkedInPostType.MINI_TUTORIAL,
        LinkedInPostType.PROFESSIONAL_OPINION,
    ]
    formats = [
        LinkedInPostFormat.SHORT,
        LinkedInPostFormat.MEDIUM,
        LinkedInPostFormat.LONG,
        LinkedInPostFormat.SHORT,
        LinkedInPostFormat.MEDIUM,
        LinkedInPostFormat.LONG,
        LinkedInPostFormat.SHORT,
        LinkedInPostFormat.MEDIUM,
        LinkedInPostFormat.LONG,
        LinkedInPostFormat.SHORT,
        LinkedInPostFormat.MEDIUM,
        LinkedInPostFormat.LONG,
    ]
    hooks = [
        "Un proyecto Agile mejora cuando los acuerdos se vuelven visibles.",
        "La comunicación con stakeholders no empieza en la reunión de seguimiento.",
        "Jira funciona mejor cuando refleja decisiones, no sólo tareas.",
        "Priorizar también significa explicar por qué algo espera.",
        "Liderar proyectos no requiere prometer certeza absoluta.",
        "Una brecha técnica bien nombrada también puede mostrar madurez.",
        "Este método me ayuda a convertir ambigüedad en próximos pasos.",
        "Innovar en coordinación puede empezar con una conversación mejor diseñada.",
        "La evidencia profesional evita que el perfil prometa de más.",
        "El networking profesional mejora cuando hay criterio y contexto.",
        "Un tablero útil cuenta una historia operativa simple.",
        "La colaboración tecnológica necesita ritmo, lenguaje común y trazabilidad.",
    ]
    ctas = [
        "¿Qué práctica te ayuda a volver visibles los acuerdos?",
        "¿Cuál ha sido tu experiencia alineando stakeholders?",
        "¿Cómo haces que una herramienta refleje decisiones reales?",
        "¿Qué señal usas para decidir qué debe esperar?",
        "¿Qué opinas sobre liderar con claridad sin exagerar certezas?",
        "¿Cómo hablas de una brecha sin convertirla en experiencia inventada?",
        "¿Qué paso agregaría tu equipo a este método?",
        "¿Dónde has visto innovación práctica en la coordinación diaria?",
        "¿Qué evidencia revisas antes de publicar un logro profesional?",
        "¿Cómo decides cuándo una conversación de networking aporta valor?",
        "¿Qué elemento no puede faltar en un tablero operativo?",
        "¿Qué opinas sobre el rol de la trazabilidad en equipos de tecnología?",
    ]
    hashtags = [
        ["#Agile", "#ProjectManagement", "#Liderazgo"],
        ["#Stakeholders", "#Comunicacion", "#Liderazgo"],
        ["#Jira", "#Agile", "#Tecnologia"],
        ["#ProjectManagement", "#Metodologia", "#Tecnologia"],
        ["#Liderazgo", "#Aprendizaje", "#ProjectManagement"],
        ["#Aprendizaje", "#Tecnologia", "#Metodologia"],
        ["#Metodologia", "#Agile", "#Stakeholders"],
        ["#Innovacion", "#Tecnologia", "#Comunicacion"],
        ["#ProjectManagement", "#Aprendizaje", "#Comunicacion"],
        ["#Networking", "#Comunicacion", "#Liderazgo"],
        ["#Jira", "#ProjectManagement", "#Metodologia"],
        ["#Tecnologia", "#Stakeholders", "#Agile"],
    ]
    posts = []
    for index in range(12):
        week = index // 3 + 1
        day = (EditorialDay.MONDAY, EditorialDay.WEDNESDAY, EditorialDay.FRIDAY)[index % 3]
        body = _body_for(formats[index], themes[index], index)
        posts.append(
            LinkedInPostPlan(
                week=week,
                day=day,
                title=f"{themes[index]}",
                objective=objectives[index],
                theme=themes[index],
                audience="Recruiters, líderes de tecnología y profesionales de gestión de proyectos",
                format=formats[index],
                post_type=post_types[index],
                hook=hooks[index],
                body=body,
                cta=ctas[index],
                hashtags=hashtags[index],
                keywords_used=["Agile", "Stakeholder management", "Jira", "Project Manager"],
                evidence_used=[
                    "Gestiono proyectos Agile con stakeholders y seguimiento en Jira.",
                    "Redujo tiempos de seguimiento 15% en proyectos internos.",
                ],
                claims_requiring_review=["Revisar que el 15% se use sólo cuando sea pertinente."],
                notes=["Borrador ficticio para pruebas automatizadas."],
                character_count=len(body.strip()),
            )
        )
    weeks = [
        EditorialCalendarWeek(week=week, posts=[post for post in posts if post.week == week])
        for week in range(1, 5)
    ]
    return ProfessionalBrandPlan(
        output_language=OutputLanguage.ES,
        generated_at=datetime(2026, 1, 1),
        summary=(
            "Plan editorial ficticio para posicionar un perfil de Project Manager con evidencia en Agile, "
            "Jira, stakeholder management, comunicación operativa y liderazgo práctico."
        ),
        objectives=[
            EditorialObjective.AUTHORITY,
            EditorialObjective.EXPERIENCE,
            EditorialObjective.LEADERSHIP,
            EditorialObjective.LEARNING,
            EditorialObjective.METHODOLOGY,
            EditorialObjective.INNOVATION,
            EditorialObjective.REFLECTION,
            EditorialObjective.NETWORKING,
        ],
        calendar=EditorialCalendar(weeks=weeks),
        strengths_exploited=["Gestión de proyectos Agile", "Stakeholder management", "Seguimiento con Jira"],
        themes=themes,
        risks=["No presentar brechas técnicas como experiencia respaldada."],
        recommendations=["Revisar cada texto antes de publicarlo manualmente."],
    )


def replace_editorial_post(plan: ProfessionalBrandPlan, post_index: int, **updates) -> ProfessionalBrandPlan:
    posts = list(plan.calendar.posts)
    posts[post_index] = posts[post_index].model_copy(update=updates)
    weeks = [
        EditorialCalendarWeek(week=week, posts=[post for post in posts if post.week == week])
        for week in range(1, 5)
    ]
    return plan.model_copy(update={"calendar": EditorialCalendar(weeks=weeks)})


def _body_for(format_value: LinkedInPostFormat, theme: str, index: int) -> str:
    ranges = {
        LinkedInPostFormat.SHORT: 360,
        LinkedInPostFormat.MEDIUM: 760,
        LinkedInPostFormat.LONG: 1320,
    }
    target = ranges[format_value]
    text = (
        f"{theme}: en gestión de proyectos Agile he aprendido que el avance depende de acuerdos claros, "
        "stakeholders informados y seguimiento visible en Jira. La evidencia del perfil muestra coordinación "
        "operativa, trabajo con equipos de tecnología y una mejora de 15% en tiempos de seguimiento. "
    )
    additions = [
        "Cuando una prioridad cambia, el valor está en explicar el contexto y dejar trazabilidad para que el equipo actúe con menos fricción. ",
        "También ayuda separar lo demostrado de lo que todavía debe fortalecerse; esa honestidad evita convertir una expectativa del mercado en una promesa personal. ",
        "Un buen mensaje profesional no necesita exagerar: puede enseñar una práctica, mostrar criterio y abrir conversación desde experiencia verificable. ",
        "La comunicación con stakeholders gana fuerza cuando resume decisiones, riesgos y próximos pasos sin esconder ambigüedades relevantes. ",
        "Ese enfoque hace que la herramienta sea menos un repositorio y más un mapa compartido de ejecución. ",
    ]
    cursor = index
    while len(text.strip()) < target:
        text += additions[cursor % len(additions)]
        cursor += 1
    return text.strip()
