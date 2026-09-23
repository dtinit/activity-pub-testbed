import pytest
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone
from testbed.core.models import Actor, CreateActivity, LikeActivity, FollowActivity
from testbed.core.factories import (
    ActorFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
)
from testbed.core.utils.actor_utils import create_remote_follow

# Test Create activity for note creation
@pytest.mark.django_db
def test_create_activity_with_note(actor, note):
    activity = CreateActivityFactory(actor=actor, note=note)
    
    assert activity.note == note
    assert activity.timestamp is not None
    assert str(activity) == f"Create by {actor.user.username}: {note}"

# Test Create activity for actor creation
@pytest.mark.django_db
def test_create_activity_for_actor(actor_create_activity):
    assert actor_create_activity.note is None
    assert actor_create_activity.timestamp is not None
    assert str(actor_create_activity) == f"Create by {actor_create_activity.actor.user.username}: Actor creation"

# Test Like activity for local note
@pytest.mark.django_db
def test_like_activity_local(actor, note):
    activity = LikeActivityFactory(actor=actor, note=note)
    
    assert activity.note == note
    assert activity.object_url is None
    assert activity.object_data is None
    assert str(activity) == f"Like by {actor.user.username}: {note}"

# Test Like activity for remote object
@pytest.mark.django_db
def test_like_activity_remote(actor):
    activity = LikeActivityFactory(
        actor=actor,
        note=None,
        object_url="https://remote.example/notes/123",
        object_data={"content": "Remote content"}
    )
    
    assert activity.note is None
    assert activity.object_url == "https://remote.example/notes/123"
    assert "content" in activity.object_data
    assert str(activity) == f"Like by {actor.user.username}: Remote content..."

# Test Like activity validation rules
@pytest.mark.django_db
def test_like_activity_validation(actor):
    with pytest.raises(ValidationError):
        # Neither local note nor remote object
        LikeActivityFactory(
            actor=actor,
            note=None,
            object_url=None,
            object_data=None
        ).clean()

# Test Follow activity for local actor
@pytest.mark.django_db
def test_follow_activity_local(actor, other_actor):
    activity = FollowActivityFactory(
        actor=actor,
        target_actor=other_actor
    )
    
    assert activity.target_actor == other_actor
    assert activity.target_actor_url is None
    assert activity.target_actor_data is None
    assert str(activity) == f"Follow by {actor.user.username}: {other_actor.user.username}"

# Test Follow activity for remote actor
@pytest.mark.django_db
def test_follow_activity_remote(actor):
    activity = FollowActivityFactory(
        actor=actor,
        target_actor=None,
        target_actor_url="https://remote.example/users/remote_user",
        target_actor_data={"preferredUsername": "remote_user"}
    )
    
    assert activity.target_actor is None
    assert activity.target_actor_url == "https://remote.example/users/remote_user"
    assert "preferredUsername" in activity.target_actor_data
    assert str(activity) == f"Follow by {actor.user.username}: remote_user (remote)"

# Test Follow activity validation rules
@pytest.mark.django_db
def test_follow_activity_validation(actor):
    with pytest.raises(ValidationError):
        # Neither local target nor remote actor
        FollowActivityFactory(
            actor=actor,
            target_actor=None,
            target_actor_url=None,
            target_actor_data=None
        ).clean()

# Test activities are properly added to outbox
@pytest.mark.django_db
def test_activity_outbox_integration(outbox, create_activity, like_activity, follow_activity):
    # Get initial counts before adding activities
    initial_create_count = outbox.activities_create.count()
    initial_like_count = outbox.activities_like.count()
    initial_follow_count = outbox.activities_follow.count()

    # Add to outbox
    outbox.add_activity(create_activity)
    outbox.add_activity(like_activity)
    outbox.add_activity(follow_activity)

    # Verify counts have increased by 1
    assert outbox.activities_create.count() == initial_create_count + 1
    assert outbox.activities_like.count() == initial_like_count + 1
    assert outbox.activities_follow.count() == initial_follow_count + 1

    # Verify activity presence
    assert create_activity in outbox.activities_create.all()
    assert like_activity in outbox.activities_like.all()
    assert follow_activity in outbox.activities_follow.all()

# Ordering follows the stored timestamp, not insertion order - build_outbox_json_ld sorts on it
@pytest.mark.django_db
def test_activity_timestamp_ordering(actor, other_actor, note):
    base = timezone.now() - timedelta(days=30)

    # Created newest first, so insertion order is the reverse of chronological order
    newest = CreateActivityFactory(actor=actor, note=note, timestamp=base + timedelta(days=2))
    oldest = LikeActivityFactory(actor=actor, note=note, timestamp=base)
    middle = FollowActivityFactory(actor=actor, target_actor=other_actor, timestamp=base + timedelta(days=1))

    for activity in (newest, oldest, middle):
        activity.refresh_from_db()

    assert sorted([newest, oldest, middle], key=lambda a: a.timestamp) == [oldest, middle, newest]

# Test that a supplied timestamp survives to the database, so a copied activity can keep its original date (LOLA §7.1.7)

# Create and Like are parametrised together because both take `note` and both are copied with
# their original date (§7.1.7, and §6.5 for the liked collection).

# FollowActivity is not included because §3.3.1 says a new Follow must NOT carry history, and that rule gets its own
# test below, against the real creation path rather than a factory.
@pytest.mark.django_db
@pytest.mark.parametrize("activity_factory", [CreateActivityFactory, LikeActivityFactory])
def test_activity_timestamp_is_settable(actor, note, activity_factory):
    original = timezone.now() - timedelta(days=400)

    activity = activity_factory(actor=actor, note=note, timestamp=original)
    activity.refresh_from_db()

    assert activity.timestamp == original

@pytest.mark.django_db
def test_activity_defaults_are_safe(actor, note):
    before = timezone.now()
    activity = CreateActivityFactory(actor=actor, note=note)
    after = timezone.now()

    activity.refresh_from_db()
    assert before <= activity.timestamp <= after
    assert activity.previously == []

# Test that breadcrumbs survive the database round trip in the shape §7.1.8 defines: {actor, id}.
@pytest.mark.django_db
def test_activity_previously_round_trip(actor, note):
    breadcrumbs = [
        {"actor": "https://mistywing.example/cherry", "id": "https://mistywing.example/like/228"},
    ]

    activity = LikeActivityFactory(actor=actor, note=note, previously=breadcrumbs)
    activity.refresh_from_db()

    assert activity.previously == breadcrumbs

# LOLA §3.3.1: "New Follow activities from the new Actor are optional and not linked to old Follow activities.
# New Follow activities should not have older timestamps or breadcrumbs."
@pytest.mark.django_db
def test_new_follow_carries_no_history(actor):
    before = timezone.now()
    follow = create_remote_follow(actor)
    after = timezone.now()

    follow.refresh_from_db()
    assert before <= follow.timestamp <= after
    assert follow.previously == []