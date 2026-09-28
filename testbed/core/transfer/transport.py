"""
The one HTTP client every destination module uses to reach a source server.

Owns
    - The URL policy, checked before any socket opens: `https` always; `http` only to a loopback
      host, and only where the environment permits it
    - The `Authorization: Bearer` header, on a session nothing in the environment can rewrite it from
    - `Accept` negotiation for ActivityPub content types, with an `application/json` fallback
    - A fixed timeout on every call, and a cap on the decoded size of every body
    - The descriptive `User-Agent` that lets a source operator see who is fetching
    - Capture of every exchange as an artifact, with credentials redacted as it is built

Must not be bypassed. LOLA §6.1 makes two MUST claims:
    - "The destination MUST fetch data using HTTPS, not HTTP"
    - "It MUST provide the account migration authorization token in requests even when it
      believes the requests are for public content"

Both are auditable only while there is exactly one exit point, which is why this module exists.

Must not
    - Relax the scheme policy beyond loopback. HTTPS is required unless the host resolves to
      loopback and the environment permits it (true in development, test and CI; false in staging and production).
    - Store anything. Artifacts go back to the caller, which decides where they live.
"""

import ipaddress
import json
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests
from django.utils import timezone
from oauth2_provider.settings import oauth2_settings

logger = logging.getLogger(__name__)

# Connect and read timeouts in seconds
TIMEOUT = (5, 30)

MAX_BODY_BYTES = 5 * 1024 * 1024 # 5 MiB
_CHUNK_BYTES = 64 * 1024 # (64 KiB)

# ActivityPub §3.2:
    # MUST present the ActivityStreams object representation in response to application/ld+json; profile="https://www.w3.org/ns/activitystreams".
    # SHOULD also present the ActivityStreams representation in response to application/activity+json as well.
    # The client MUST specify an Accept header with the application/ld+json; profile="https://www.w3.org/ns/activitystreams" media type in order to retrieve the activity.
    # application/json is the fallback.
ACCEPT = (
    'application/ld+json; profile="https://www.w3.org/ns/activitystreams", '
    "application/activity+json; q=0.9, "
    "application/json; q=0.5"
)
USER_AGENT = "activitypub-testbed-lola-destination (+https://github.com/dtinit/activity-pub-testbed)"

# Keep secrets out of the artifacts. Applies to both the headers we send and the headers the source sends back.
# Serves as evidence for LOLA §6.1 ("MUST provide the token"), without revealing the token.
_REDACTED_HEADERS = frozenset({"authorization", "proxy-authorization", "cookie", "set-cookie"})
_REDACTED = "[redacted]"

class TransportError(Exception):
    """
    A request that produced no usable response due to refused by the URL policy, unreachable, timed out or too large.
    
    It is not a 4xx or 5xx status, which are returned as Fetched for the caller to deal with.
    """

@dataclass(frozen=True)
class Fetched:
    """
    Represents one completed exchange.
    Every status comes back as one of these (including 4xx and 5xx).
    """
    url: str            # where the response came from
    status: int         # status code
    headers: object     # source headers
    body: object        # the parsed JSON (or None when the body isn't)
    text: str           # the body as text whether or not it parsed
    artifact: dict      # the exchange as a JSON-serialisable dict with the headers already redacted


def get(url, *, token):
    """
    GET `url` from a source server.

    `token` is the portability access token, and it is required. Pass None only for the requests
    made before authorization exists (discovery RFC 8414 and public-Actor fetches).
    LOLA §6.1 wants the token on every request after that, "even when it believes the requests are for public
    content", so leaving it out has to be a visible decision at the call site.

    Returns a Fetched whatever the status. Raises TransportError when no usable response arrived.
    """
    headers = {"Accept": ACCEPT, "User-Agent": USER_AGENT}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

    try:
        _check_url(url)
        with _new_session() as session:
            with _send(session, url, headers) as response:
                content = _read_body(response)
    except TransportError as exc:
        logger.warning("Transport GET did not complete: %s", exc)
        raise

    text = content.decode("utf-8", errors="replace")
    logger.info(
        "Transport GET %s -> %s (%d bytes, %d ms)",
        _describe(response.url),
        response.status_code,
        len(content),
        response.elapsed.total_seconds() * 1000,
    )
    return Fetched(
        url=response.url,
        status=response.status_code,
        headers=response.headers,
        body=_parse_json(text),
        text=text,
        artifact=_artifact(url, response, text),
    )

def _check_url(url):
    """
    Apply the URL policy, raising TransportError for a URL that may not be fetched.

    https always allowed. http only to a loopback host,
    and where OAUTH2_PROVIDER["ALLOWED_REDIRECT_URI_SCHEMES"] allows it
    """
    try:
        parts = urlsplit(url)
        parts.port  # malformed or out of range port gets caught
    except ValueError:
        raise TransportError("refused a malformed URL") from None

    if parts.username is not None or parts.password is not None:
        raise TransportError(f"refused {_describe(url)}: credentials in the URL")
    if not parts.hostname:
        raise TransportError(f"refused {_describe(url)}: no host")

    if parts.scheme == "http":
        if not _is_loopback(parts.hostname):
            raise TransportError(f"refused {_describe(url)}: plaintext is allowed to loopback only (LOLA §6.1)")
        
        allowed = {scheme.lower() for scheme in oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES}

        if "http" not in allowed:
            raise TransportError(f"refused {_describe(url)}: plaintext is not allowed in this environment")
    
    elif parts.scheme != "https":
        raise TransportError(f"refused {_describe(url)}: scheme {parts.scheme!r} is not https")

def _is_loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
    
# The URL as it may appear in a log line or an error (no userinfo, no query string or fragment)
def _describe(url):
    try:
        parts = urlsplit(url)
        host, port = parts.hostname or "", parts.port
    except ValueError:
        return "a malformed URL"
    if ":" in host:
        host = f"[{host}]"  # an IPv6 literal
    netloc = f"{host}:{port}" if port else host
    return f"{parts.scheme}://{netloc}{parts.path}"

def _new_session():
    session = requests.Session()
    session.trust_env = False
    return session

# One GET with status and headers only, the body stays unread
def _send(session, url, headers):
    try:
        return session.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=False, stream=True)
    except requests.Timeout as exc:
        raise TransportError(f"timed out reaching {_describe(url)}") from exc
    except requests.RequestException as exc:
        raise TransportError(f"could not reach {_describe(url)} ({type(exc).__name__})") from exc

def _read_body(response):
    content = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
            content += chunk
            if len(content) > MAX_BODY_BYTES:
                raise TransportError(
                    f"the response from {_describe(response.url)} is larger than {MAX_BODY_BYTES} bytes"
                )
    except requests.RequestException as exc:
        raise TransportError(
            f"failed reading the response from {_describe(response.url)} ({type(exc).__name__})"
        ) from exc
    return bytes(content)

def _parse_json(text):
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        return None

def _artifact(requested_url, response, text):
    return {
        "method": "GET",
        "requested_url": requested_url,
        "url": response.url,
        "fetched_at": timezone.now().isoformat(),
        "request_headers": _redacted(response.request.headers),
        "status": response.status_code,
        "response_headers": _redacted(response.headers),
        "body": text,
    }

def _redacted(headers):
    return {
        name: _REDACTED if name.lower() in _REDACTED_HEADERS else value
        for name, value in headers.items()
    }
