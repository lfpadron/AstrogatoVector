# Astrogato Vector

Asesor de Posicionamiento Profesional para LinkedIn.

## Descripción

Astrogato Vector es un piloto funcional para capturar información profesional, compararla contra vacantes objetivo y preparar una propuesta de posicionamiento para LinkedIn.

## Estado

Estado actual: análisis, generación, compatibilidad, auditoría y paquete profesional descargable.

## Requisitos

- Python 3.12 o compatible.

## Instalación

Crear entorno virtual:

```bash
python -m venv .venv
```

Activar en Windows:

```bash
.venv\Scripts\activate
```

Activar en Linux/macOS:

```bash
source .venv/bin/activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Variables de entorno

Crear el archivo local de variables a partir del ejemplo.

Windows:

```bash
copy .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

La API de OpenAI se utiliza en el diagnóstico manual, la extracción profesional del candidato, el análisis estructurado de vacantes, la evaluación semántica de compatibilidad y la generación del perfil optimizado de LinkedIn al pulsar `Procesar`. La auditoría final de LinkedIn y ATS y el paquete profesional descargable se calculan localmente a partir de resultados estructurados ya generados.

Configuración OpenAI para diagnóstico:

```env
OPENAI_API_KEY=...
OPENAI_MODEL_FAST=...
OPENAI_MODEL_QUALITY=...
OPENAI_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=1
OPENAI_DIAGNOSTIC_ENABLED=true
```

Utiliza nombres de modelos disponibles para tu cuenta. No incluyas secretos reales en archivos versionados.

## Ejecución

```bash
streamlit run app.py
```

## Pruebas

```bash
pytest
```

`reportlab` está incluido para generar PDFs digitales ficticios en las pruebas unitarias.

Prueba local del banner PNG con datos ficticios:

```bash
uv run python scripts/test_banner_generation.py
```

Prueba local de compatibilidad con datos ficticios:

```bash
uv run python scripts/test_compatibility_analysis.py
```

Prueba local del paquete final con datos ficticios:

```bash
uv run python scripts/test_final_package_export.py
```

## JSON Schema

Los modelos estructurados usan Pydantic v2 y pueden exportarse como JSON Schema:

```bash
uv run python scripts/export_schemas.py
```

Los archivos generados se escriben en `generated_schemas/`. La carpeta se ignora porque los esquemas son artefactos reproducibles y no contienen datos reales.

## Diagnóstico OpenAI

La app incluye un diagnóstico manual en la barra lateral. También puede ejecutarse por consola:

```bash
uv run python scripts/openai_diagnostic.py
```

El diagnóstico no analiza CV, no envía datos del formulario, consume una pequeña cantidad de tokens, requiere una API key válida y valida una respuesta Pydantic estructurada.

## Extracción profesional del candidato

El botón `Procesar` ya extrae un `CandidateProfessionalProfile` estructurado a partir del CV efectivo y, cuando exista, el perfil de LinkedIn.

En esta etapa:

- se envían CV y perfil opcional al proveedor de inteligencia artificial;
- las vacantes todavía no se envían a esta llamada;
- se aplica un filtro preventivo limitado de datos sensibles;
- se utilizan estados de evidencia `SUPPORTED`, `INFERRED`, `MISSING` y `CONFLICT`;
- se validan referencias y cifras con una auditoría local;
- las respuestas requieren revisión humana antes de usarse.

El filtro preventivo no garantiza detectar todos los datos sensibles. Evita incluir información personal sensible o innecesaria desde el origen.

También puede probarse con datos ficticios:

```bash
uv run python scripts/test_candidate_extraction.py
```

## Análisis del mercado objetivo

Después de extraer el perfil profesional, el botón `Procesar` analiza entre dos y seis vacantes objetivo y genera un `TargetMarketAnalysis`.

En esta etapa:

- se envían las descripciones efectivas de las vacantes al proveedor de inteligencia artificial;
- no se envía CV, perfil de LinkedIn ni perfil profesional extraído en esta llamada;
- se identifican responsabilidades, requisitos, skills, tecnologías, seniority y keywords;
- se diferencia entre requisitos obligatorios y deseables;
- se calcula frecuencia de keywords entre vacantes;
- el análisis describe el mercado y no compara todavía al candidato contra vacantes;
- las respuestas requieren revisión humana antes de usarse.

También puede probarse con vacantes ficticias:

```bash
uv run python scripts/test_job_analysis.py
```

## Compatibilidad por vacante

Después de contar con un perfil profesional y un mercado objetivo válidos, la app calcula un `CompatibilityReport` con un `JobCompatibility` por vacante.

En esta etapa:

- OpenAI ayuda a clasificar la correspondencia semántica requisito por requisito;
- el score final 0–100 se calcula localmente;
- se usan seis dimensiones con pesos MVP: experiencia y responsabilidades, skills y conocimientos, herramientas y tecnologías, liderazgo y gestión, industria y negocio, educación/certificaciones/idiomas;
- se muestran evidencias, requisitos cubiertos, brechas, riesgos, recomendaciones y confidence;
- las dimensiones no solicitadas no se puntúan como cero y su peso se redistribuye;
- solo se aplican penalizaciones limitadas por requisitos críticos obligatorios faltantes, brecha de seniority significativa e idioma obligatorio ausente;
- el score no representa probabilidad de contratación ni garantiza resultados;
- el perfil optimizado de LinkedIn y el banner no se usan como evidencia.

