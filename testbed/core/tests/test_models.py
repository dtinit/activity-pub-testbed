import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from testbed.core.models import Actor, Note
from testbed.core.factories import (
    UserFactory,
    ActorFactory,
    NoteFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
)

# Actor Tests
def test_actor_creation(actor):
    assert actor.user is not None
    assert actor.role in [Actor.ROLE_SOURCE, Actor.ROLE_DESTINATION]

def test_actor_str_representation(actor):
    assert str(actor) == f"{actor.user.username}'s {actor.role} actor"

def test_actor_roles():
    source_actor = ActorFactory(role=Actor.ROLE_SOURCE)
    dest_actor = ActorFactory(role=Actor.ROLE_DESTINATION)
    
    assert source_actor.is_source
    assert dest_actor.is_destination
    assert not source_actor.is_destination
    assert not dest_actor.is_source

# Fix for the unique role constraint test
def test_actor_unique_role_constraint():
    user = UserFactory()
    ActorFactory(user=user, role=Actor.ROLE_SOURCE)
    
    # Create the second actor but don't save it yet
    actor = ActorFactory.build(user=user, role=Actor.ROLE_SOURCE)
    
    # Now the validation should raise the error
    with pytest.raises(ValidationError):
        actor.clean()

def test_actor_move_history():
    actor = ActorFactory()
    test_date = timezone.now()
    
    actor.record_move("old-server.com", "old_username", test_date)
    assert len(actor.previously) == 1
    assert actor.previously[0]["type"] == "Move"
    assert actor.previously[0]["object"] == "https://old-server.com/users/old_username"
    assert actor.previously[0]["published"] == test_date.isoformat()

def test_actor_json_ld():
    actor = ActorFactory()
    json_ld = actor.get_json_ld()
    
    assert json_ld["@context"]
    assert json_ld["type"] == "Person"
    assert json_ld["id"] == f"https://example.com/actors/{actor.id}"
    assert json_ld["preferredUsername"] == actor.username
    assert json_ld["name"] == actor.username
    assert isinstance(json_ld["previously"], list)

# Note Tests
def test_note_creation(note):
    assert note.content is not None
    assert note.actor is not None
    assert note.visibility in ["public", "private", "followers-only"]

def test_note_str_representation(note):
    expected = f"Note by {note.actor.user.username}: {note.content[:30]}"
    assert str(note) == expected

def test_note_json_ld(note):
    json_ld = note.get_json_ld()
    
    assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["type"] == "Note"
    assert json_ld["content"] == note.content
    assert json_ld["visibility"] == note.visibility

# Activity Tests
def test_create_activity_str(create_activity):
    if create_activity.note:
        expected = f"Create by {create_activity.actor.user.username}: {create_activity.note}"
    else:
        expected = f"Create by {create_activity.actor.user.username}: Actor creation"
    assert str(create_activity) == expected

def test_like_activity_validation():
    with pytest.raises(ValidationError):
        activity = LikeActivityFactory(note=None, object_url=None)
        activity.clean()  # Need to call clean explicitly

def test_like_activity_remote_object():
    activity = LikeActivityFactory(
        note=None,
        object_url="https://remote.example/notes/123",
        object_data={"content": "Remote note content"}
    )
    json_ld = activity.get_json_ld()
    
    assert json_ld["object"]["id"] == "https://remote.example/notes/123"
    assert json_ld["object"]["content"] == "Remote note content"

def test_follow_activity_validation():
    with pytest.raises(ValidationError):
        activity = FollowActivityFactory(target_actor=None, target_actor_url=None)
        activity.clean()  # Need to call clean explicitly

def test_follow_activity_remote_actor():
    activity = FollowActivityFactory(
        target_actor=None,
        target_actor_url="https://remote.example/users/remote_user",
        target_actor_data={"preferredUsername": "remote_user"}
    )
    json_ld = activity.get_json_ld()
    
    assert json_ld["object"]["id"] == "https://remote.example/users/remote_user"
    assert json_ld["object"]["preferredUsername"] == "remote_user"

# Outbox Tests
def test_portability_outbox_creation(actor):
    outbox = actor.portability_outbox
    assert outbox is not None
    assert outbox.activities_create.count() == 1  # Initial Create activity
    assert outbox.activities_create.first().note is None  # Should be an Actor creation activity

def test_outbox_activity_types():
    # Create a source actor explicitly
    actor = ActorFactory(role=Actor.ROLE_SOURCE)
    
    # Initialize the outbox (this should happen automatically in save())
    actor.initialize_if_source()
    
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