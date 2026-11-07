"""
Turning a source server into a set of URLs, by asking it rather than assuming.

Owns
    - Fetching `/.well-known/oauth-authorization-server` (RFC 8414)
    - Reading 'token_endpoint` and `activitypub_account_portability`, once `issuer` matches (RFC 8414 §3.3)
    - Fetching the public Actor and reading `endpoints.oauthMigrationEndpoint`
    - Re-fetching the Actor with the token
    - And resolving the scope-gated `migration` object into the four collection URLs (outbox, content, following, blocked)
    - Also owns starting from either a base URL or an Actor URL, since a user may supply either

Must not
    - Read `settings` for a URL that should have been discovered.
      In Mode C, this server already knows its own endpoints, so constructing one instead of fetching it
      silently deletes the discovery half of the protocol.
"""

import logging
from urllib.parse import urlsplit

from testbed.core.transfer import jobs, transport

logger = logging.getLogger(__name__)

WELL_KNOWN = '/.well-known/oauth-authorization-server'
METADATA_ARTIFACT = "well-known"
PUBLIC_ACTOR_ARTIFACT = "actor-public"


class DiscoveryError(Exception):
    """
    The source's documents do not give usable endpoints.
    The message is safe to store.
    """


def discover(job):
    """
    Ask the source for its portability authorization endpoint and its token endpoint. Save both on the job.

    Raises DiscoveryError when its documents do not give them.
    TransportError and RateLimited propgate because recording a failure or a pause is the job owner's
    """
    try:
        authorization_endpoint, token_endpoint = _endpoints(job)
    except DiscoveryError as exc:
        logger.warning("Transfer job %s: discovery failed: %s", job.pk, exc)
        raise

    job.authorization_endpoint = authorization_endpoint
    job.token_endpoint = token_endpoint
    job.save(update_fields=["authorization_endpoint", "token_endpoint", "updated_at"])

    logger.info(
        "Transfer job %s: authorization endpoint %s, token endpoint %s",
        job.pk,
        authorization_endpoint,
        token_endpoint,
    )


def _endpoints(job):
    issuer = job.source_base_url.strip("/")

    metadata = _fetch(job, METADATA_ARTIFACT, _metadata_url(issuer))
    if metadata is None:
        raise DiscoveryError(f"{issuer} serves no RFC 8414 metadata document")
    # RFC 8414 §3.3: metadata naming another issuer MUST NOT be used
    if _string(metadata, "issuer").rstrip("/") != issuer:
        raise DiscoveryError(f"the metadata document at {issuer} names a different issuer")
    token_endpoint = _string(metadata, "token_endpoint")
    if not token_endpoint:
        raise DiscoveryError(f"the metadata document at {issuer} has no token_endpoint")

    from_metadata = _string(metadata, "activitypub_account_portability")
    from_actor = _actor_endpoint(job) if job.source_actor_url else ""
    if from_actor and from_metadata and from_actor != from_metadata:
        logger.warning(
            "Transfer job %s: the Actor names %s but the metadata names %s; using the Actor's",
            job.pk,
            from_actor,
            from_metadata,
        )
    authorization_endpoint = from_actor or from_metadata
    if not authorization_endpoint:
        raise DiscoveryError(f"{issuer} advertises no portability authorization endpoint")

    for endpoint in (authorization_endpoint, token_endpoint):
        try:
            transport.check_url(endpoint)
        except transport.TransportError as exc:
            raise DiscoveryError(f"a discovered endpoint in unusable: {exc}") from exc

    return authorization_endpoint, token_endpoint


def _fetch(job, name, url):
    # Kept as evidence before it is judged.
    # Returns the JSON object or None when the response is not one
    fetched = transport.get(url, token=None)
    jobs.record_artifact(job, name, fetched)
    if fetched.status != 200 or not isinstance(fetched.body, dict):
        return None
    return fetched.body


def _actor_endpoint(job):
    # The Actor URL is advisory (§5.3). An unusable Actor falls back to the metadata rather than failing
    actor = _fetch(job, PUBLIC_ACTOR_ARTIFACT, job.source_actor_url)
    endpoint = _string(actor.get("endpoints") if actor else None, "oauthMigrationEndpoint")
    if not endpoint:
        logger.warning(
            "Transfer job %s: the Actor at %s gives no oauthMigrationEndpoint; using the metadata's",
            job.pk,
            job.source_actor_url,
        )
    return endpoint


def _metadata_url(issuer):
    # RFC 8414 §3.1: the well-known path goes between the host and any path the issuer has
    parts = urlsplit(issuer)
    return f"{parts.scheme}://{parts.netloc}{WELL_KNOWN}{parts.path}"


def _string(document, key):
    # A missing key, a null or a non-string reads as "". A malformed document cannot raise KeyError
    value = document.get(key) if isinstance(document, dict) else None
    return value if isinstance(value, str) else ""

