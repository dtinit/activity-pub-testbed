from django.urls import path
from testbed.core.views import (
    actor_detail,
    portability_outbox_detail,
    deactivate_account,
    oauth_authorization_server_metadata,
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
    # Deactivate Account: API endpoint for account deactivation
    path(
        "actors/<int:actor_id>/deactivate/",
        deactivate_account,
        name="deactivate-account",
    ),
]
