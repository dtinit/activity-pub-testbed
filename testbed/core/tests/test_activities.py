import pytest
from django.core.exceptions import ValidationError
from testbed.core.models import Actor, CreateActivity, LikeActivity, FollowActivity
from testbed.core.factories import (
    ActorFactory,
    NoteFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
)

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

# Test activities maintain proper temporal ordering
@pytest.mark.django_db
def test_activity_timestamp_ordering(actor):
    # Create a note for the activities
    note = NoteFactory(actor=actor)
    target_actor = actor  # Use the same actor as target to avoid uniqueness issues
    
    # Create activities using the existing actor
    activities = [
        CreateActivityFactory(actor=actor, note=note),
        LikeActivityFactory(actor=actor, note=note),
        FollowActivityFactory(actor=actor, target_actor=target_actor)
    ]
    
    # Verify timestamps exist and are ordered
    timestamps = [activity.timestamp for activity in activities]
    assert all(timestamps)
    assert sorted(timestamps) == timestamps