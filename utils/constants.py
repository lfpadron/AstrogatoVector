"""Constants used across the Astrogato Vector pilot."""

PRODUCT_NAME = "Astrogato Vector"
PRODUCT_SUBTITLE = "Asesor de Posicionamiento Profesional para LinkedIn"
PRODUCT_DESCRIPTION = (
    "Analiza tu experiencia profesional y compárala con vacantes objetivo para crear "
    "una propuesta de posicionamiento más clara, coherente y alineada con el mercado."
)

MIN_JOB_POSTINGS = 2
MAX_JOB_POSTINGS = 6
MAX_CV_FILE_SIZE_MB = 10
MIN_JOB_DESCRIPTION_CHARS = 100
MAX_JOB_DESCRIPTION_CHARS = 25_000
MAX_ALL_JOBS_SOURCE_CHARS = 100_000
MIN_EXTRACTED_CV_CHARS = 200
MIN_PDF_TEXT_CHARS = 200
SCANNED_PDF_EMPTY_PAGE_RATIO = 0.7
SCANNED_PDF_AVG_CHARS_PER_PAGE = 50
CV_PREVIEW_CHARS = 3000
LINK_FETCH_TIMEOUT_SECONDS = 10
LINK_FETCH_MAX_REDIRECTS = 5
MIN_LINK_CONTENT_CHARS = 300
LINK_PREVIEW_CHARS = 2000
MAX_HTTP_RESPONSE_BYTES = 2_000_000
LINK_USER_AGENT = "AstrogatoVectorPilot/0.1 (+local Streamlit application)"
MAX_CANDIDATE_SOURCE_CHARS = 80_000
MAX_CV_SOURCE_CHARS = 65_000
MAX_LINKEDIN_SOURCE_CHARS = 20_000
MAX_PROFILE_GENERATION_INPUT_CHARS = 90_000
MAX_PROFILE_EXPERIENCE_ENTRIES = 30
MAX_MARKET_KEYWORDS_FOR_GENERATION = 100
MAX_REFERENCES_PER_ITEM_FOR_GENERATION = 2
MAX_REASONABLE_YEARS_EXPERIENCE = 70

UPLOAD_TYPES = ("docx", "pdf")
LANGUAGE_LABELS = {
    "es": "Español",
    "en": "English",
}
OUTPUT_LANGUAGES = tuple(LANGUAGE_LABELS.keys())
DEFAULT_OUTPUT_LANGUAGE = "es"

FILE_UPLOAD_HELP = (
    f"Formatos permitidos: DOCX o PDF. Tamaño máximo: {MAX_CV_FILE_SIZE_MB} MB. "
    "La extracción se realiza localmente al procesar si no pegaste texto."
)
LINKEDIN_HELP = (
    "Si no proporcionas un perfil, Astrogato Vector podrá generar una propuesta desde "
    "cero a partir de tu CV."
)
PROCESSING_PLACEHOLDER_MESSAGE = (
    "La información fue validada correctamente y quedó preparada para los siguientes "
    "incrementos de análisis con inteligencia artificial."
)
EMPTY_RESULT_MESSAGE = "Los resultados aparecerán aquí después de procesar la información."

PILOT_NOTICE = (
    "Astrogato Vector utiliza inteligencia artificial para analizar información profesional "
    "y generar recomendaciones orientativas para mejorar el posicionamiento de un perfil de "
    "LinkedIn.<br><br>"
    "Los resultados no garantizan entrevistas, contrataciones, posicionamiento preferente en "
    "LinkedIn, compatibilidad con un sistema ATS específico ni ningún otro resultado laboral."
    "<br><br>"
    "No proporciones RFC, CURP, domicilio particular, números de identificación oficial, "
    "cuentas bancarias, contraseñas, información médica, datos financieros ni información "
    "personal sensible o innecesaria.<br><br>"
    "Esta versión piloto no almacena la información en bases de datos ni conserva el contenido "
    "de los documentos en logs de la aplicación.<br><br>"
    "Parte de la información proporcionada podrá enviarse a un proveedor externo de "
    "inteligencia artificial para realizar el análisis.<br><br>"
    "Revisa y valida cuidadosamente cualquier texto, recomendación o puntuación antes de "
    "utilizarlo. Confirma que no se hayan atribuido habilidades, logros, responsabilidades "
    "o experiencias que no correspondan a tu trayectoria real."
)

CONSENT_TEXT = (
    "He leído el aviso, confirmo que no proporcionaré datos personales sensibles y autorizo "
    "el procesamiento de la información profesional que ingrese."
)

RESULT_TABS = (
    "Perfil LinkedIn",
    "Mercado objetivo",
    "Compatibilidad",
    "Auditoría",
    "CV por vacante",
    "Comunicación",
    "Publicaciones",
    "Descargas",
)
