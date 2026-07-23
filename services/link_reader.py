"""Controlled public text page reading for profile and job links."""

from __future__ import annotations

import html
import ipaddress
import re
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from schemas.models import LinkReadResult
from utils.constants import (
    LINK_FETCH_MAX_REDIRECTS,
    LINK_FETCH_TIMEOUT_SECONDS,
    LINK_USER_AGENT,
    MAX_HTTP_RESPONSE_BYTES,
    MIN_LINK_CONTENT_CHARS,
)

UNSAFE_URL_MESSAGE = "El enlace apunta a una dirección no permitida y no puede procesarse."
UNSUPPORTED_CONTENT_MESSAGE = (
    "El enlace no apunta a una página de texto que Astrogato Vector pueda leer. "
    "Copia y pega el contenido manualmente."
)
ACCESS_RESTRICTED_MESSAGE = (
    "La página requiere iniciar sesión o restringe el acceso automatizado. Abre el enlace "
    "en tu navegador, copia el contenido y pégalo en el campo correspondiente."
)
DYNAMIC_OR_EMPTY_MESSAGE = (
    "La página no entregó suficiente contenido visible. Puede depender de JavaScript o "
    "restringir la lectura automática. Copia y pega el texto para continuar."
)
INVALID_URL_MESSAGE = "El enlace no tiene un formato válido. Revisa que comience con http:// o https://."
DNS_ERROR_MESSAGE = "No fue posible encontrar el sitio del enlace. Revisa la dirección o copia y pega el contenido manualmente."
TIMEOUT_MESSAGE = "La lectura del enlace tardó demasiado. Copia y pega el contenido manualmente."
CONNECTION_ERROR_MESSAGE = "No fue posible conectarse al enlace. Copia y pega el contenido manualmente."
TOO_MANY_REDIRECTS_MESSAGE = "El enlace redirigió demasiadas veces. Copia y pega el contenido manualmente."
TOO_LARGE_MESSAGE = "La página es demasiado grande para procesarla de forma segura. Copia y pega el contenido relevante."
EMPTY_CONTENT_MESSAGE = "El enlace no devolvió contenido. Copia y pega el texto para continuar."
NONSTANDARD_STATUS_MESSAGE = (
    "El sitio devolvió una respuesta no estándar o bloqueó la lectura automática. "
    "Copia y pega el contenido manualmente."
)

ACCEPTED_CONTENT_TYPES = {"text/html", "text/plain", "application/xhtml+xml"}
REMOVED_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "canvas",
    "form",
    "iframe",
    "nav",
    "header",
    "footer",
    "aside",
    "button",
    "input",
    "select",
    "textarea",
}
NAVLIKE_PATTERN = re.compile(
    r"(nav|menu|sidebar|footer|header|cookie|subscribe|modal|popup|advert|ad-|social|share|promo)",
    re.IGNORECASE,
)
LOGIN_PATH_PATTERN = re.compile(r"/(login|signin|sign-in|auth|session|account)(/|$)", re.IGNORECASE)
LOGIN_TEXT_PATTERNS = (
    "sign in",
    "sign-in",
    "login",
    "log in",
    "iniciar sesion",
    "iniciar sesión",
    "registrate",
    "regístrate",
    "join now",
    "join linkedin",
    "access denied",
    "members only",
)
DYNAMIC_TEXT_PATTERNS = (
    "enable javascript",
    "please enable javascript",
    "requires javascript",
    "javascript is disabled",
    "loading",
    "cargando",
    "window.__",
    "__next",
    "id=\"root\"",
    "id='root'",
    "id=\"app\"",
    "id='app'",
)

Resolver = Callable[..., list[tuple]]


class _ResponseTooLargeError(Exception):
    """Raised when a response exceeds the configured safe byte limit."""


