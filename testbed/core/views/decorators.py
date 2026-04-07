"""
Shared decorators and helpers for LOLA views.

- validate_lola_access: OAuth scope gate for LOLA-protected endpoints
- build_auth_context: standardized auth context dict passed to JSON-LD builders
- activitypub_content: sets ActivityPub content-type + CORS headers
"""

import logging
from functools import wraps

from ..utils.errors import build_insufficient_scope_error

logger = logging.getLogger(__name__)


def validate_lola_access(request, required_scope=True):
    """
    Scope gate for LOLA-protected endpoints.

    Args:
        request: HTTP request with OAuth authentication attributes set by OptionalOAuth2Authentication.
        required_scope: Whether the LOLA portability scope is required (default: True).

    Returns:
        dict: Validation result with 'valid' boolean and, on failure, 'error_response'.
    
     What each validation layer does:
        Layer 1: OAuth Scope Validation - Ensures proper LOLA scope
        Layer 2: Trust Settings Framework - Ready for TR1 trust controls
        Layer 3: Security Event Logging - Audit trail for monitoring
        Layer 4: Structured Error Responses - Consistent JSON error format
    """
    if required_scope and not getattr(request, "has_portability_scope", False):
        logger.warning(f"LOLA access denied: insufficient_scope for {request.path}")
        return {
            "valid": False,
            "error_response": build_insufficient_scope_error(
                required_scope="activitypub_account_portability",
                endpoint_path=request.path,
                request=request,
            ),
        }

    if required_scope and getattr(request, "has_portability_scope", False):
        logger.info(
            f"LOLA access granted: scope=activitypub_account_portability endpoint={request.path}"
        )

    return {"valid": True}


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
