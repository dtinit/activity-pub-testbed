"""
The OAuth authorization process, seen from the destination side.

Owns
    - Building the authorization URL (`client_id`, `redirect_uri`, `scope`, `state`)
    - Generating and validating `state`
    - Parsing the callback's `code`, `state` and `activitypub_actor`
    - The token exchange
    - And for Mode B (serve as a Destination Server only), the per-source-server client credentials this
      server holds as a registered OAuth client on that source server.

Must not
    - Prefer the Actor ID the user typed over the `activitypub_actor` returned with the
      authorization code. LOLA §5.3: the destination "MUST use the Actor ID provided with the
      authorization code rather than the original one the user communicated.".
    - Accept a callback whose `state` does not match the one issued for that job
"""

import logging
from urllib.parse import quote_plus, urlsplit

from django.conf import settings
from django.urls import reverse

from testbed.core.oauth.scopes import scope_grants_portability
from testbed.core.transfer import transport

logger = logging.getLogger(__name__)

# RFC 6749 §4.1.2.1 and §5.2. Only these are recorded from a source's answer, never its free text
OAUTH_ERRORS = frozenset(
    {
        "invalid_request",
        "unauthorized_client",
        "access_denied",
        "unsupported_response_type",
        "invalid_scope",
        "server_error",
        "temporarily_unavailable",
        "invalid_client",
        "invalid_grant",
        "unsupported_grant_type",
    }
)


class AuthorizationError(Exception):
    """The authorization cannot start, or did not complete. The message is safe to show the user."""


def callback_url():
    return f"{settings.BASE_URL}{reverse('transfer-callback')}"


def complete_authorization(job, params):
    """
    Take the source's answer to this job's authorization request.

    Keeps the Actor the source authorized (LOLA §5.3) and exchanges the code for a token.
    Raises AuthorizationError, or TransportError when the token endpoint could not be reached.
    """
    error = params.get("error")
    if error:
        raise AuthorizationError(f"the source refused authorization ({_error_code(error)})")

    actor_url = params.get("activitypub_actor")
    if not actor_url:
        raise AuthorizationError("the source named no authorized Actor (activitypub_actor, LOLA §5.3)")
    _require_source_origin(job, actor_url, "the authorized Actor")
    # Checked before the code is spent. A longer URL would fail at save, after the exchange
    if len(actor_url) > job._meta.get_field("authorized_actor_url").max_length:
        raise AuthorizationError("the authorized Actor's URL is too long to keep")

    token = _exchange(job, params.get("code"))

    # LOLA §5.3: the Actor the source authorized wins over the one the user typed
    if job.source_actor_url and job.source_actor_url != actor_url:
        logger.warning(
            "Transfer job %s: the user gave %s, the source authorized %s; using the source's",
            job.pk,
            job.source_actor_url,
            actor_url,
        )
    job.authorized_actor_url = actor_url
    job.set_access_token(token)
    job.oauth_state = None
    job.pkce_verifier = ""
    job.save(
        update_fields=[
            "authorized_actor_url",
            "encrypted_access_token",
            "oauth_state",
            "pkce_verifier",
            "updated_at",
        ]
    )
    logger.info("Transfer job %s: authorized as %s", job.pk, actor_url)


def _exchange(job, code):
    client = _client(job)
    fetched = transport.post(
        job.token_endpoint,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": callback_url(),
            "code_verifier": job.pkce_verifier,
        },
        # RFC 6749 §2.3.1: each is form-encoded before it becomes the Basic user and password
        auth=(quote_plus(client.client_id), quote_plus(client.get_client_secret())),
    )

    body = fetched.body if isinstance(fetched.body, dict) else {}
    if fetched.status != 200:
        raise AuthorizationError(
            f"the token endpoint refused the code ({fetched.status}, {_error_code(body.get('error'))})"
        )
    token = body.get("access_token")
    # RFC 6749 §7.1: a token type the client does not understand MUST NOT be used
    if not isinstance(token, str) or not token or str(body.get("token_type", "")).lower() != "bearer":
        raise AuthorizationError("the token endpoint returned no bearer token")
    if "scope" in body and not scope_grants_portability(body["scope"]):
        raise AuthorizationError("the source granted a scope without account portability")
    return token


def _client(job):
    # Through the job's owner, so another user's registration at the same source is never used
    client = job.user.source_clients.filter(source_base_url=job.source_base_url).first()
    if client is None:
        raise AuthorizationError(f"no client is registered for {job.source_base_url}")
    return client


def _require_source_origin(job, url, what):
    # Names only our own source_base_url: `url` may come from the browser's query string
    source = urlsplit(job.source_base_url)
    try:
        other = urlsplit(url)
    except ValueError:
        other = None
    if other is None or (other.scheme.lower(), other.netloc.lower()) != (source.scheme.lower(), source.netloc.lower()):
        raise AuthorizationError(f"{what} is not on {job.source_base_url}")


def _error_code(value):
    return value if value in OAUTH_ERRORS else "unrecognised error"