def fetch_url_content(
    url: str,
    *,
    timeout_seconds: int = LINK_FETCH_TIMEOUT_SECONDS,
    max_redirects: int = LINK_FETCH_MAX_REDIRECTS,
    session: requests.Session | None = None,
    resolver: Resolver | None = None,
) -> LinkReadResult:
    """Fetch and extract visible text from a safe public HTTP(S) URL."""
    requested_url = url.strip()
    safe, message = _validate_public_url(requested_url, resolver=resolver)
    if not safe:
        return _failure(requested_url, message, "unsafe_url" if message == UNSAFE_URL_MESSAGE else "invalid_url")

    owns_session = session is None
    http = session or requests.Session()
    if hasattr(http, "max_redirects"):
        http.max_redirects = max_redirects

    current_url = requested_url
    warnings: list[str] = []

    try:
        for redirect_count in range(max_redirects + 1):
            safe, message = _validate_public_url(current_url, resolver=resolver)
            if not safe:
                return _failure(
                    requested_url,
                    message,
                    "unsafe_url" if message == UNSAFE_URL_MESSAGE else "invalid_url",
                    final_url=current_url,
                    warnings=warnings,
                )

            _clear_session_cookies(http)
            response = http.get(
                current_url,
                headers={"User-Agent": LINK_USER_AGENT},
                timeout=timeout_seconds,
                allow_redirects=False,
                stream=True,
            )
            _clear_session_cookies(http)

            status_code = int(getattr(response, "status_code", 0) or 0)
            final_url = str(getattr(response, "url", current_url) or current_url)
            safe, message = _validate_public_url(final_url, resolver=resolver)
            if not safe:
                return _failure(
                    requested_url,
                    message,
                    "unsafe_url",
                    final_url=final_url,
                    status_code=status_code,
                    warnings=warnings,
                )

            if _is_redirect(status_code):
                location = response.headers.get("Location") if hasattr(response, "headers") else None
                if not location:
                    return _failure(
                        requested_url,
                        DYNAMIC_OR_EMPTY_MESSAGE,
                        "empty_redirect",
                        final_url=final_url,
                        status_code=status_code,
                        warnings=warnings,
                    )
                if redirect_count >= max_redirects:
                    return _failure(
                        requested_url,
                        TOO_MANY_REDIRECTS_MESSAGE,
                        "too_many_redirects",
                        final_url=final_url,
                        status_code=status_code,
                        warnings=warnings,
                    )
                current_url = urljoin(final_url, location)
                warnings.append(f"Redirección a {current_url}")
                continue

            return _process_response(
                requested_url,
                final_url,
                status_code,
                response,
                warnings,
            )

        return _failure(requested_url, TOO_MANY_REDIRECTS_MESSAGE, "too_many_redirects", warnings=warnings)
    except requests.exceptions.Timeout:
        return _failure(requested_url, TIMEOUT_MESSAGE, "timeout", warnings=warnings)
    except requests.exceptions.TooManyRedirects:
        return _failure(requested_url, TOO_MANY_REDIRECTS_MESSAGE, "too_many_redirects", warnings=warnings)
    except requests.exceptions.SSLError:
        return _failure(requested_url, CONNECTION_ERROR_MESSAGE, "tls_error", warnings=warnings)
    except requests.exceptions.ConnectionError:
        return _failure(requested_url, CONNECTION_ERROR_MESSAGE, "connection_error", warnings=warnings)
    except requests.exceptions.RequestException:
        return _failure(requested_url, CONNECTION_ERROR_MESSAGE, "request_error", warnings=warnings)
    finally:
        if owns_session and hasattr(http, "close"):
            http.close()


def read_public_profile_or_job_link(url: str) -> str:
    """Compatibility wrapper that returns extracted text or raises a clean error."""
    result = fetch_url_content(url)
    if not result.success:
        raise ValueError(result.errors[0] if result.errors else CONNECTION_ERROR_MESSAGE)
    return result.normalized_text


def is_safe_public_url(url: str, *, resolver: Resolver | None = None) -> bool:
    """Return whether a URL targets a public HTTP(S) address."""
    safe, _message = _validate_public_url(url, resolver=resolver)
    return safe


