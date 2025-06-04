import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from testbed.core.models import Actor
from testbed.core.factories import (
    UserFactory,
    ActorFactory,
    NoteFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
)

# Test basic actor creation
def test_actor_creation(source_actor):
    assert source_actor.user is not None
    assert source_actor.role == Actor.ROLE_SOURCE

# Test actor string representation
def test_actor_str_representation(source_actor):
    assert str(source_actor) == f"{source_actor.user.username}'s {source_actor.role} actor"

# Test actor role properties
def test_actor_roles():
    source_actor = ActorFactory.create_source_actor()
    dest_actor = ActorFactory.create_destination_actor()
    
    assert source_actor.is_source
    assert dest_actor.is_destination
    assert not source_actor.is_destination
    assert not dest_actor.is_source

# Test that a user cannot have multiple actors with the same role
def test_actor_unique_role_constraint():
    user = UserFactory(with_actors=False)
    ActorFactory(user=user, role=Actor.ROLE_SOURCE)
    
    actor = ActorFactory.build(user=user, role=Actor.ROLE_SOURCE)
    
    with pytest.raises(ValidationError):
        actor.clean()

# Test recording actor movement history
def test_actor_move_history():
    actor = ActorFactory.create_source_actor()
    test_date = timezone.now()
    
    actor.record_move("old-server.com", "old_username", test_date)
    assert len(actor.previously) == 1
    assert actor.previously[0]["type"] == "Move"
    assert actor.previously[0]["object"] == "https://old-server.com/users/old_username"
    assert actor.previously[0]["published"] == test_date.isoformat()

# Test basic note creation
def test_note_creation(note):
    assert note.content is not None
    assert note.actor.is_source  # Notes can only be created by source actors
    assert note.visibility in ["public", "private", "followers-only"]

# Test note string representation
def test_note_str_representation(note):
    expected = f"Note by {note.actor.user.username}: {note.content[:30]}"
    assert str(note) == expected

# Test string representation of Create activity with note
def test_create_activity_str_with_note(create_activity):
    expected = f"Create by {create_activity.actor.user.username}: {create_activity.note}"
    assert str(create_activity) == expected

# Test string representation of Create activity for actor creation
def test_create_activity_str_for_actor_creation(actor_create_activity):
    expected = f"Create by {actor_create_activity.actor.user.username}: Actor creation"
    assert str(actor_create_activity) == expected

# Test that Like activity requires either note or remote object data
def test_like_activity_validation():
    with pytest.raises(ValidationError):
        activity = LikeActivityFactory(note=None, object_url=None)
        activity.clean()

# Test Like activity with remote object data
def test_like_activity_remote_object_validation():
    activity = LikeActivityFactory(
        note=None,
        object_url="https://remote.example/notes/123",
        object_data={"content": "Remote note content"}
    )
    assert activity.object_url == "https://remote.example/notes/123"
    assert activity.object_data["content"] == "Remote note content"

# Test that Follow activity requires either target_actor or remote actor data
def test_follow_activity_validation():
    with pytest.raises(ValidationError):
        activity = FollowActivityFactory(target_actor=None, target_actor_url=None)
        activity.clean()

# Test Follow activity with remote actor data
def test_follow_activity_remote_actor_validation():
    activity = FollowActivityFactory(
        target_actor=None,
        target_actor_url="https://remote.example/users/remote_user",
        target_actor_data={"preferredUsername": "remote_user"}
    )
    assert activity.target_actor_url == "https://remote.example/users/remote_user"
    assert activity.target_actor_data["preferredUsername"] == "remote_user"

# Test outbox is created automatically for source actors
def test_portability_outbox_creation(source_actor):
    outbox = source_actor.portability_outbox
    assert outbox is not None
    assert outbox.activities_create.count() == 1  # Initial Create activity
    assert outbox.activities_create.first().note is None  # Should be an Actor creation activity

# Test adding different types of activities to outbox
def test_outbox_activity_types():
    actor = ActorFactory.create_source_actor()
    outbox = actor.portability_outbox
    initial_count = outbox.activities_create.count()

    # Add different types of activities
    create_activity = CreateActivityFactory(actor=actor)
    like_activity = LikeActivityFactory(actor=actor)
    follow_activity = FollowActivityFactory(actor=actor)

    outbox.add_activity(create_activity)
    outbox.add_activity(like_activity)
    outbox.add_activity(follow_activity)

    assert outbox.activities_create.count() == initial_count + 1
    assert outbox.activities_like.count() == 1
    assert outbox.activities_follow.count() == 1

# Test adding multiple activities to outbox
def test_outbox_activity_addition():
    actor = ActorFactory.create_source_actor()
    outbox = actor.portability_outbox
    
    activities = [
        CreateActivityFactory(actor=actor),
        LikeActivityFactory(actor=actor),
        FollowActivityFactory(actor=actor)
    ]
    
    for activity in activities:
        outbox.add_activity(activity)
        
    assert activity in outbox.activities_follow.all() or \
           activity in outbox.activities_like.all() or \
           activity in outbox.activities_create.all()