También puede probarse con datos ficticios:

```bash
uv run python scripts/test_compatibility_analysis.py
```

## Generación del perfil optimizado de LinkedIn

Después de contar con un perfil profesional y un mercado objetivo válidos, el botón `Procesar` genera un `LinkedInProfileOutput` editable.

En esta etapa:

- se usa el perfil profesional respaldado como evidencia del candidato;
- se usa el análisis de mercado para vocabulario, prioridades y keywords;
- se genera banner textual, headline, About, experiencia reescrita, skills priorizadas y keywords ATS;
- las keywords del mercado no respaldadas se muestran como brechas, no como capacidades;
- el contenido queda editable antes de copiarlo;
- el banner PNG se genera localmente con Pillow desde el contenido editable;
- el objeto auditado no se modifica con las ediciones;
- el resultado requiere revisión humana antes de publicarse;
- la compatibilidad por vacante es independiente del contenido optimizado de LinkedIn.

También puede probarse con datos ficticios:

```bash
uv run python scripts/test_linkedin_profile_generation.py
```

## Banner PNG para LinkedIn

Desde la sección `Banner profesional`, el usuario puede editar el texto, elegir una de cuatro plantillas y generar un PNG descargable.

En esta etapa:

- las dimensiones del banner son 1584 × 396 píxeles;
- la generación es local y programática con Pillow;
- existen cuatro plantillas: profesional claro, profesional oscuro, ejecutivo azul y tecnología limpia;
- no utiliza IA de imágenes;
- no descarga fondos ni assets externos;
- respeta una zona segura conservadora para la fotografía de perfil;
- ajusta tipografía y saltos de línea para evitar texto cortado;
- valida contraste, dimensiones, firma PNG, zona segura y overflow;
- guarda solo el último PNG en memoria de sesión;
- no almacena archivos permanentemente;
- permite descargar `astrogato-vector-linkedin-banner.png` cuando la auditoría pasa.

También puede probarse con datos ficticios:

```bash
uv run python scripts/test_banner_generation.py
```

## Auditoría integral LinkedIn y ATS

Después de contar con perfil profesional, mercado objetivo, perfil de LinkedIn generado y compatibilidad por vacante, la app calcula un `AuditReport` local y explicable.

En esta etapa:

- se usan únicamente `CandidateProfessionalProfile`, `TargetMarketAnalysis`, `LinkedInProfileOutput` y `CompatibilityReport`;
- no se vuelve a enviar CV, PDF, DOCX, vacantes completas ni banner PNG;
- se calculan scores 0-100 para LinkedIn y ATS con pesos fijos;
- se muestran KPI, resumen ejecutivo, hallazgos, fortalezas, riesgos, Quick Wins y recomendaciones;
- se validan localmente duplicados, categorías, severidades, recomendaciones y consistencia matemática;
- los scores no son probabilidades y no garantizan entrevistas, rankings ni contratación.

También puede probarse con datos ficticios:

```bash
uv run python scripts/test_final_audit.py
```

## Paquete profesional descargable

Después de contar con perfil profesional, mercado objetivo, perfil de LinkedIn, compatibilidad y auditoría integral válidos, la pestaña `Descargas` muestra la sección `Entregables`.

En esta etapa:

- se consolida un `FinalDeliverablePackage` local;
- se prioriza el contenido editado por el usuario sobre el contenido generado y auditado;
- se requiere auditoría integral válida para generar el paquete completo;
- el banner PNG es opcional y se incluye si está vigente;
- se exportan Markdown, HTML, DOCX, PDF y ZIP en memoria;
- el ZIP incluye README, manifest y JSON reducidos de compatibilidad y auditoría;
- los archivos se auditan antes de habilitar descargas;
- no se guarda contenido permanentemente;
- no se llama OpenAI ni servicios externos durante la exportación.

El HTML individual es autocontenido cuando incluye banner. El HTML dentro del ZIP usa una ruta relativa a `linkedin-banner.png`.

También puede probarse con datos ficticios:

```bash
uv run python scripts/test_final_package_export.py
```

## Comportamiento actual

