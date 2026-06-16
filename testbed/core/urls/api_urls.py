from django.urls import path
from testbed.core.views import (
    actor_detail,
    portability_outbox_detail,
    following_collection,
    followers_collection,
    content_collection,
    liked_collection,
    blocked_collection,
)

urlpatterns = [
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
    # LOLA Content Collection: Raw authored objects, LOLA authentication required
    path(
        "actors/<int:pk>/content/",
        content_collection,
        name="content-collection",
    ),
    # LOLA Liked Collection: Interaction history with migration metadata, LOLA authentication required
    path(
        "actors/<int:pk>/liked/",
        liked_collection,
        name="liked-collection",
    ),
    # LOLA Blocked Collection: User safety data (block list), LOLA authentication required, FEP-c648 compliant
    path(
        "actors/<int:pk>/blocked/",
        blocked_collection,
        name="blocked-collection",
    ),
    # Dedicated LOLA migration collection routes. These are the URLs advertised under the Actor `migration` object.
    # Each route delegates to the existing collection view so the advertised URL is real and resolves.
    # The behavioral update of the migration surface (migration-outbox activity filtering, pagination, and
    # the public-vs-migration following/blocked gating decisions) is upcoming work and is intentionally not done here.
    path(
        "actors/<int:pk>/migration/outbox/",
        portability_outbox_detail,
        name="migration-outbox",
    ),
    path(
        "actors/<int:pk>/migration/content/",
        content_collection,
        name="migration-content",
    ),
    path(
        "actors/<int:pk>/migration/following/",
        following_collection,
        name="migration-following",
    ),
    path(
        "actors/<int:pk>/migration/blocked/",
        blocked_collection,
        name="migration-blocked",
    ),
]
