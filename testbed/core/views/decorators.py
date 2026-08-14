"""
Shared decorators and helpers for LOLA views.

Access-control decorators:
- actor_required: resolve the URL <pk> to an Actor (404 if missing) and inject it
- lola_scope_required: strict LOLA gate - portability scope is mandatory
- lola_scope_optional: dual-mode LOLA gate - public allowed, binding still enforced

Supporting helpers:
- lola_access_error: the gate logic behind the two decorators (Response | None)
- build_auth_context: standardized auth context dict passed to JSON-LD builders
- activitypub_content: sets ActivityPub content-type + CORS headers
"""

import logging
from functools import wraps

from django.core.exceptions import ObjectDoesNotExist

from ..models import Actor
from ..oauth.scopes import LOLA_PORTABILITY_SCOPE
from ..utils.errors import (
    build_actor_mismatch_error,
    build_actor_not_found_error,
    build_insufficient_scope_error,
)

logger = logging.getLogger(__name__)


def lola_access_error(request, required_scope, url_pk):
    """
    Evaluate the LOLA access gate for an actor-scoped request.

    Returns the error Response that should be sent, or None if access is allowed (no error -> None).

    Two-layer check, each regulated by a different condition:

    Layer 1 - Scope presence (controlled by `required_scope`):
        Strict endpoints (required_scope=True) MUST carry a token with
        the activitypub_account_portability scope. Returns 403 insufficient_scope otherwise.
        Dual-mode endpoints (required_scope=False) skip this layer so
        unauthenticated/public traffic falls through (returns None).

    Layer 2 - Actor binding enforcement (LOLA Section 5 MUST):
        Runs whenever a portability token is present (request.has_portability_scope),
        regardless of required_scope. The token MUST be bound to the Actor whose
        <pk> is in the URL, or the request is rejected with 403 actor_mismatch.

        Binding is persisted at token issuance by ActivityPubOAuth2Validator._save_bearer_token (the write side).
        This gate is the read/enforcement side. The check covers both OptionalOAuth2Authentication paths (Authorization header
        and the demo-only session token) because both set request.auth to the same AccessToken instance.

    Fail-closed: once a portability scope is claimed, access is allowed only if a
    binding can actually be verified. A missing URL pk, a missing token object, a
    missing binding row, or a binding to a different actor all return actor_mismatch.

    Args:
        request: DRF request; OptionalOAuth2Authentication has set
            request.has_portability_scope and request.auth.
        required_scope: True for strict endpoints, False for dual-mode endpoints.
        url_pk: the actor pk from the URL (the value the token must be bound to).

    Returns:
        Response on denial, or None when access is allowed.
    """
    has_scope = bool(getattr(request, "has_portability_scope", False))

    # Layer 1: scope presence (strict endpoints only)
    if required_scope and not has_scope:
        logger.warning("LOLA access denied: insufficient_scope for %s", request.path)
        return build_insufficient_scope_error(
            required_scope=LOLA_PORTABILITY_SCOPE,
            endpoint_path=request.path,
            request=request,
        )

    # No portability token: nothing to bind. Strict endpoints already returned above
    # dual-mode endpoints fall through to their public response.
    if not has_scope:
        return None

    # Layer 2: actor binding. Reached whenever a portability token is present, so dual-mode
    # endpoints cannot leak another actor's augmented data to a token bound to a different actor.
    if url_pk is None:
        # Fail closed. All LOLA actor-scoped endpoints carry <pk> in the URL, so this should not occur in normal operation.
        logger.warning(
            "LOLA access denied: actor binding check invoked without URL pk path=%s",
            request.path,
        )
        return build_actor_mismatch_error(request=request)

    token = getattr(request, "auth", None)
    if token is None:
        # In normal flows has_portability_scope is derived from the token, so this state should not occur;
        # if it does the binding is unverifiable -> fail closed rather than grant on an unverifiable claim.
        logger.warning(
            "LOLA access denied: portability scope claimed without a token object path=%s",
            request.path,
        )
        return build_actor_mismatch_error(request=request)

    error = _check_actor_binding(request, token, url_pk)
    if error is not None:
        return error

    logger.info(
        "LOLA access granted: scope=%s endpoint=%s actor_pk=%s",
        LOLA_PORTABILITY_SCOPE,
        request.path,
        url_pk,
    )
    return None


def _check_actor_binding(request, token, url_pk):
    """
    Compare the token's bound Actor against the actor pk in the URL.

    Returns an actor_mismatch Response on a missing binding row or a binding to a
    different actor, or None when the binding is valid.

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
            "LOLA access denied: portability token has no actor_binding token_id=%s path=%s",
            getattr(token, "pk", None),
            request.path,
        )
        return build_actor_mismatch_error(request=request)

    if binding.actor_id != int(url_pk):
        logger.warning(
            "LOLA access denied: actor_mismatch token_id=%s bound_actor_id=%s "
            "requested_pk=%s path=%s",
            getattr(token, "pk", None),
            binding.actor_id,
            url_pk,
            request.path,
        )
        return build_actor_mismatch_error(request=request)

    return None


def _apply_lola_gate(view_func, required_scope):
    """
    Wrap `view_func` so lola_access_error runs before it, short-circuiting with the error Response on denial.
    Shared implementation behind lola_scope_required (required_scope=True) and lola_scope_optional (required_scope=False).
    The actor pk is read from the view's URL kwargs.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        error = lola_access_error(request, required_scope, kwargs.get("pk"))
        if error is not None:
            return error
        return view_func(request, *args, **kwargs)

    return wrapper


def lola_scope_required(view_func):
    """
    Strict LOLA gate. The activitypub_account_portability scope is REQUIRED (no token -> 403 insufficient_scope),
    and any token present MUST be bound to the URL actor (else 403 actor_mismatch).
    Use on endpoints that expose only scope-gated data (followers, content, liked, blocked).
    """
    return _apply_lola_gate(view_func, required_scope=True)


def lola_scope_optional(view_func):
    """
    Dual-mode LOLA gate. Public access is allowed (no token -> public response), but any portability token present
    MUST be bound to the URL actor (else 403 actor_mismatch).
    Use on endpoints that serve public traffic and augment it for the bound actor (actor-detail, outbox, following).
    """
    return _apply_lola_gate(view_func, required_scope=False)


def actor_required(view_func):
    """
    Resolve the Actor named by the URL <pk> and inject it into the view as the
    `actor` keyword argument; return 404 actor_not_found if no such actor exists.

    Stack this ABOVE the LOLA gate decorators (lola_scope_required / lola_scope_optional) so the existence check (404)
    runs before the auth check (403), preserving each endpoint's 404-before-403 precedence.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        pk = kwargs.get("pk")
        try:
            actor = Actor.objects.get(pk=pk)
        except Actor.DoesNotExist:
            return build_actor_not_found_error(pk, request)
        kwargs["actor"] = actor
        return view_func(request, *args, **kwargs)

    return wrapper


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
