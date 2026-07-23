from __future__ import annotations

from datetime import datetime

from schemas.application_communication_models import (
    ApplicationCommunicationKit,
    ApplicationEmailOutput,
    CommunicationClaim,
    CoverLetterOutput,
    GreetingStrategy,
    RecruiterMessageOutput,
)
from schemas.enums import EvidenceStatus, OutputLanguage
from services.application_communication_audit_service import count_words
from tests.targeted_cv_helpers import build_targeted_cv, build_targeted_cv_inputs


def build_application_communication_inputs():
    profile, market, compatibility = build_targeted_cv_inputs()
    targeted_cvs = {1: build_targeted_cv(1), 2: build_targeted_cv(2)}
    return profile, market, compatibility, targeted_cvs


def build_application_communication_kit(job_index: int = 1) -> ApplicationCommunicationKit:
    profile, market, compatibility, targeted_cvs = build_application_communication_inputs()
    job = next(item for item in market.job_analyses if item.job_index == job_index)
    job_compatibility = next(item for item in compatibility.job_compatibilities if item.job_index == job_index)
    cv = targeted_cvs[job_index]
    company = job.company or "su equipo"
    role = job.title
    claim = CommunicationClaim(
        text="Gestión de proyectos Agile, coordinación de stakeholders y seguimiento operativo con Jira.",
        evidence_status=EvidenceStatus.SUPPORTED,
        evidence_sources=["CandidateProfessionalProfile.skills", "TargetedCV.experience"],
    )
    cover = _cover_letter(role, company, include_gap=job_index == 2)
    recruiter = _recruiter_message(role, company, include_gap=job_index == 2)
    email = _application_email(role, company, include_gap=job_index == 2)
    return ApplicationCommunicationKit(
        output_language=OutputLanguage.ES,
        generated_at=datetime(2026, 1, 1),
        target_job_index=job.job_index,
        target_job_title=job.title,
        target_company=job.company,
        compatibility_score=job_compatibility.compatibility_score,
        compatibility_band=job_compatibility.compatibility_band,
        targeted_cv_version=cv.cv_version,
        cover_letter=CoverLetterOutput(
            greeting_strategy=GreetingStrategy.COMPANY_TEAM,
            greeting=f"Hola, equipo de {company}:",
            full_text=cover,
            sign_off="Saludos cordiales",
            word_count=count_words(cover),
            keywords_used=["Agile", "Stakeholder management", "Jira"] if job_index == 1 else ["Stakeholder management"],
            strengths_used=["Coordinación de stakeholders", "Gestión de proyectos Agile"],
            claims=[claim],
            review_notes=["Revisar tono y nombre de la empresa antes de enviar."],
        ),
        recruiter_message=RecruiterMessageOutput(
            message=recruiter,
            character_count=len(recruiter.strip()),
            call_to_action="Conversar brevemente sobre el alcance del rol.",
            keywords_used=["Stakeholder management"],
            strengths_used=["Comunicación operativa con stakeholders"],
            claims=[claim],
            personalization_notes=["No incluye teléfono ni correo por defecto."],
            review_notes=["Ajustar si existe un contacto real identificado por el usuario."],
        ),
        application_email=ApplicationEmailOutput(
            subject_options=[
                f"Postulación a {role} - experiencia en gestión de proyectos",
                f"Interés en {role} | Agile y stakeholders",
            ],
            greeting_strategy=GreetingStrategy.RECRUITING_TEAM,
            greeting=f"Hola, equipo de reclutamiento de {company}:",
            full_text=email,
            sign_off="Saludos cordiales",
            attachments_mentioned=["CV adjunto"],
            word_count=count_words(email),
            call_to_action="Quedo atento para compartir información adicional o conversar sobre el rol.",
            keywords_used=["Agile", "Stakeholder management"] if job_index == 1 else ["Stakeholder management"],
            strengths_used=["Gestión de proyectos", "Comunicación con stakeholders"],
            claims=[claim],
            personalization_notes=["Menciona el alcance del rol sin inventar cultura o reputación de la empresa."],
            review_notes=["Confirmar adjuntos antes de enviar."],
        ),
        calls_to_action=[
            "Conversar brevemente sobre el rol.",
            "Compartir información adicional si resulta útil.",
        ],
        personalization_notes=[
            f"Personalizar solo con elementos visibles de la vacante {job_index}.",
        ],
        risks_or_claims_requiring_review=_risks(job_index),
    )


