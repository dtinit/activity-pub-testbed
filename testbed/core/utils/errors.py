import uuid
from datetime import timezone, datetime
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from ..oauth.scopes import LOLA_PORTABILITY_SCOPE

"""
LOLA API errors as DRF exceptions. Views raise them; views.decorators.lola_exception_handler turns each
into its error response, so every LOLA error has one shape and one place it is built.
"""

class LolaError:
    """
    Mixed into every LOLA API exception. The remediation its error body can add to the code and the sentence,
    and how the exception handler tells a LOLA error from one of DRF's own.
    """
    remediation = None


class ActorNotFound(LolaError, NotFound):
    default_code = "actor_not_found"
    default_detail = "No such actor"
    remediation = "Check available actors via the actors list endpoint or verify the ID"


class ObjectNotFound(LolaError, NotFound):
    default_code = "object_not_found"
    default_detail = "No such object"


class InsufficientScope(LolaError, PermissionDenied):
    default_code = "insufficient_scope"
    default_detail = f"This endpoint requires {LOLA_PORTABILITY_SCOPE} scope"
    remediation = f"Request OAuth token with '{LOLA_PORTABILITY_SCOPE}' scope"


class ActorMismatch(LolaError, PermissionDenied):
    default_code = "actor_mismatch"
    default_detail = "This token is not authorized for the requested actor"
    remediation = "Request a new OAuth token for the target actor"


def generate_request_id():
    """
    Generate unique request ID for debugging and support tracking.
    
    Returns:
        str: UUID4 string for unique request identification
    """
    return str(uuid.uuid4())


def build_error_response(error_code, detail, status_code, request=None, remediation=None):
    """
    Build standardized JSON error response.
    
    Creates consistent, developer-friendly error responses with comprehensive
    metadata for debugging, remediation, and support purposes.
    
    Args:
        error_code (str): Machine-readable error identifier, an exception's default_code
        detail (str): Human-readable error description
        status_code (int): HTTP status code for the response
        request (HttpRequest, optional): Django request object for context
        remediation (str, optional): Actionable steps to fix the error
    
    Returns:
        Response: Django REST framework Response with structured error JSON
    
    Example (as lola_exception_handler calls it):
        >>> build_error_response(
        ...     exc.get_codes(), str(exc.detail), exc.status_code,
        ...     request=request, remediation=exc.remediation,
        ... )
    """
    error_data = {
        "error_code": error_code,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    # Add optional context fields if provided
    if remediation:
        error_data["remediation"] = remediation
        
    if request:
        error_data["endpoint"] = request.path
        error_data["method"] = request.method
        # Generate request ID for this specific request
        error_data["request_id"] = generate_request_id()
    
    return Response(error_data, status=status_code)
