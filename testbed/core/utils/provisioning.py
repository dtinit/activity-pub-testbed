# Test content for one source actor. Signup signal calls it for each new source actor (including prod, where seed is disabled)

import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from testbed.core.models import (
    Blocked,
    CreateActivity,
    FollowActivity,
    Followers,
    Following,
    LikeActivity,
    Note,
)

logger = logging.getLogger(__name__)

REMOTE_SERVERS = ("mastodon.example", "pixelfed.example", "pleroma.example")

NOTE_COUNT = 30
NOTE_INTERVAL = timedelta(days=4)
VISIBILITIES = ("public", "followers-only", "private")
LIKE_COUNT = 6
FOLLOWING_COUNT = 6
FOLLOWERS_COUNT = 8
BLOCKED_COUNT = 2

def _remote_actors(kind, count):
    # Fictional remote Persons named for the collection they appear in, no two collections share one
    actors = []
    for number in range(1, count + 1):
        server = REMOTE_SERVERS[number % len(REMOTE_SERVERS)]
        username = f"{kind}_{number}"
        url = f"https://{server}/users/{username}"
        actors.append((url, {
            "type": "Person",
            "id": url,
            "preferredUsername": username,
            "name": username.replace("_", " ").title(),
            "inbox": f"{url}/inbox",
        }))
    return actors


@transaction.atomic
def provision_actor_content(actor):
    now = timezone.now()
    outbox = actor.portability_outbox

    replaced = sum(
        queryset.delete()[0]
        for queryset in (
            actor.notes.all(),
            LikeActivity.objects.filter(actor=actor, note__isnull=True),
            FollowActivity.objects.filter(actor=actor, target_actor__isnull=True),
            Following.objects.filter(actor=actor, target_actor__isnull=True),
            Followers.objects.filter(actor=actor, follower_actor__isnull=True),
            Blocked.objects.filter(actor=actor, blocked_actor__isnull=True),
        )
    )

    notes = []
    for i in range(NOTE_COUNT):
        visibility = VISIBILITIES[i % len(VISIBILITIES)]
        notes.append(Note(
            actor=actor,
            content=f"Provisioned note {i + 1} of {NOTE_COUNT} ({visibility})",
            published=now - i * NOTE_INTERVAL,
            visibility=visibility,
        ))
    notes = Note.objects.bulk_create(notes)
    outbox.activities_create.add(*CreateActivity.objects.bulk_create(
        CreateActivity(actor=actor, note=note, timestamp=note.published, visibility=note.visibility)
        for note in notes
    ))

    likes = []
    for number, (author_url, author) in enumerate(_remote_actors("author", LIKE_COUNT), start=1):
        liked_at = now - number * NOTE_INTERVAL
        likes.append(LikeActivity(
            actor=actor,
            timestamp=liked_at,
            visibility="public",
            object_url=f"{author_url}/notes/{number}",
            object_data={
                "type": "Note",
                "attributedTo": author_url,
                "content": f"A remote note by {author['preferredUsername']}",
                "published": (liked_at - timedelta(days=1)).isoformat(),
            },
        ))
    outbox.activities_like.add(*LikeActivity.objects.bulk_create(likes))

    # Each remote follow is both current state (Following) and history (a Follow in the outbox)
    following = _remote_actors("followed", FOLLOWING_COUNT)
    Following.objects.bulk_create(
        Following(actor=actor, target_actor_url=url, target_actor_data=data) for url, data in following
    )
    outbox.activities_follow.add(*FollowActivity.objects.bulk_create(
        FollowActivity(actor=actor, target_actor_url=url, target_actor_data=data) for url, data in following
    ))

    Followers.objects.bulk_create(
        Followers(actor=actor, follower_actor_url=url, follower_actor_data=data)
        for url, data in _remote_actors("follower", FOLLOWERS_COUNT)
    )
    Blocked.objects.bulk_create(
        Blocked(actor=actor, blocked_actor_url=url, blocked_actor_data=data)
        for url, data in _remote_actors("blocked", BLOCKED_COUNT)
    )

    logger.info("Provisioned actor %s, replacing %s earlier rows", actor.pk, replaced)
