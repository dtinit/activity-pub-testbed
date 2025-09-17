import uuid
from datetime import timezone, datetime
from rest_framework.response import Response

"""
Provides standardized error response building and error code definitions
for consistent, developer-friendly error handling across all LOLA endpoints.
"""

class ErrorCodes:
    """
    Comprehensive error code categorizing for LOLA endpoints.
    
    Provides machine-readable error identifiers categorized by HTTP status codes
    and functional areas to enable consistent error handling across endpoints.
    """
    
    # Authentication & Authorization Errors (4xx)
    INSUFFICIENT_SCOPE = "insufficient_scope"
    ACTOR_NOT_FOUND = "actor_not_found" 
    FORBIDDEN_ACCESS = "forbidden_access"
    UNAUTHORIZED = "unauthorized"
    
    # Rate Limiting Errors (429)
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    
    # Trust Policy Errors (Still in consideration)
    # UNTRUSTED_SERVER = "untrusted_server"
    # PUBLIC_ONLY_MODE = "public_only_mode_enabled"
    
    # Validation Errors (400) 
    INVALID_PARAMETERS = "invalid_parameters"
    MALFORMED_REQUEST = "malformed_request"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    
    # Server Errors (5xx)
    INTERNAL_ERROR = "internal_server_error"
    SERVICE_UNAVAILABLE = "service_unavailable"


def generate_request_id():
    """
    Generate unique request ID for debugging and support tracking.
    
    Returns:
        str: UUID4 string for unique request identification
    """
    return str(uuid.uuid4())


def build_error_response(error_code, detail, status_code, request=None, hint=None, remediation=None):
    """
    Build standardized JSON error response.
    
    Creates consistent, developer-friendly error responses with comprehensive
    metadata for debugging, remediation, and support purposes.
    
    Args:
        error_code (str): Machine-readable error identifier from ErrorCodes
        detail (str): Human-readable error description
        status_code (int): HTTP status code for the response
        request (HttpRequest, optional): Django request object for context
        hint (str, optional): Additional context or explanation
        remediation (str, optional): Actionable steps to fix the error
    
    Returns:
        Response: Django REST framework Response with structured error JSON
    
    Example:
        >>> build_error_response(
        ...     ErrorCodes.INSUFFICIENT_SCOPE,
        ...     "This endpoint requires activitypub_account_portability scope",
        ...     403,
        ...     request=request,
        ...     hint="LOLA portability endpoints require specific OAuth scope",
        ...     remediation="Request OAuth token with 'activitypub_account_portability' scope"
        ... )
    """
    error_data = {
        "error_code": error_code,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    # Add optional context fields if provided
    if hint:
        error_data["hint"] = hint
    
    if remediation:
        error_data["remediation"] = remediation
        
    if request:
        error_data["endpoint"] = request.path
        error_data["method"] = request.method
        # Generate request ID for this specific request
        error_data["request_id"] = generate_request_id()
    
    return Response(error_data, status=status_code)


def build_actor_not_found_error(actor_id, request=None):
    """
    Build standardized 404 error for missing actors.
    
    Args:
        actor_id (int): The actor ID that was not found
        request (HttpRequest, optional): Django request object for context
    
    Returns:
        Response: 404 error response with actor-specific context
    """
    return build_error_response(
        error_code=ErrorCodes.ACTOR_NOT_FOUND,
        detail=f"Actor with ID {actor_id} does not exist",
        status_code=404,
        request=request,
        hint="Verify the actor ID is correct and the actor exists in the system",
        remediation="Check available actors via the actors list endpoint or verify the ID"
    )


def build_insufficient_scope_error(required_scope, endpoint_path, request=None):
    """
    Build standardized 403 error for insufficient OAuth scope.
    
    Args:
        required_scope (str): The OAuth scope required for access
        endpoint_path (str): The endpoint path that requires the scope
        request (HttpRequest, optional): Django request object for context
    
    Returns:
        Response: 403 error response with scope-specific context
    """
    return build_error_response(
        error_code=ErrorCodes.INSUFFICIENT_SCOPE,
        detail=f"This endpoint requires {required_scope} scope",
        status_code=403,
        request=request,
        hint="LOLA portability endpoints require specific OAuth scope for data access",
        remediation=f"Request OAuth token with '{required_scope}' scope to access {endpoint_path}"
    )


def build_rate_limit_error(retry_after_seconds, request=None):
    """
    Build standardized 429 error for rate limiting with Retry-After header.
    
    Args:
        retry_after_seconds (int): Seconds to wait before retrying
        request (HttpRequest, optional): Django request object for context
    
    Returns:
        Response: 429 error response with rate limit context
    """
    response = build_error_response(
        error_code=ErrorCodes.RATE_LIMIT_EXCEEDED,
        detail="Request rate limit exceeded",
        status_code=429,
        request=request,
        hint=f"Too many requests. Please wait {retry_after_seconds} seconds before retrying",
        remediation="Implement exponential backoff or reduce request frequency"
    )
    
    # Add standard Retry-After header for rate limiting
    response['Retry-After'] = str(retry_after_seconds)
    
    return response
