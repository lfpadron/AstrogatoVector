from __future__ import annotations

from dataclasses import dataclass

import pytest
import requests

from schemas.models import DocumentParseSummary, LinkReadResult
from services.candidate_input_service import CandidatePreparationResult
from services.input_resolution_service import (
    TEXT_PROFILE_PRIORITY_MESSAGE,
    resolve_all_inputs,
    resolve_job_inputs,
    resolve_linkedin_input,
)
from services.link_reader import (
    ACCESS_RESTRICTED_MESSAGE,
    DYNAMIC_OR_EMPTY_MESSAGE,
    LINK_USER_AGENT,
    NONSTANDARD_STATUS_MESSAGE,
    UNSAFE_URL_MESSAGE,
    UNSUPPORTED_CONTENT_MESSAGE,
    extract_visible_text_from_html,
    fetch_url_content,
    is_safe_public_url,
    normalize_web_text,
)
from utils.constants import MAX_HTTP_RESPONSE_BYTES
from utils.validators import JobFormInput


LONG_TEXT = (
    "Product manager role focused on platform strategy, stakeholder communication, "
    "roadmap prioritization, analytics, experimentation, customer discovery, launch "
    "planning, cross-functional execution, executive updates, process improvement and "
    "team coordination across complex technology organizations. "
    * 4
)


class CookieJar:
    def __init__(self) -> None:
        self.clear_calls = 0

    def clear(self) -> None:
        self.clear_calls += 1


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        url: str = "https://example.com/page",
        headers: dict[str, str] | None = None,
        body: bytes | str = "",
        encoding: str = "utf-8",
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.headers = headers or {}
        self.encoding = encoding
        self._body = body.encode(encoding) if isinstance(body, str) else body

    def iter_content(self, chunk_size: int = 64 * 1024):
        for index in range(0, len(self._body), chunk_size):
            yield self._body[index : index + chunk_size]


class FakeSession:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []
        self.cookies = CookieJar()
        self.closed = False
        self.max_redirects = None

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


@dataclass
class FakeFetcher:
    responses: dict[str, LinkReadResult]
    calls: list[str]

    def __call__(self, url: str) -> LinkReadResult:
        self.calls.append(url)
        return self.responses[url]


def public_resolver(host: str, port: int, **kwargs):
    return [(None, None, None, "", ("93.184.216.34", port))]


def private_resolver(host: str, port: int, **kwargs):
    return [(None, None, None, "", ("10.0.0.5", port))]


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "http://localhost/page",
        "http://127.0.0.1/page",
        "http://0.0.0.0/page",
        "http://[::1]/page",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/internal",
        "http://172.16.1.1/internal",
        "http://192.168.1.2/internal",
    ],
)
def test_unsafe_urls_are_rejected(url):
    assert not is_safe_public_url(url, resolver=public_resolver)


def test_safe_public_url_is_allowed():
    assert is_safe_public_url("https://example.com/job", resolver=public_resolver)


def test_domain_resolving_to_private_ip_is_rejected():
    assert not is_safe_public_url("https://internal.example/job", resolver=private_resolver)


def test_fetch_uses_limited_plain_http_request():
    response = FakeResponse(
        headers={"Content-Type": "text/plain"},
        body=LONG_TEXT,
    )
    session = FakeSession([response])

    result = fetch_url_content("https://example.com/job", session=session, resolver=public_resolver)

    assert result.success
    assert result.normalized_text.startswith("Product manager role")
    assert session.calls[0][1]["headers"]["User-Agent"] == LINK_USER_AGENT
    assert session.calls[0][1]["allow_redirects"] is False
    assert session.cookies.clear_calls >= 2


def test_html_page_extracts_visible_content_and_metadata():
    response = FakeResponse(
        headers={"Content-Type": "text/html; charset=utf-8"},
        body=_html_page(),
    )
    result = fetch_url_content("https://example.com/job", session=FakeSession([response]), resolver=public_resolver)

    assert result.success
    assert result.page_title == "Senior Product Manager"
    assert "Visible responsibilities" in result.normalized_text
    assert "Platform | Strategy" in result.normalized_text
    assert "hidden analytics" not in result.normalized_text


