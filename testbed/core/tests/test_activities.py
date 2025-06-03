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
def test_create_activity_with_note(source_actor):
    note = NoteFactory(actor=source_actor)
    activity = CreateActivityFactory(actor=source_actor, note=note)
    
    assert activity.actor.is_source
    assert activity.note == note
    assert activity.timestamp is not None
    assert str(activity) == f"Create by {source_actor.user.username}: {note}"

# Test Create activity for actor creation
@pytest.mark.django_db
def test_create_activity_for_actor(source_actor):
    activity = CreateActivityFactory.create_for_actor(source_actor)
    
    assert activity.actor.is_source
    assert activity.note is None
    assert activity.timestamp is not None
    assert str(activity) == f"Create by {source_actor.user.username}: Actor creation"

# Test Like activity for local note
@pytest.mark.django_db
def test_like_activity_local(source_actor):
    note = NoteFactory(actor=source_actor)
    activity = LikeActivityFactory(actor=source_actor, note=note)
    
    assert activity.actor.is_source
    assert activity.note == note
    assert activity.object_url is None
    assert activity.object_data is None
    assert str(activity) == f"Like by {source_actor.user.username}: {note}"

# Test Like activity for remote object
@pytest.mark.django_db
def test_like_activity_remote(source_actor):
    activity = LikeActivityFactory(
        actor=source_actor,
        note=None,
        object_url="https://remote.example/notes/123",
        object_data={"content": "Remote content"}
    )
    
    assert activity.actor.is_source
    assert activity.note is None
    assert activity.object_url == "https://remote.example/notes/123"
    assert "content" in activity.object_data
    assert str(activity) == f"Like by {source_actor.user.username}: Remote content..."

# Test Like activity validation rules
@pytest.mark.django_db
def test_like_activity_validation():
    source_actor = ActorFactory.create_source_actor()
    
    with pytest.raises(ValidationError):
        # Neither local note nor remote object
        LikeActivityFactory(
            actor=source_actor,
            note=None,
            object_url=None,
            object_data=None
        ).clean()

# Test Follow activity for local actor
@pytest.mark.django_db
def test_follow_activity_local(source_actor, destination_actor):
    activity = FollowActivityFactory(
        actor=source_actor,
        target_actor=destination_actor
    )
    
    assert activity.actor.is_source
    assert activity.target_actor.is_destination
    assert activity.target_actor_url is None
    assert activity.target_actor_data is None
    assert str(activity) == f"Follow by {source_actor.user.username}: {destination_actor.user.username}"

# Test Follow activity for remote actor
@pytest.mark.django_db
def test_follow_activity_remote(source_actor):
    activity = FollowActivityFactory(
        actor=source_actor,
        target_actor=None,
        target_actor_url="https://remote.example/users/remote_user",
        target_actor_data={"preferredUsername": "remote_user"}
    )
    
    assert activity.actor.is_source
    assert activity.target_actor is None
    assert activity.target_actor_url == "https://remote.example/users/remote_user"
    assert "preferredUsername" in activity.target_actor_data
    assert str(activity) == f"Follow by {source_actor.user.username}: remote_user (remote)"

# Test Follow activity validation rules
@pytest.mark.django_db
def test_follow_activity_validation():
    source_actor = ActorFactory.create_source_actor()
    
    with pytest.raises(ValidationError):
        # Neither local target nor remote actor
        FollowActivityFactory(
            actor=source_actor,
            target_actor=None,
            target_actor_url=None,
            target_actor_data=None
        ).clean()

# General Activity Tests
# Test activities are properly added to outbox
@pytest.mark.django_db
def test_activity_outbox_integration(source_actor):
    outbox = source_actor.portability_outbox
    initial_count = outbox.activities_create.count()

    # Create different types of activities
    create_activity = CreateActivityFactory(actor=source_actor)
    like_activity = LikeActivityFactory(actor=source_actor)
    follow_activity = FollowActivityFactory(actor=source_actor)

    # Add to outbox
    outbox.add_activity(create_activity)
    outbox.add_activity(like_activity)
    outbox.add_activity(follow_activity)

    # Verify counts
    assert outbox.activities_create.count() == initial_count + 1
    assert outbox.activities_like.count() == 1
    assert outbox.activities_follow.count() == 1

    # Verify activity presence
    assert create_activity in outbox.activities_create.all()
    assert like_activity in outbox.activities_like.all()
    assert follow_activity in outbox.activities_follow.all()

# Test activities maintain proper temporal ordering
@pytest.mark.django_db
def test_activity_timestamp_ordering(source_actor):
    activities = [
        CreateActivityFactory(actor=source_actor),
        LikeActivityFactory(actor=source_actor),
        FollowActivityFactory(actor=source_actor)
    ]
    
    # Verify timestamps exist and are ordered
    timestamps = [activity.timestamp for activity in activities]
    assert all(timestamps)
    assert sorted(timestamps) == timestamps