def extract_visible_text_from_html(html_text: str) -> str:
    """Extract useful visible text from an HTML document."""
    soup = BeautifulSoup(html_text, "html.parser")
    _remove_non_content_nodes(soup)

    lines: list[str] = []
    title = _extract_title(soup)
    if title:
        lines.append(title)

    for element in soup.find_all(["h1", "h2", "h3", "p", "li", "blockquote", "pre"]):
        text = _clean_inline_text(element.get_text(" ", strip=True))
        if text:
            lines.append(text)

    for row in soup.find_all("tr"):
        cells = [_clean_inline_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        cells = [cell for cell in cells if cell]
        if cells:
            lines.append(" | ".join(cells))

    if not lines:
        body = soup.body or soup
        fallback_text = body.get_text("\n", strip=True)
        lines.extend(fallback_text.splitlines())

    return normalize_web_text("\n".join(lines))


def normalize_web_text(value: str) -> str:
    """Normalize extracted web text conservatively without inventing structure."""
    decoded = html.unescape(value or "").replace("\x00", "")
    decoded = decoded.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    decoded = re.sub(r"[\t\f\v]+", " ", decoded)

    cleaned_lines: list[str] = []
    previous_line: str | None = None
    blank_pending = False
    for raw_line in decoded.split("\n"):
        line = _clean_inline_text(raw_line)
        if not line:
            blank_pending = bool(cleaned_lines)
            continue
        if previous_line == line:
            blank_pending = False
            continue
        if blank_pending and cleaned_lines and cleaned_lines[-1] != "":
            cleaned_lines.append("")
        cleaned_lines.append(line)
        previous_line = line
        blank_pending = False

    return "\n".join(cleaned_lines).strip()


def _process_response(
    requested_url: str,
    final_url: str,
    status_code: int,
    response: requests.Response,
    warnings: list[str],
) -> LinkReadResult:
    content_type = _content_type(response)

    if not _is_valid_http_status_code(status_code):
        return _failure(
            requested_url,
            NONSTANDARD_STATUS_MESSAGE,
            f"http_{status_code}",
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            warnings=warnings,
            access_restricted=True,
        )

    if status_code in {401, 403}:
        return _failure(
            requested_url,
            ACCESS_RESTRICTED_MESSAGE,
            "access_restricted",
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            warnings=warnings,
            access_restricted=True,
        )

    if status_code >= 400:
        return _failure(
            requested_url,
            _http_error_message(status_code),
            f"http_{status_code}",
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            warnings=warnings,
        )

    if content_type and content_type not in ACCEPTED_CONTENT_TYPES:
        return _failure(
            requested_url,
            UNSUPPORTED_CONTENT_MESSAGE,
            "unsupported_content_type",
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            warnings=warnings,
        )

    try:
        content_bytes = _read_limited_response_bytes(response)
    except _ResponseTooLargeError:
        return _failure(
            requested_url,
            TOO_LARGE_MESSAGE,
            "too_large",
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            warnings=warnings,
        )

    if not content_bytes:
        return _failure(
            requested_url,
            EMPTY_CONTENT_MESSAGE,
            "empty",
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            warnings=warnings,
        )

    raw_text = _decode_response_bytes(content_bytes, response)
    page_title = _extract_html_title(raw_text) if _is_html_content(content_type, raw_text) else None
    extracted_text = (
        extract_visible_text_from_html(raw_text)
        if _is_html_content(content_type, raw_text)
        else normalize_web_text(raw_text)
    )

    likely_login = _is_likely_login_page(final_url, page_title, extracted_text)
    if likely_login:
        return _failure(
            requested_url,
            ACCESS_RESTRICTED_MESSAGE,
            "login_page",
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            page_title=page_title,
            extracted_text=extracted_text,
            warnings=warnings,
            access_restricted=True,
            likely_login_page=True,
        )

    character_count = len(extracted_text)
    likely_dynamic = character_count < MIN_LINK_CONTENT_CHARS
    if likely_dynamic:
        return _failure(
            requested_url,
            DYNAMIC_OR_EMPTY_MESSAGE,
            "insufficient_visible_text",
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            page_title=page_title,
            extracted_text=extracted_text,
            warnings=warnings,
            likely_dynamic_page=True,
        )

    return LinkReadResult(
        success=True,
        requested_url=requested_url,
        final_url=final_url,
        status_code=status_code,
        content_type=content_type,
        page_title=page_title,
        extracted_text=extracted_text,
        normalized_text=extracted_text,
        character_count=character_count,
        word_count=_count_words(extracted_text),
        warnings=warnings,
    )


def _validate_public_url(url: str, *, resolver: Resolver | None = None) -> tuple[bool, str | None]:
    parsed = urlparse(url.strip())
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return False, UNSAFE_URL_MESSAGE
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        return False, INVALID_URL_MESSAGE

    hostname = parsed.hostname.strip().lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost") or hostname.endswith(".local"):
        return False, UNSAFE_URL_MESSAGE

    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        return (False, UNSAFE_URL_MESSAGE) if _is_blocked_ip(literal_ip) else (True, None)

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    lookup = resolver or socket.getaddrinfo
    try:
        resolved = lookup(hostname, port, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror):
        return False, DNS_ERROR_MESSAGE

    if not resolved:
        return False, DNS_ERROR_MESSAGE

    for result in resolved:
        address = result[-1][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False, UNSAFE_URL_MESSAGE
        if _is_blocked_ip(ip):
            return False, UNSAFE_URL_MESSAGE

    return True, None


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_reserved,
            ip.is_multicast,
            ip.is_unspecified,
        )
    )


def _is_redirect(status_code: int) -> bool:
    return status_code in {301, 302, 303, 307, 308}


def _is_valid_http_status_code(status_code: int | None) -> bool:
    return status_code is not None and 100 <= status_code <= 599


def _content_type(response: requests.Response) -> str | None:
    raw = response.headers.get("Content-Type", "") if hasattr(response, "headers") else ""
    return raw.split(";", 1)[0].strip().lower() or None


def _read_limited_response_bytes(response: requests.Response) -> bytes:
    content_length = response.headers.get("Content-Length") if hasattr(response, "headers") else None
    if content_length:
        try:
            if int(content_length) > MAX_HTTP_RESPONSE_BYTES:
                raise _ResponseTooLargeError
        except ValueError:
            pass

    chunks: list[bytes] = []
    total = 0
    iterator = _response_chunks(response)
    for chunk in iterator:
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_HTTP_RESPONSE_BYTES:
            raise _ResponseTooLargeError
        chunks.append(chunk)
    return b"".join(chunks)


