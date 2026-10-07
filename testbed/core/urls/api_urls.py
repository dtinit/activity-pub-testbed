from django.urls import path
from testbed.core.views import (
    actor_detail,
    portability_outbox_detail,
    following_collection,
    followers_collection,
    content_collection,
    liked_collection,
    blocked_collection,
    note_detail,
    create_activity_detail,
    like_activity_detail,
    follow_activity_detail,
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
    # Note: the URL its `id` names, nested under the owning actor so a moved actor can still be found from it
    path(
        "actors/<int:pk>/notes/<int:object_pk>/",
        note_detail,
        name="note-detail",
    ),
    # Create activity
    path(
        "actors/<int:pk>/activities/create/<int:object_pk>/",
        create_activity_detail,
        name="create-activity-detail",
    ),
    # Like activity
    path(
        "actors/<int:pk>/activities/like/<int:object_pk>/",
        like_activity_detail,
        name="like-activity-detail",
    ),
    # Follow activity
    path(
        "actors/<int:pk>/activities/follow/<int:object_pk>/",
        follow_activity_detail,
        name="follow-activity-detail",
    ),
    # Dedicated LOLA migration collection routes. These are the URLs advertised under the Actor `migration` object.
    # Each route reuses the existing collection view. The migration outbox passes migration=True, which keeps
    # only the Creates of a Note (LOLA §6.2, §6.6.1).
    path(
        "actors/<int:pk>/migration/outbox/",
        portability_outbox_detail,
        {"migration": True},
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
