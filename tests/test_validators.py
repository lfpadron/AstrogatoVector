from utils.validators import (
    JobFormInput,
    find_duplicate_jobs,
    is_probable_linkedin_url,
    is_valid_http_url,
    validate_complete_form,
    validate_cv_input,
    validate_job_input,
    validate_linkedin_input,
)


VALID_DESCRIPTION = (
    "Responsable de liderar iniciativas estratégicas, coordinar equipos multifuncionales, "
    "analizar métricas de negocio y comunicar prioridades con stakeholders internos."
)


def _messages(result_or_messages, level=None):
    messages = getattr(result_or_messages, "messages", result_or_messages)
    if level is None:
        return [message.message for message in messages]
    return [message.message for message in messages if message.level == level]


def test_http_url_is_valid():
    assert is_valid_http_url("http://example.com/job")


def test_https_url_is_valid():
    assert is_valid_http_url("https://www.linkedin.com/in/usuario")


def test_url_without_scheme_is_invalid():
    assert not is_valid_http_url("www.linkedin.com/in/usuario")


def test_linkedin_url_is_probable_linkedin():
    assert is_probable_linkedin_url("https://www.linkedin.com/in/usuario")


def test_external_domain_is_not_probable_linkedin():
    assert not is_probable_linkedin_url("https://example.com/in/usuario")
    result = validate_linkedin_input("", "https://example.com/in/usuario")
    assert result.is_valid
    assert _messages(result, "warning")


def test_empty_cv_is_invalid():
    result = validate_cv_input("")
    assert not result.is_valid
    assert "Agrega tu CV" in _messages(result, "error")[0]


def test_cv_with_text_is_valid():
    assert validate_cv_input("Experiencia profesional relevante.").is_valid


def test_cv_with_file_is_valid():
    assert validate_cv_input("", "cv.pdf", 1024).is_valid


def test_cv_file_too_large_is_invalid():
    result = validate_cv_input("", "cv.pdf", 11 * 1024 * 1024)
    assert not result.is_valid
    assert any("límite de 10 MB" in message for message in _messages(result, "error"))


def test_job_without_title_is_invalid():
    job = JobFormInput(index=1, description=VALID_DESCRIPTION)
    result = validate_job_input(job)
    assert not result.is_valid
    assert "Indica el nombre o título de la Vacante 1." in _messages(result, "error")


def test_job_without_description_or_url_is_invalid():
    job = JobFormInput(index=1, title="Product Manager")
    result = validate_job_input(job)
    assert not result.is_valid
    assert "La Vacante 1 necesita una descripción o un enlace." in _messages(result, "error")


def test_short_description_without_url_is_invalid():
    job = JobFormInput(index=1, title="Product Manager", description="Muy breve.")
    result = validate_job_input(job)
    assert not result.is_valid
    assert any("demasiado breve" in message for message in _messages(result, "error"))


def test_short_description_with_valid_url_is_warning_only():
    job = JobFormInput(
        index=1,
        title="Product Manager",
        description="Muy breve.",
        url="https://www.linkedin.com/jobs/view/123",
    )
    result = validate_job_input(job)
    assert result.is_valid
    assert any("demasiado breve" in message for message in _messages(result, "warning"))


def test_job_valid_by_text():
    job = JobFormInput(index=1, title="Product Manager", description=VALID_DESCRIPTION)
    assert validate_job_input(job).is_valid


def test_job_valid_by_url():
    job = JobFormInput(index=1, title="Product Manager", url="https://www.linkedin.com/jobs/view/123")
    assert validate_job_input(job).is_valid


def test_duplicate_by_url():
    jobs = [
        JobFormInput(index=1, title="A", url="https://www.linkedin.com/jobs/view/123/"),
        JobFormInput(index=2, title="B", url="https://www.linkedin.com/jobs/view/123"),
    ]
    messages = find_duplicate_jobs(jobs)
    assert any("Vacantes 1 y 2" in message.message for message in messages)


def test_duplicate_by_title_and_company():
    jobs = [
        JobFormInput(index=1, title=" Product Manager ", company="Acme"),
        JobFormInput(index=2, title="product   manager", company=" acme "),
    ]
    messages = find_duplicate_jobs(jobs)
    assert any("Vacantes 1 y 2" in message.message for message in messages)


def test_complete_form_without_consent_is_invalid():
    result = validate_complete_form(
        consent_accepted=False,
        cv_text="CV válido",
        cv_file_name=None,
        cv_file_size=None,
        linkedin_text="",
        linkedin_url="",
        jobs=[
            JobFormInput(index=1, title="Uno", description=VALID_DESCRIPTION),
            JobFormInput(index=2, title="Dos", description=VALID_DESCRIPTION),
        ],
        output_language="es",
    )
    assert not result.is_valid
    assert any("aceptar el aviso" in message for message in _messages(result, "error"))


def test_complete_form_is_valid():
    result = validate_complete_form(
        consent_accepted=True,
        cv_text="CV válido",
        cv_file_name=None,
        cv_file_size=None,
        linkedin_text="",
        linkedin_url="",
        jobs=[
            JobFormInput(index=1, title="Uno", description=VALID_DESCRIPTION),
            JobFormInput(index=2, title="Dos", description=VALID_DESCRIPTION),
        ],
        output_language="en",
    )
    assert result.is_valid