def test_plain_text_page_succeeds():
    response = FakeResponse(headers={"Content-Type": "text/plain"}, body=LONG_TEXT)
    result = fetch_url_content("https://example.com/plain", session=FakeSession([response]), resolver=public_resolver)

    assert result.success
    assert result.content_type == "text/plain"


def test_low_text_or_dynamic_page_is_rejected():
    response = FakeResponse(
        headers={"Content-Type": "text/html"},
        body='<html><body><div id="root">Loading...</div><script>hydrate()</script></body></html>',
    )
    result = fetch_url_content("https://example.com/app", session=FakeSession([response]), resolver=public_resolver)

    assert not result.success
    assert result.likely_dynamic_page
    assert DYNAMIC_OR_EMPTY_MESSAGE in result.errors


def test_login_page_is_rejected():
    response = FakeResponse(
        url="https://example.com/login",
        headers={"Content-Type": "text/html"},
        body="<html><head><title>Sign in</title></head><body><p>Join now to continue</p></body></html>",
    )
    result = fetch_url_content("https://example.com/login", session=FakeSession([response]), resolver=public_resolver)

    assert not result.success
    assert result.access_restricted
    assert result.likely_login_page
    assert ACCESS_RESTRICTED_MESSAGE in result.errors


@pytest.mark.parametrize("status_code", [401, 403])
def test_access_restricted_status_codes_are_rejected(status_code):
    response = FakeResponse(status_code=status_code, headers={"Content-Type": "text/html"}, body="")
    result = fetch_url_content("https://example.com/private", session=FakeSession([response]), resolver=public_resolver)

    assert not result.success
    assert result.access_restricted
    assert ACCESS_RESTRICTED_MESSAGE in result.errors


@pytest.mark.parametrize("status_code", [404, 429, 500])
def test_http_errors_return_clean_messages(status_code):
    response = FakeResponse(status_code=status_code, headers={"Content-Type": "text/html"}, body="")
    result = fetch_url_content("https://example.com/missing", session=FakeSession([response]), resolver=public_resolver)

    assert not result.success
    assert result.failure_reason == f"http_{status_code}"
    assert result.errors


def test_nonstandard_http_status_is_rejected_without_validation_error():
    response = FakeResponse(status_code=999, headers={"Content-Type": "text/html"}, body="")

    result = fetch_url_content("https://example.com/blocked", session=FakeSession([response]), resolver=public_resolver)

    assert not result.success
    assert result.status_code is None
    assert result.failure_reason == "http_999"
    assert result.access_restricted
    assert result.errors == [NONSTANDARD_STATUS_MESSAGE]


@pytest.mark.parametrize(
    "exception,reason",
    [
        (requests.exceptions.Timeout(), "timeout"),
        (requests.exceptions.ConnectionError(), "connection_error"),
        (requests.exceptions.TooManyRedirects(), "too_many_redirects"),
    ],
)
def test_request_exceptions_return_clean_messages(exception, reason):
    result = fetch_url_content("https://example.com/job", session=FakeSession([exception]), resolver=public_resolver)

    assert not result.success
    assert result.failure_reason == reason
    assert result.errors


def test_redirect_to_private_address_is_blocked_before_following():
    redirect = FakeResponse(
        status_code=302,
        url="https://example.com/job",
        headers={"Location": "http://127.0.0.1/private"},
    )
    session = FakeSession([redirect])

    result = fetch_url_content("https://example.com/job", session=session, resolver=public_resolver)

    assert not result.success
    assert result.errors == [UNSAFE_URL_MESSAGE]
    assert len(session.calls) == 1


def test_too_many_manual_redirects_are_rejected():
    responses = [
        FakeResponse(status_code=302, url=f"https://example.com/{index}", headers={"Location": f"/{index + 1}"})
        for index in range(7)
    ]
    result = fetch_url_content(
        "https://example.com/0",
        session=FakeSession(responses),
        resolver=public_resolver,
        max_redirects=5,
    )

    assert not result.success
    assert result.failure_reason == "too_many_redirects"


def test_content_too_large_is_rejected_by_header():
    response = FakeResponse(
        headers={"Content-Type": "text/plain", "Content-Length": str(MAX_HTTP_RESPONSE_BYTES + 1)},
        body="",
    )
    result = fetch_url_content("https://example.com/large", session=FakeSession([response]), resolver=public_resolver)

    assert not result.success
    assert result.failure_reason == "too_large"


