from .decorators import activitypub_content, build_auth_context, validate_lola_access

from .api import (
    actor_detail,
    blocked_collection,
    content_collection,
    followers_collection,
    following_collection,
    liked_collection,
    oauth_authorization_server_metadata,
    portability_outbox_detail,
)

from .pages import deactivate_account, index, report_activity, trigger_account

from .oauth_demo import (
    oauth_callback,
    test_authorization_view,
    test_error_view,
    test_token_exchange_view,
)

__all__ = [
    "validate_lola_access",
    "build_auth_context",
    "activitypub_content",
    "actor_detail",
    "portability_outbox_detail",
    "following_collection",
    "followers_collection",
    "content_collection",
    "liked_collection",
    "blocked_collection",
    "oauth_authorization_server_metadata",
    "deactivate_account",
    "trigger_account",
    "report_activity",
    "index",
    "oauth_callback",
    "test_authorization_view",
    "test_error_view",
    "test_token_exchange_view",
]