def _cover_letter(role: str, company: str, *, include_gap: bool) -> str:
    gap_sentence = (
        "También conviene preparar una respuesta honesta sobre Kubernetes, ya que aparece como expectativa de la vacante "
        "pero no debe presentarse como dominio demostrado. "
        if include_gap
        else ""
    )
    return (
        f"Hola, equipo de {company}:\n\n"
        f"Me interesa postularme al rol de {role} porque combina coordinación de proyectos, comunicación con áreas "
        "involucradas y seguimiento disciplinado de prioridades. Mi trayectoria respaldada se concentra en gestión "
        "de proyectos Agile, trabajo con stakeholders y uso de Jira para mantener visibilidad operativa. En Empresa "
        "Demo coordiné iniciativas internas donde fue necesario ordenar actividades, conectar conversaciones entre "
        "equipos de tecnología y sostener acuerdos claros sobre avances, riesgos y siguientes pasos.\n\n"
        "Puedo aportar una forma de trabajo práctica: traduzco objetivos en planes manejables, ayudo a que las "
        "personas involucradas compartan contexto común y doy seguimiento a compromisos sin perder de vista la "
        "calidad de la comunicación. La evidencia disponible muestra una reducción de 15% en tiempos de seguimiento "
        "en proyectos internos, cifra que usaría con cuidado y solo cuando sea pertinente dentro del proceso. "
        f"{gap_sentence}"
        "Para esta vacante priorizaría ejemplos concretos de coordinación, priorización y colaboración con perfiles "
        "técnicos, evitando presentar como experiencia aquello que todavía deba fortalecerse. También cuidaría que "
        "la conversación se enfoque en prácticas observables: definición de próximos pasos, seguimiento de acuerdos, "
        "visibilidad de dependencias y comunicación clara con personas involucradas. Ese enfoque permite conectar mi "
        "experiencia real con las responsabilidades del puesto sin añadir herramientas, certificaciones o resultados "
        "que no estén respaldados.\n\n"
        "Me gustaría conversar sobre los retos del puesto y entender mejor cómo se organiza la gestión de proyectos "
        "en el equipo. Si mi perfil resulta relevante, con gusto comparto información adicional y adapto los ejemplos "
        "a las responsabilidades más importantes del proceso.\n\n"
        "Saludos cordiales"
    )


def _recruiter_message(role: str, company: str, *, include_gap: bool) -> str:
    gap_sentence = (
        " También tengo identificada una brecha técnica a preparar antes de presentarla como experiencia."
        if include_gap
        else ""
    )
    return (
        f"Hola, equipo de {company}. Me interesa el rol de {role}. Cuento con experiencia respaldada en gestión "
        "de proyectos con marcos Agile, coordinación con stakeholders y uso de Jira para dar visibilidad. En Empresa Demo trabajé "
        "con equipos de tecnología y mantuve prioridades visibles para facilitar acuerdos y avances medibles."
        f"{gap_sentence} Me gustaría conversar brevemente sobre el alcance del puesto."
    )


def _application_email(role: str, company: str, *, include_gap: bool) -> str:
    gap_sentence = (
        "Además, revisaría con cuidado cualquier expectativa sobre Kubernetes para no presentarla como experiencia "
        "demostrada si no corresponde a la evidencia disponible. "
        if include_gap
        else ""
    )
    return (
        f"Hola, equipo de reclutamiento de {company}:\n\n"
        f"Comparto mi postulación para la vacante de {role}. Mi experiencia respaldada conecta gestión de "
        "proyectos Agile, comunicación con stakeholders y seguimiento con Jira. En Empresa Demo participé "
        "en iniciativas internas de tecnología, ordenando prioridades, facilitando comunicación entre equipos y "
        "dando seguimiento a compromisos para mantener claridad sobre avances y próximos pasos.\n\n"
        "Adjunto mi CV para su revisión. Considero que mi perfil puede aportar estructura, comunicación y disciplina "
        "de ejecución en contextos donde varias áreas necesitan alinearse alrededor de objetivos compartidos. También "
        "puedo explicar cómo organizo prioridades, doy seguimiento a acuerdos y adapto la comunicación según el nivel "
        "de detalle que requiere cada interlocutor, manteniendo trazabilidad, claridad, ritmo y foco durante la ejecución. "
        f"{gap_sentence}"
        "Quedo atento para compartir información adicional o conversar brevemente sobre el alcance del rol y las "
        "responsabilidades principales.\n\n"
        "Saludos cordiales"
    )


def _risks(job_index: int) -> list[str]:
    if job_index == 2:
        return ["Preparar conversación sobre Kubernetes sin declararlo como experiencia respaldada."]
    return ["Evitar ampliar métricas más allá del 15% respaldado."]