def _response_chunks(response: requests.Response) -> Iterable[bytes]:
    iter_content = getattr(response, "iter_content", None)
    if callable(iter_content):
        yield from iter_content(chunk_size=64 * 1024)
        return

    content = getattr(response, "content", b"")
    if isinstance(content, str):
        yield content.encode("utf-8", errors="replace")
    else:
        yield content


def _decode_response_bytes(content: bytes, response: requests.Response) -> str:
    encoding = getattr(response, "encoding", None) or "utf-8"
    try:
        return content.decode(encoding, errors="replace")
    except LookupError:
        return content.decode("utf-8", errors="replace")


def _is_html_content(content_type: str | None, raw_text: str) -> bool:
    if content_type in {"text/html", "application/xhtml+xml"}:
        return True
    if content_type == "text/plain":
        return False
    return bool(re.search(r"<\s*(html|body|article|main|p|h1)\b", raw_text, re.IGNORECASE))


def _extract_html_title(raw_text: str) -> str | None:
    soup = BeautifulSoup(raw_text, "html.parser")
    return _extract_title(soup)


def _extract_title(soup: BeautifulSoup) -> str | None:
    if not soup.title:
        return None
    return _clean_inline_text(soup.title.get_text(" ", strip=True))


def _remove_non_content_nodes(soup: BeautifulSoup) -> None:
    for tag_name in REMOVED_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()

    for element in soup.find_all(attrs={"aria-hidden": "true"}):
        element.decompose()

    for element in soup.find_all(True):
        role = " ".join(element.get("role", []) if isinstance(element.get("role"), list) else [str(element.get("role", ""))])
        if role.lower() in {"navigation", "banner", "contentinfo", "complementary", "search"}:
            element.decompose()
            continue

        marker_values: list[str] = []
        for attribute in ("class", "id"):
            value = element.get(attribute)
            if isinstance(value, list):
                marker_values.extend(str(item) for item in value)
            elif value:
                marker_values.append(str(value))
        if marker_values and NAVLIKE_PATTERN.search(" ".join(marker_values)):
            element.decompose()


def _clean_inline_text(value: str) -> str:
    return re.sub(r"[ \t\f\v]+", " ", value or "").strip()


def _is_likely_login_page(final_url: str, page_title: str | None, text: str) -> bool:
    parsed = urlparse(final_url)
    if LOGIN_PATH_PATTERN.search(parsed.path):
        return True

    probe = _accentless(f"{page_title or ''}\n{text[:5000]}").casefold()
    return any(pattern in probe for pattern in LOGIN_TEXT_PATTERNS)


def _accentless(value: str) -> str:
    replacements = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return value.translate(replacements)


def _http_error_message(status_code: int) -> str:
    if status_code == 404:
        return "La página no existe o ya no está disponible. Copia y pega el contenido manualmente."
    if status_code == 429:
        return "El sitio limitó temporalmente la lectura automática. Copia y pega el contenido manualmente."
    if 500 <= status_code <= 599:
        return "El sitio respondió con un error temporal. Copia y pega el contenido manualmente."
    return f"El sitio respondió con HTTP {status_code}. Copia y pega el contenido manualmente."


def _failure(
    requested_url: str,
    message: str | None,
    failure_reason: str,
    *,
    final_url: str | None = None,
    status_code: int | None = None,
    content_type: str | None = None,
    page_title: str | None = None,
    extracted_text: str = "",
    warnings: list[str] | None = None,
    likely_login_page: bool = False,
    likely_dynamic_page: bool = False,
    access_restricted: bool = False,
) -> LinkReadResult:
    normalized_text = normalize_web_text(extracted_text)
    return LinkReadResult(
        success=False,
        requested_url=requested_url,
        final_url=final_url,
        status_code=status_code if _is_valid_http_status_code(status_code) else None,
        content_type=content_type,
        page_title=page_title,
        extracted_text=normalized_text,
        normalized_text=normalized_text,
        character_count=len(normalized_text),
        word_count=_count_words(normalized_text),
        warnings=warnings or [],
        errors=[message or CONNECTION_ERROR_MESSAGE],
        failure_reason=failure_reason,
        likely_login_page=likely_login_page,
        likely_dynamic_page=likely_dynamic_page,
        access_restricted=access_restricted,
    )


def _clear_session_cookies(session: requests.Session) -> None:
    cookies = getattr(session, "cookies", None)
    clear = getattr(cookies, "clear", None)
    if callable(clear):
        clear()


def _count_words(value: str) -> int:
    return len(re.findall(r"\b\w+\b", value, flags=re.UNICODE))
