# CV específico por vacante

## Propósito

El incremento genera un CV optimizado para cada vacante analizada. Cada CV reorganiza y redacta evidencia profesional existente para una vacante concreta, sin inventar experiencia, herramientas, certificaciones, idiomas, cargos, fechas ni cifras.

## Flujo

```text
Perfil profesional
       +
Vacante
       +
Compatibilidad
       ↓
Generación estructurada
       ↓
Auditoría de evidencia
       ↓
Auditoría ATS
       ↓
Edición y validación
       ↓
DOCX / PDF / Markdown
```

## Fuentes permitidas

La generación usa únicamente `CandidateProfessionalProfile`, un `JobAnalysis`, un `JobCompatibility` y el idioma de salida. No utiliza CV crudo, vacantes crudas, perfil optimizado de LinkedIn, banner, prompts ni respuestas crudas como evidencia.

## Evidencia

El perfil profesional define lo que puede afirmarse del candidato. La vacante define relevancia, vocabulario y prioridad. Una keyword solo puede aparecer como capacidad si está respaldada por el perfil o por un `RequirementMatch` con evidencia válida.

## Selección de experiencia

Cada empleo fuente debe estar representado exactamente una vez. Un empleo puede marcarse como no incluido en el CV exportado, pero debe conservarse en el objeto estructurado con una razón de exclusión. La auditoría valida empleador, cargo fuente, fechas, ubicación, tecnologías, industrias y bullets.

## Relevancia

La generación puede priorizar responsabilidades, skills y bullets por alineación con la vacante. La relevancia no representa probabilidad de contratación.

## Keywords y Brechas

Las keywords respaldadas pueden integrarse en resumen, skills o bullets. Las faltantes u omitidas se conservan como información interna de revisión y no se presentan como experiencia real.

## ATS

La auditoría ATS del CV es local y orientativa. Usa pesos fijos para cobertura de keywords, requisitos, skills, alineación de título, legibilidad y consistencia. No simula un ATS específico.

## Edición

El usuario puede editar título profesional, resumen, skills seleccionadas, bullets y visibilidad de educación, certificaciones e idiomas. Editar no llama OpenAI y no reemplaza el objeto generado auditado.

## Validación

Antes de exportar se revalida localmente el CV editado. La validación bloquea cargos inflados, cifras nuevas, herramientas no respaldadas, placeholders, empleos nuevos, datos sensibles y keywords no respaldadas.

## Exportación

Cada CV puede exportarse como Markdown, DOCX y PDF. El ZIP `astrogato-vector-cvs-por-vacante.zip` contiene una carpeta por vacante con `cv.md`, `cv.docx`, `cv.pdf` y `review-summary.json`.

Los CV exportables no incluyen scores, brechas, evidencias internas, hallazgos, prompts, respuestas crudas, request IDs ni tokens.

## Privacidad

La llamada de generación envía solo datos estructurados reducidos. Las exportaciones son locales y viven en memoria de sesión. El ZIP no incluye CV original, archivos subidos, URLs ni secretos.

## Fingerprint

El fingerprint de generación se calcula por vacante a partir de candidato reducido, vacante estructurada, compatibilidad, idioma, modelo y versión de prompt. El fingerprint de exportación considera el CV editado y la versión de exportación.

## Limitaciones

El score ATS es orientativo. La aplicación no garantiza entrevistas ni contratación. Todavía no genera cartas de presentación, mensajes para recruiters ni correos de postulación.

## Script

```bash
uv run python scripts/test_targeted_cv_generation.py
```

Para guardar artefactos ficticios de preview:

```bash
uv run python scripts/test_targeted_cv_generation.py --save-preview
```

Los previews se escriben en `tmp/targeted_cv_preview/`.
