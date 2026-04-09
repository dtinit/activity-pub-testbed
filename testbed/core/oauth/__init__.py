"""
OAuth package — all OAuth, authentication, and authorization components for LOLA.

Submodules:
    authentication  -- OptionalOAuth2Authentication (dual-mode: public + LOLA)
    forms           -- OAuthApplicationForm (OAuth app settings UI form)
    utils           -- State params, token sessions, client credential management
    validators      -- ActivityPubOAuth2Validator (scope + redirect validation)

Public symbols are re-exported here so that the rest of the project can import
them via ``from testbed.core.oauth import <name>``.  When adding a new public
symbol, add it to the appropriate submodule AND to this file's imports and
``__all__`` list.
"""

from .authentication import OptionalOAuth2Authentication
from .forms import OAuthApplicationForm
from .utils import (
    clear_token_from_session,
    generate_secure_state,
    get_token_from_session,
    get_token_scope_from_session,
    get_user_application,
    store_state_in_session,
    store_token_in_session,
    validate_state_from_session,
)
from .validators import ActivityPubOAuth2Validator

__all__ = [
    "OptionalOAuth2Authentication",
    "OAuthApplicationForm",
    "ActivityPubOAuth2Validator",
    "clear_token_from_session",
    "generate_secure_state",
    "get_token_from_session",
    "get_token_scope_from_session",
    "get_user_application",
    "store_state_in_session",
    "store_token_in_session",
    "validate_state_from_session",
]
