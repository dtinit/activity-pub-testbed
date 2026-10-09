from rest_framework.exceptions import NotFound, PermissionDenied

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

