# Kit de comunicación por vacante

Este incremento genera cartas de presentación, mensajes para recruiters y correos de postulación por cada vacante objetivo.

## Insumos

La generación usa únicamente:

- `CandidateProfessionalProfile`
- `JobAnalysis`
- `JobCompatibility`
- `TargetedCV`
- `OutputLanguage`

No usa CV original, LinkedIn original, `LinkedInProfileOutput`, banner, publicaciones, cartas previas, mensajes previos, búsquedas web ni conocimiento externo de empresa.

## Flujo

1. La pestaña `CV por vacante` debe tener un CV específico generado y validado para la vacante.
2. La pestaña `Postulación` genera un `ApplicationCommunicationKit`.
3. El kit se audita localmente contra evidencia, brechas, longitudes, saludos, asuntos, claims y datos sensibles.
4. Una auditoría de redundancia evita copiar frases largas del CV o repetir piezas entre sí.
5. El usuario puede editar texto y validar cambios localmente sin llamadas a OpenAI.
6. Las exportaciones se preparan en memoria como Markdown, TXT, DOCX, PDF y ZIP.

## Auditorías

La auditoría local valida:

- índice, título y empresa de la vacante;
- correspondencia con compatibilidad y CV específico;
- carta entre 250 y 500 palabras;
- mensaje para recruiter entre 280 y 650 caracteres;
- correo entre 140 y 320 palabras;
- asuntos entre 20 y 120 caracteres;
- ausencia de placeholders, nombres inventados, datos sensibles y metadatos internos;
- claims con evidencia `SUPPORTED` o inferencias marcadas para revisión;
- brechas críticas no presentadas como capacidades.

La auditoría de redundancia usa heurísticas locales: oraciones normalizadas, n-gramas, Jaccard, frases idénticas largas y copia de bullets del CV.

## Exportaciones

Cada vacante puede exportarse como:

- Markdown;
- TXT para copiar y pegar;
- DOCX;
- PDF con texto seleccionable.

El ZIP `astrogato-vector-comunicaciones-por-vacante.zip` contiene:

- `application-communications/README.txt`
- `application-communications/manifest.json`
- carpetas `vacancy-XX/`
- `communication-kit.md`
- `communication-kit.txt`
- `communication-kit.docx`
- `communication-kit.pdf`
- `review-summary.json`

El resumen JSON no incluye el texto completo de carta, correo ni mensaje.

## Privacidad

El kit no envía ni exporta CV original, vacantes crudas, URLs, prompts, respuestas crudas, request IDs, tokens, secretos ni evidencia completa.

No envía correos, no conecta Gmail/Outlook y no inventa destinatarios.

## Prueba local

```bash
uv run python scripts/test_application_communications.py
```

Para guardar una vista previa local con datos ficticios:

```bash
uv run python scripts/test_application_communications.py --save-preview
```
