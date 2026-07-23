# Paquete final de entregables

El paquete final de Astrogato Vector consolida resultados ya validados y ediciones explícitas del usuario para generar documentos profesionales descargables.

## Prerrequisitos

Para generar el paquete completo deben existir:

- `CandidateProfessionalProfile`
- `TargetMarketAnalysis`
- `LinkedInProfileOutput`
- `CompatibilityReport`
- `AuditReport` válido

El banner PNG es opcional. Si no está disponible o quedó desactualizado frente al texto editable, se omite del paquete y se registra `Banner PNG not included.`

## Flujo

```text
Resultados auditados
        +
Ediciones del usuario
        +
Banner opcional
        ↓
Consolidación
        ↓
Validación
        ↓
Exporters
        ↓
Auditoría de archivos
        ↓
Descargas individuales y ZIP
```

## Contenido

El paquete incluye:

- perfil de LinkedIn listo para copiar;
- banner textual;
- headline;
- About;
- experiencia reescrita;
- skills priorizadas;
- keywords ATS;
- compatibilidad por vacante;
- fortalezas;
- brechas;
- recomendaciones;
- auditoría LinkedIn;
- auditoría ATS;
- metodología y disclaimer.

No genera CV optimizado, cartas, mensajes, publicaciones, correos, PowerPoint ni Excel.

## Edit State

Cuando existe `linkedin_profile_edit_state`, sus campos tienen prioridad sobre el objeto `LinkedInProfileOutput` auditado para:

- banner textual;
- headline;
- About;
- experiencia reescrita;
- skills seleccionadas;
- keywords seleccionadas.

El objeto auditado original se conserva como referencia interna. El manifest indica `content_source` como `user-edited` o `generated-and-audited`.

## Validación

Antes de exportar se valida que el contenido tenga headline, About, experiencia, skills, keywords, compatibilidad y auditoría. También se revisan scores, banner textual, placeholders, posibles datos sensibles, unsupported claims, secretos, prompts y respuestas crudas.

Los hallazgos bloqueantes impiden generar archivos. Los warnings permiten exportar.

## Formatos

Markdown usa UTF-8, encabezados claros, tablas simples y una referencia relativa al banner cuando aplica.

HTML es local, responsivo, imprimible, sin JavaScript, sin recursos remotos y con CSS incrustado. La descarga individual puede usar data URI para el banner; el HTML dentro del ZIP usa `linkedin-banner.png`.

DOCX se genera en memoria con `python-docx`, estilos simples, tablas, encabezado discreto, pie con disclaimer y banner insertado cuando está disponible.

PDF se genera en memoria con ReportLab. El texto es seleccionable, usa márgenes profesionales, tablas legibles, disclaimer y banner opcional.

ZIP contiene documentos, manifest, README y JSON reducidos. No incluye CV original, archivos subidos, URLs, prompts, respuestas crudas, `.env`, logs ni archivos temporales.

## Manifest

`manifest.json` incluye versión, fecha, idioma, fuente de contenido, archivos incluidos, estado del banner, scores y versiones de metodología. No incluye API keys, request IDs, tokens, modelo OpenAI ni fingerprints completos.

## Privacidad

La exportación es local y trabaja en memoria con `BytesIO`, `StringIO` y `zipfile`. No llama OpenAI, servicios web, conversores externos, Gmail, Drive ni APIs de almacenamiento. No guarda documentos permanentemente durante el uso normal.

## Fingerprint

El fingerprint considera contenido editable, compatibilidad, auditoría, idioma, versión del paquete, versión de exportación y presencia/fingerprint del banner. Si no cambia, la app reutiliza los bytes generados en sesión.

## Script

Prueba con datos ficticios:

```bash
uv run python scripts/test_final_package_export.py
```

Para guardar previews ficticios:

```bash
uv run python scripts/test_final_package_export.py --save-preview
```

Los previews se escriben en `tmp/final_package_preview/`, que está ignorado por git.
