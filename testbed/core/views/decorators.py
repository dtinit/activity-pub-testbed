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

    Two-layer check (both layers apply when required_scope=True):

    Layer 1 - Scope validation:
        Confirms the request carries a token with the activitypub_account_portability
        scope. Returns 403 insufficient_scope if not.

    Layer 2 - Actor binding enforcement (LOLA Section 5 MUST):
        Confirms the token is bound to the Actor whose <pk> appears in the URL.
        Returns 403 actor_mismatch if not.

        LOLA Section 5: "This scope MUST be limited to an account - if there is
        more than one account on the source server, the source server MUST NOT
        allow access to any other accounts than the one granted."

        This check covers all three authentication paths because
        OptionalOAuth2Authentication (header, URL param, session) all produce the
        same request.auth object, so request.auth.actor_binding is available
        whenever request.has_portability_scope is True.

    Args:
        request: HTTP request with OAuth authentication attributes set by
            OptionalOAuth2Authentication. request.auth is the AccessToken.
        required_scope: Whether the LOLA portability scope is required (default: True).

    Returns:
        dict: {'valid': True} on success, or
              {'valid': False, 'error_response': Response} on any failure.
    """
    # Layer 1: scope check
    if required_scope and not getattr(request, "has_portability_scope", False):
        logger.warning("LOLA access denied: insufficient_scope for %s", request.path)
        return {
            "valid": False,
            "error_response": build_insufficient_scope_error(
                required_scope="activitypub_account_portability",
                endpoint_path=request.path,
                request=request,
            ),
        }

    # Layer 2: actor binding check (only when a portability token is present)
    if required_scope and getattr(request, "has_portability_scope", False):
        token = getattr(request, "auth", None)
        url_pk = _get_url_pk(request)

        if url_pk is None:
            # All LOLA-gated endpoints are actor-scoped with <pk> in the
            # URL. A missing pk here means the decorator is being invoked from an
            # unexpected endpoint shape. Fail closed rather than silently skip
            # a LOLA Section 5 MUST.
            logger.warning(
                "LOLA access denied: actor binding check invoked without URL pk "
                "path=%s",
                request.path,
            )
            return {
                "valid": False,
                "error_response": build_actor_mismatch_error(request=request),
            }

        if token is not None:
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