@pytest.mark.parametrize("content_type", ["application/pdf", "image/png", "application/zip"])
def test_binary_content_types_are_rejected(content_type):
    response = FakeResponse(headers={"Content-Type": content_type}, body=b"%PDF-1.7")
    result = fetch_url_content("https://example.com/file", session=FakeSession([response]), resolver=public_resolver)

    assert not result.success
    assert result.errors == [UNSUPPORTED_CONTENT_MESSAGE]


def test_html_extraction_removes_scripts_nav_and_duplicate_lines():
    text = extract_visible_text_from_html(
        """
        <html>
          <head><title>Role &amp; Details</title><script>alert("hidden")</script></head>
          <body>
            <nav>Menu</nav>
            <main>
              <h1>Role &amp; Details</h1>
              <p>Visible text   with   spacing.</p>
              <p>Visible text   with   spacing.</p>
              <ul><li>First skill</li><li>Second skill</li></ul>
              <table><tr><th>Area</th><th>Focus</th></tr><tr><td>Product</td><td>Growth</td></tr></table>
            </main>
          </body>
        </html>
        """
    )

    assert "alert" not in text
    assert "Menu" not in text
    assert "Role & Details" in text
    assert text.count("Visible text with spacing.") == 1
    assert "Area | Focus" in text
    assert "Product | Growth" in text


def test_normalize_web_text_decodes_entities_and_deduplicates_lines():
    text = normalize_web_text("A&nbsp;B\r\nA&nbsp;B\n\n\nC   D")

    assert text == "A B\n\nC D"


def test_profile_text_wins_and_does_not_fetch_url():
    def fail_fetch(url: str) -> LinkReadResult:
        raise AssertionError("fetcher should not be called")

    result = resolve_linkedin_input(" Perfil pegado con experiencia suficiente. ", "https://example.com/profile", fetcher=fail_fetch)

    assert result.is_valid
    assert result.source == "text"
    assert result.text.startswith("Perfil pegado")
    assert result.messages[0].message == TEXT_PROFILE_PRIORITY_MESSAGE


def test_profile_url_success_recovers_text():
    fetcher = FakeFetcher(
        {"https://example.com/profile": _success_result("https://example.com/profile", LONG_TEXT)},
        [],
    )

    result = resolve_linkedin_input("", "https://example.com/profile", fetcher=fetcher)

    assert result.is_valid
    assert result.source == "url"
    assert result.text == LONG_TEXT.strip()
    assert result.summary.character_count == len(LONG_TEXT)
    assert fetcher.calls == ["https://example.com/profile"]


def test_profile_url_failure_blocks_resolution():
    fetcher = FakeFetcher(
        {"https://example.com/profile": _failure_result("https://example.com/profile")},
        [],
    )

    result = resolve_all_inputs(
        _prepared_cv(),
        linkedin_text="",
        linkedin_url="https://example.com/profile",
        jobs=[
            JobFormInput(index=1, title="Uno", description=LONG_TEXT),
            JobFormInput(index=2, title="Dos", description=LONG_TEXT),
        ],
        output_language="es",
        fetcher=fetcher,
    )

    assert not result.is_valid
    assert result.candidate_input is None
    assert "Perfil de LinkedIn" in result.link_error
    assert fetcher.calls == ["https://example.com/profile"]


def test_job_description_with_url_does_not_fetch():
    def fail_fetch(url: str) -> LinkReadResult:
        raise AssertionError("fetcher should not be called")

    result = resolve_job_inputs(
        [JobFormInput(index=1, title="Product Manager", description=LONG_TEXT, url="https://example.com/job")],
        fetcher=fail_fetch,
    )

    assert result.is_valid
    assert result.jobs[0].source == "text"
    assert result.jobs[0].description == LONG_TEXT.strip()
    assert result.jobs[0].link_summary is None


def test_job_url_success_sets_effective_description():
    fetcher = FakeFetcher({"https://example.com/job": _success_result("https://example.com/job", LONG_TEXT)}, [])
    result = resolve_job_inputs(
        [JobFormInput(index=1, title="Product Manager", url="https://example.com/job")],
        fetcher=fetcher,
    )

    assert result.is_valid
    assert result.jobs[0].source == "url"
    assert result.jobs[0].description == LONG_TEXT.strip()
    assert result.jobs[0].link_summary.requested_url == "https://example.com/job"