- El consentimiento es obligatorio para procesar.
- El texto pegado tiene prioridad sobre archivos o enlaces.
- El CV puede capturarse por texto o archivo DOCX/PDF.
- El archivo de CV tiene un límite de 10 MB.
- DOCX extrae párrafos y tablas en memoria.
- PDF requiere texto seleccionable y se extrae en memoria con `pypdf`.
- Los PDFs probablemente escaneados se detectan y se rechazan sin OCR.
- El perfil de LinkedIn es opcional.
- El perfil de LinkedIn puede pegarse como texto o leerse desde un enlace público compatible.
- Las vacantes objetivo deben estar entre dos y seis.
- Cada vacante requiere título y descripción o enlace.
- La descripción de una vacante debe tener al menos 100 caracteres, salvo que exista un enlace válido.
- Las vacantes con solo enlace se leen de forma secuencial; si un enlace obligatorio falla, se detiene el procesamiento.
- Se detectan duplicados evidentes y se muestran advertencias.
- Se construye una entrada normalizada temporal en memoria después de validar.
- Se extrae un perfil profesional estructurado del candidato mediante OpenAI cuando la configuración está completa.
- Se analizan las vacantes objetivo con OpenAI en una llamada separada que no recibe datos del candidato.
- Se genera un perfil optimizado de LinkedIn a partir del perfil auditado y el mercado auditado.
- Se genera un banner PNG programático para LinkedIn desde el contenido editable, a solicitud explícita del usuario.
- Se calcula una auditoría integral local de posicionamiento LinkedIn y ATS a partir de los resultados estructurados.
- Se genera un paquete profesional descargable en Markdown, HTML, DOCX, PDF y ZIP desde resultados validados y contenido editado.
- Existen modelos Pydantic v2 para entrada, evidencia, mercado, perfil, compatibilidad, auditorías, comunicación, contenidos y resultado completo.
- Los contratos están preparados para JSON Schema y futuros Structured Outputs.
- Existen ejemplos ficticios en `schemas/examples.py` para validar serialización sin usar datos reales.
- Existe un cliente OpenAI encapsulado con timeout, reintentos limitados, diagnóstico estructurado manual, extracción profesional con evidencia y análisis de mercado.

## Seguridad y privacidad

- No se utiliza OCR.
- El diagnóstico de OpenAI no envía información del formulario, CV, perfil, vacantes ni archivos.
- La extracción profesional envía el CV y el perfil opcional al proveedor de IA, pero no envía las vacantes.
- El análisis de mercado envía vacantes, pero no envía CV, LinkedIn ni perfil profesional extraído.
- La generación de LinkedIn envía solo el perfil profesional estructurado, el mercado estructurado y el idioma.
- El banner PNG se genera localmente con Pillow, sin llamadas a OpenAI, imágenes remotas, logos ni fondos externos.
- La auditoría integral se calcula localmente y no reenvía CV, vacantes completas, perfil de LinkedIn original ni banner PNG.
- El paquete profesional se exporta localmente en memoria, no llama OpenAI, no usa servicios web y no almacena documentos permanentemente.
- El paquete no incluye CV original, archivos subidos, URLs, prompts, respuestas crudas, API keys, request IDs ni tokens.
- Los bytes del banner viven solo en memoria de sesión y se reemplazan al regenerar.
- Antes de la extracción se aplica un filtro preventivo limitado de patrones sensibles evidentes.
- Los enlaces se consultan solo como páginas públicas de texto mediante HTTP/HTTPS.
- No se usan navegador automatizado, cookies, sesiones, credenciales ni técnicas para evadir restricciones de acceso.
- Se bloquean enlaces a localhost, redes privadas, direcciones internas, link-local, reservadas y esquemas no HTTP/HTTPS.
- Se limita el tamaño de respuesta y se aceptan únicamente páginas HTML, XHTML o texto plano.
- No se guarda información en base de datos.
- No se escriben documentos ni contenido extraído en logs.
- No se almacenan archivos de CV en disco.

## Problemas frecuentes

### El PDF parece escaneado

Pega el contenido como texto o genera un PDF digital con texto seleccionable.

### El DOCX no contiene texto

Verifica que el contenido no sea una imagen incrustada dentro de Word.

### El texto extraído está incompleto

Pega manualmente el contenido en el campo de texto.

### El enlace requiere iniciar sesión

Abre el enlace en tu navegador, copia el contenido visible y pégalo manualmente.

### El enlace depende de JavaScript

Algunos sitios no entregan texto visible en la respuesta inicial. Copia y pega la descripción o perfil para continuar.

## Limitaciones de enlaces

- La lectura de enlaces es de mejor esfuerzo y funciona principalmente con páginas públicas que entregan HTML o texto plano.
- LinkedIn y otros sitios pueden bloquear la lectura automática, requerir login o depender de JavaScript.
- No se inicia sesión, no se usan cookies del navegador y no se evaden restricciones.
- Si un enlace obligatorio falla, el procesamiento se detiene y el usuario debe pegar el texto manualmente.
- Los enlaces eliminados, respuestas binarias, PDFs, imágenes, ZIPs o descargas se rechazan.
- Las respuestas tienen límites de timeout, redirecciones y tamaño.
- Las URLs internas, privadas, reservadas, link-local o locales se bloquean por seguridad.

## Limitaciones actuales

- La lectura de enlaces no accede a contenido detrás de login, muros, cookies, JavaScript obligatorio o bloqueos anti-automatización.
- No implementa OCR.
- No genera CV optimizado, mensajes, cartas, publicaciones, correos, PowerPoint ni Excel.

## Próximo incremento

Generación de un CV optimizado y específico para cada vacante, manteniendo trazabilidad con el perfil profesional y evitando afirmaciones no respaldadas.
# AstrogatoVector
