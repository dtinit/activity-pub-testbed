"""
The one HTTP client every destination module uses to reach a source server.

Owns
    - The URL policy, checked before any socket opens: `https` always; `http` only to a loopback
      host, and only where the environment permits it
    - The `Authorization: Bearer` header
    - `Accept` negotiation for ActivityPub content types, with an `application/json` fallback
    - A fixed timeout on every call, and a cap on the decoded size of every body
    - The descriptive `User-Agent` that lets a source operator see who is fetching

Must not be bypassed. LOLA §6.1 makes two MUST claims:
    - "The destination MUST fetch data using HTTPS, not HTTP"
    - "It MUST provide the account migration authorization token in requests even when it
      believes the requests are for public content"

Both are auditable only while there is exactly one exit point, which is why this module exists.

Must not
    - Relax the scheme policy beyond loopback. HTTPS is required unless the host resolves to
      loopback and the environment permits it (true in development, test and CI; false in staging and production).
    - Store anything. The caller decides what to keep from a Fetched, and where.
"""

import json
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests
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
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


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
    body: object        # the parsed JSON (or None when the body isn't)
    text: str           # the body as text whether or not it parsed


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
        try:
            with requests.get(
                url, headers=headers, timeout=TIMEOUT, allow_redirects=False, stream=True
            ) as response:
                content = _read_body(response)
        except requests.RequestException as exc:
            # Connecting, timing out or failing mid-body
            raise TransportError(f"could not fetch {url} ({type(exc).__name__})") from exc
    except TransportError as exc:
        logger.warning("Transport GET did not complete: %s", exc)
        raise

    text = content.decode("utf-8", errors="replace")
    logger.info(
        "Transport GET %s -> %s (%d bytes, %d ms)",
        response.url,
        response.status_code,
        len(content),
        response.elapsed.total_seconds() * 1000,
    )
    return Fetched(
        url=response.url,
        status=response.status_code,
        body=_parse_json(text),
        text=text,
    )

def _check_url(url):
    """
    Apply the URL policy, raising TransportError for a URL that may not be fetched.

    https always allowed. http only to a loopback host,
    and where OAUTH2_PROVIDER["ALLOWED_REDIRECT_URI_SCHEMES"] allows it
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        raise TransportError("refused a malformed URL") from None

    if parts.username is not None or parts.password is not None:
        raise TransportError("refused a URL with credentials in it")
    if not parts.hostname:
        raise TransportError(f"refused {url}: no host")

    if parts.scheme == "http":
        if parts.hostname not in _LOOPBACK_HOSTS:
            raise TransportError(f"refused {url}: plaintext is allowed to loopback only (LOLA §6.1)")
        
        allowed = {scheme.lower() for scheme in oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES}

        if "http" not in allowed:
            raise TransportError(f"refused {url}: plaintext is not allowed in this environment")
    
    elif parts.scheme != "https":
        raise TransportError(f"refused {url}: scheme {parts.scheme!r} is not https")

def _read_body(response):
    # A declared length over the cap is refused before anything is read
    try:
        declared = int(response.headers.get("Content-Length", ""))
    except ValueError:
        declared = None 
    if declared is not None and declared > MAX_BODY_BYTES:
        raise TransportError(
            f"the response from {response.url} declares more than {MAX_BODY_BYTES} bytes"
        )

    content = bytearray()
    for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
        content += chunk
        if len(content) > MAX_BODY_BYTES:
            raise TransportError(f"the response from {response.url} is larger than {MAX_BODY_BYTES} bytes")
    return bytes(content)

def _parse_json(text):
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        return None
