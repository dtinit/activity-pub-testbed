from django.urls import path
from testbed.core.views import (
    actor_detail,
    portability_outbox_detail,
    deactivate_account,
    oauth_authorization_server_metadata,
    following_collection,
    followers_collection,
)

urlpatterns = [
    # LOLA Discovery: RFC8414-compliant OAuth Authorization Server Metadata
    path(
        ".well-known/oauth-authorization-server/",
        oauth_authorization_server_metadata,
        name="oauth-server-metadata",
    ),
    # Actor Endpoint: Retrieve actor details and export LOLA-compliant data
    path("actors/<int:pk>/", actor_detail, name="actor-detail"),
    # Portability Outbox: Retrieve the outbox linked to the actor
    path(
        "actors/<int:pk>/outbox/",
        portability_outbox_detail,
        name="actor-outbox",
    ),
    # LOLA Following Collection: Public access, LOLA-gated discovery
    path(
        "actors/<int:pk>/following/",
        following_collection,
        name="following-collection",
    ),
    # LOLA Followers Collection: LOLA authentication required
    path(
        "actors/<int:pk>/followers/",
        followers_collection,
        name="followers-collection",
    ),
    # Deactivate Account: API endpoint for account deactivation
    path(
        "actors/<int:actor_id>/deactivate/",
        deactivate_account,
        name="deactivate-account",
    ),
]
