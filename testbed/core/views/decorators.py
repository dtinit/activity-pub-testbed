"""
Shared decorators and helpers for LOLA views.

- validate_lola_access: OAuth scope + token-to-actor binding gate for LOLA-protected endpoints
- build_auth_context: standardized auth context dict passed to JSON-LD builders
- activitypub_content: sets ActivityPub content-type + CORS headers
"""

import logging
from functools import wraps

from django.core.exceptions import ObjectDoesNotExist

from ..utils.errors import build_actor_mismatch_error, build_insufficient_scope_error

logger = logging.getLogger(__name__)


def validate_lola_access(request, required_scope=True):
    """
    Scope gate and actor binding check for LOLA-protected endpoints.

    Two-layer check, each regulated by a different condition:

    Layer 1 - Scope presence (controlled by `required_scope`):
        Strict endpoints (required_scope=True) MUST carry a token with the activitypub_account_portability scope.
        Returns 403 insufficient_scope otherwise.
        Dual-mode endpoints (required_scope=False) skip this layer so
        unauthenticated/public traffic falls through to their public response.

    Layer 2 - Actor binding enforcement (LOLA Section 5 MUST):
        Runs whenever a portability token is present (request.has_portability_scope) -- regardless of required_scope.
        A dual-mode endpoint stays publicly readable, but the moment a portability token is supplied it must be bound
        to the Actor whose <pk> is in the URL, or the request is rejected with 403 actor_mismatch.

        Binding is persisted at token issuance by ActivityPubOAuth2Validator._save_bearer_token (the write side).
        This gate is the read/enforcement side. The check covers both OptionalOAuth2Authentication paths (Authorization header
        and the demo-only session token) because both set request.auth to the same AccessToken instance, so
        request.auth.actor_binding is available whenever request.has_portability_scope is True.

    Mode summary:
        required_scope=True  (strict):    no token -> 403 insufficient_scope;
                                          token bound to other actor -> 403 actor_mismatch.
        required_scope=False (dual-mode): no token -> public access (valid);
                                          token bound to other actor -> 403 actor_mismatch.

    Args:
        request: HTTP request with OAuth authentication attributes set by
            OptionalOAuth2Authentication. request.auth is the AccessToken.
        required_scope: Whether the LOLA portability scope is required (default: True).
            Pass False for dual-mode endpoints that also serve public traffic but
            must still reject mis-bound portability tokens.

    Returns:
        dict: {'valid': True} on success, or
              {'valid': False, 'error_response': Response} on any failure.
    """

    has_scope = bool(getattr(request, "has_portability_scope", False))

    # Layer 1: scope presence (strict endpoints only)
    if required_scope and not has_scope:
        logger.warning("LOLA access denied: insufficient_scope for %s", request.path)
        return {
            "valid": False,
            "error_response": build_insufficient_scope_error(
                required_scope="activitypub_account_portability",
                endpoint_path=request.path,
                request=request,
            ),
        }

    # No portability token
    if not has_scope:
        return {"valid": True}

    # Layer 2: actor binding. Reached whenever a portability token is present, so dual-mode
    # endpoints cannot leak another actor's augmented data to a token bound to a different actor.
    url_pk = _get_url_pk(request)
    if url_pk is None:
        # Fail closed. All LOLA actor-scoped endpoints carry <pr> in the URL, so this should not occur in normal operation.
        logger.warning(
            "LOLA access denied: actor binding check invoked without URL pk path=%s",
            request.path,
        )
        return {
            "valid": False,
            "error_response": build_actor_mismatch_error(request=request),
        }

    token = getattr(request, "auth", None)
    if token is None:
        # In normal flows has_portability_scope is derived from the token, so this state should not occur;
        # if it does the binding is unverifiable -> fail closed rather than grant on an unverifiable claim.
        logger.warning(
            "LOLA access denied: portability scope claimed without a token object "
            "path=%s",
            request.path,
        )
        return {
            "valid": False,
            "error_response": build_actor_mismatch_error(request=request),
        }

    mismatch = _check_actor_binding(request, token, url_pk)
    if mismatch is not None:
        return mismatch

    logger.info(
        "LOLA access granted: scope=activitypub_account_portability "
        "endpoint=%s actor_pk=%s",
        request.path,
        url_pk,
    )

    return {"valid": True}


def _get_url_pk(request):
    """
    Extract the actor primary key from the URL resolver kwargs.

    All LOLA-protected actor endpoints use the URL pattern
    /api/actors/<int:pk>/... so the actor pk is always available as
    request.resolver_match.kwargs["pk"] when this decorator is called
    from an actor-scoped view.

    Returns None if the pk is not present (e.g. unexpected endpoint shape).
    The caller treats None as a fail-closed signal.
    """
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None:
        return None
    return resolver_match.kwargs.get("pk")


def _check_actor_binding(request, token, url_pk):
    """
    Compare the token's bound Actor against the actor pk in the URL.

    Returns a validation failure dict (with error_response) on mismatch or
    missing binding, or None when the binding is valid.

    Failure modes:
    - Missing binding row (ObjectDoesNotExist on token.actor_binding):
      the token has no TokenActorBinding.
    - binding.actor_id != url_pk: the token is bound to a different actor
      than the one being requested. Fail closed: actor_mismatch.
    """
    try:
        binding = token.actor_binding  # OneToOne reverse accessor
    except ObjectDoesNotExist:
        logger.warning(
            "LOLA access denied: portability token has no actor_binding "
            "token_id=%s path=%s",
            getattr(token, "pk", None),
            request.path,
        )
        return {
            "valid": False,
            "error_response": build_actor_mismatch_error(request=request),
        }

    if binding.actor_id != int(url_pk):
        logger.warning(
            "LOLA access denied: actor_mismatch token_id=%s bound_actor_id=%s "
            "requested_pk=%s path=%s",
            getattr(token, "pk", None),
            binding.actor_id,
            url_pk,
            request.path,
        )
        return {
            "valid": False,
            "error_response": build_actor_mismatch_error(request=request),
        }

    return None


def build_auth_context(request):
    """
    Build the standardized authentication context dict passed to all JSON-LD builders.

    Args:
        request: HTTP request with OAuth authentication attributes set by OptionalOAuth2Authentication.

    Returns:
        dict: Authentication context with keys:
            - is_authenticated: boolean OAuth authentication status
            - has_portability_scope: boolean LOLA scope presence
            - request: HTTP request object for dynamic URL building
    """
    return {
        "is_authenticated": getattr(request, "is_oauth_authenticated", False),
        "has_portability_scope": getattr(request, "has_portability_scope", False),
        "request": request,
    }


def activitypub_content(view_func):
    """
    Decorator that adds the required ActivityPub content-type
    and CORS headers to views that return ActivityPub JSON-LD content.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)

        # Add ActivityPub headers for JSON responses (preserves DRF browsable API)
        if (
            hasattr(request, "accepted_renderer")
            and request.accepted_renderer.format == "json"
        ):
            response["Content-Type"] = "application/activity+json"
            response["Access-Control-Allow-Origin"] = "*"

        return response

    return wrapper