def test_job_three_failure_stops_before_job_four():
    fetcher = FakeFetcher(
        {
            "https://example.com/job2": _success_result("https://example.com/job2", LONG_TEXT),
            "https://example.com/job3": _failure_result("https://example.com/job3"),
            "https://example.com/job4": _success_result("https://example.com/job4", LONG_TEXT),
        },
        [],
    )

    result = resolve_all_inputs(
        _prepared_cv(),
        linkedin_text="",
        linkedin_url="",
        jobs=[
            JobFormInput(index=1, title="Uno", description=LONG_TEXT),
            JobFormInput(index=2, title="Dos", url="https://example.com/job2"),
            JobFormInput(index=3, title="Tres", url="https://example.com/job3"),
            JobFormInput(index=4, title="Cuatro", url="https://example.com/job4"),
        ],
        output_language="es",
        fetcher=fetcher,
    )

    assert not result.is_valid
    assert result.candidate_input is None
    assert result.failed_link_index == 3
    assert fetcher.calls == ["https://example.com/job2", "https://example.com/job3"]


def test_integration_valid_cv_empty_profile_text_jobs_and_url_job_builds_final_input():
    fetcher = FakeFetcher({"https://example.com/job3": _success_result("https://example.com/job3", LONG_TEXT)}, [])

    result = resolve_all_inputs(
        _prepared_cv(),
        linkedin_text="",
        linkedin_url="",
        jobs=[
            JobFormInput(index=1, title="Uno", description=LONG_TEXT),
            JobFormInput(index=2, title="Dos", description=LONG_TEXT),
            JobFormInput(index=3, title="Tres", url="https://example.com/job3"),
        ],
        output_language="en",
        fetcher=fetcher,
    )

    assert result.is_valid
    assert result.candidate_input is not None
    assert result.candidate_input.linkedin_source == "generated"
    assert len(result.candidate_input.jobs) == 3
    assert result.candidate_input.jobs[2].source == "url"
    assert result.link_reading_completed


def test_integration_second_job_link_failure_identifies_vacante_two():
    fetcher = FakeFetcher({"https://example.com/job2": _failure_result("https://example.com/job2")}, [])

    result = resolve_all_inputs(
        _prepared_cv(),
        linkedin_text="",
        linkedin_url="",
        jobs=[
            JobFormInput(index=1, title="Uno", description=LONG_TEXT),
            JobFormInput(index=2, title="Dos", url="https://example.com/job2"),
        ],
        output_language="es",
        fetcher=fetcher,
    )

    assert not result.is_valid
    assert result.candidate_input is None
    assert result.failed_link_index == 2
    assert "Vacante 2" in result.link_error


def _html_page() -> str:
    return f"""
    <html>
      <head><title>Senior Product Manager</title></head>
      <body>
        <header>Navigation</header>
        <main>
          <h1>Senior Product Manager</h1>
          <p>Visible responsibilities {LONG_TEXT}</p>
          <ul><li>Coordinate teams</li><li>Prioritize roadmap</li></ul>
          <table><tr><td>Platform</td><td>Strategy</td></tr></table>
          <script>hidden analytics</script>
        </main>
      </body>
    </html>
    """


def _prepared_cv() -> CandidatePreparationResult:
    return CandidatePreparationResult(
        cv_text=LONG_TEXT,
        cv_source="text",
        cv_filename=None,
        cv_file_size=None,
        cv_preview=LONG_TEXT,
        cv_summary=DocumentParseSummary(
            source="text",
            character_count=len(LONG_TEXT),
            word_count=100,
        ),
    )


def _success_result(url: str, text: str) -> LinkReadResult:
    return LinkReadResult(
        success=True,
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        page_title="Public page",
        extracted_text=text,
        normalized_text=text,
        character_count=len(text),
        word_count=100,
    )


def _failure_result(url: str) -> LinkReadResult:
    return LinkReadResult(
        success=False,
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        errors=[DYNAMIC_OR_EMPTY_MESSAGE],
        failure_reason="insufficient_visible_text",
        likely_dynamic_page=True,
    )
