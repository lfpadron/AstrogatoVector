# Plan editorial profesional para LinkedIn

El incremento genera un `ProfessionalBrandPlan` con un calendario de cuatro semanas para fortalecer marca profesional en LinkedIn.

## Entradas

La generación usa únicamente:

- `CandidateProfessionalProfile`
- `TargetMarketAnalysis`
- `CompatibilityReport`
- `AuditReport`
- `OutputLanguage`

No usa CV crudo, LinkedIn crudo, vacantes completas, cartas, correos, mensajes para recruiters, publicaciones previas, URLs ni búsquedas externas.

## Contrato

El plan contiene exactamente cuatro semanas, tres publicaciones por semana y doce publicaciones en total. Los días son sugeridos como lunes, miércoles y viernes, sin fechas absolutas.

Cada `LinkedInPostPlan` incluye título, objetivo, tema, audiencia, formato, tipo, hook, cuerpo, CTA, hashtags, keywords, evidencia usada, claims para revisión y conteo de caracteres.

Los formatos se validan por longitud:

- `short`: 300 a 600 caracteres.
- `medium`: 600 a 1200 caracteres.
- `long`: 1200 a 2200 caracteres.

## Auditoría local

`editorial_plan_audit_service.py` valida:

- estructura de cuatro semanas y doce publicaciones;
- diversidad de temas, hooks, CTAs e hashtags;
- longitud declarada y real;
- CTAs profesionales sin pedir likes, shares ni follows;
- hashtags válidos y relacionados con evidencia o mercado;
- evidencia y keywords respaldadas;
- brechas del mercado no presentadas como experiencia;
- bloqueo de información confidencial, datos sensibles, presupuestos, vulnerabilidades, clientes o marcadores internos.

Las ediciones del usuario se validan localmente y no llaman OpenAI.

## UI y exportación

La pestaña `Marca Profesional` permite generar, revisar y editar cada publicación. La pestaña `Descargas` expone Markdown, HTML, DOCX, PDF y `linkedin-editorial-plan.zip`.

El ZIP contiene README, manifest, `calendar.md`, `calendar.html`, `calendar.docx`, `calendar.pdf` y carpetas `week01` a `week04` con archivos Markdown por semana y por publicación.

No incluye imágenes, videos, carouseles, blog, newsletter, CRM, tracking, LinkedIn API ni publicación automática.

## Smoke test

```bash
uv run python scripts/test_editorial_plan.py
```

Para guardar artefactos ficticios de revisión:

```bash
uv run python scripts/test_editorial_plan.py --save-preview
```
