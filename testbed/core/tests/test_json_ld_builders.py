import pytest
from testbed.core.json_ld_builders import (
    build_actor_json_ld,
    build_note_json_ld,
    build_create_activity_json_ld,
    build_like_activity_json_ld,
    build_follow_activity_json_ld,
    build_outbox_json_ld
)
from testbed.core.json_ld_utils import (
    build_basic_context,
    build_actor_context,
    build_actor_id,
    build_note_id,
    build_activity_id,
    build_outbox_id
)
from testbed.core.factories import (
    LikeActivityFactory,
    FollowActivityFactory,
    CreateActivityFactory,
    NoteFactory
)

# Test building JSON-LD for a source actor
@pytest.mark.django_db
def test_build_actor_json_ld(source_actor):
    json_ld = build_actor_json_ld(source_actor)
    
    assert json_ld["@context"] == build_actor_context()
    assert json_ld["type"] == "Person"
    assert json_ld["id"] == build_actor_id(source_actor.id)
    assert json_ld["preferredUsername"] == source_actor.username
    assert json_ld["name"] == source_actor.username
    assert isinstance(json_ld["previously"], list)

# Test building JSON-LD for a note"
@pytest.mark.django_db
def test_build_note_json_ld(note):
    json_ld = build_note_json_ld(note)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Note"
    assert json_ld["id"] == build_note_id(note.id)
    assert json_ld["actor"] == build_actor_id(note.actor.id)
    assert json_ld["content"] == note.content
    assert json_ld["visibility"] == note.visibility

# Test building JSON-LD for note creation activity
@pytest.mark.django_db
def test_build_create_activity_json_ld_note(source_actor):
    note = NoteFactory(actor=source_actor)
    activity = CreateActivityFactory(actor=source_actor, note=note)
    json_ld = build_create_activity_json_ld(activity)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Create"
    assert json_ld["id"] == build_activity_id(activity.id)
    assert json_ld["actor"] == build_actor_id(source_actor.id)
    assert json_ld["object"]["type"] == "Note"
    assert json_ld["object"]["id"] == build_note_id(note.id)

# Test building JSON-LD for actor creation activity
@pytest.mark.django_db
def test_build_create_activity_json_ld_actor_creation(source_actor):
    activity = CreateActivityFactory.create_for_actor(source_actor)
    json_ld = build_create_activity_json_ld(activity)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Create"
    assert json_ld["id"] == build_activity_id(activity.id)
    assert json_ld["actor"] == build_actor_id(source_actor.id)
    assert json_ld["object"]["type"] == "Person"
    assert json_ld["object"]["id"] == build_actor_id(source_actor.id)

# Test building JSON-LD for local like activity
@pytest.mark.django_db
def test_build_like_activity_json_ld_local(source_actor):
    note = NoteFactory(actor=source_actor)
    activity = LikeActivityFactory(actor=source_actor, note=note)
    json_ld = build_like_activity_json_ld(activity)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Like"
    assert json_ld["id"] == build_activity_id(activity.id)
    assert json_ld["actor"] == build_actor_id(source_actor.id)
    assert json_ld["object"]["type"] == "Note"
    assert json_ld["object"]["id"] == build_note_id(note.id)

# Test building JSON-LD for remote like activity
@pytest.mark.django_db
def test_build_like_activity_json_ld_remote(source_actor):
    activity = LikeActivityFactory(
        actor=source_actor,
        note=None,
        object_url="https://remote.example/notes/123",
        object_data={"content": "Remote content"}
    )
    
    json_ld = build_like_activity_json_ld(activity)
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Like"
    assert json_ld["id"] == build_activity_id(activity.id)
    assert json_ld["actor"] == build_actor_id(source_actor.id)
    assert json_ld["object"]["id"] == "https://remote.example/notes/123"
    assert json_ld["object"]["content"] == "Remote content"

# Test building JSON-LD for local follow activity
@pytest.mark.django_db
def test_build_follow_activity_json_ld_local(source_actor, destination_actor):
    activity = FollowActivityFactory(
        actor=source_actor,
        target_actor=destination_actor
    )
    
    json_ld = build_follow_activity_json_ld(activity)
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Follow"
    assert json_ld["id"] == build_activity_id(activity.id)
    assert json_ld["actor"] == build_actor_id(source_actor.id)
    assert json_ld["object"]["type"] == "Person"
    assert json_ld["object"]["id"] == build_actor_id(destination_actor.id)

# Test building JSON-LD for remote follow activity
@pytest.mark.django_db
def test_build_follow_activity_json_ld_remote(source_actor):
    activity = FollowActivityFactory(
        actor=source_actor,
        target_actor=None,
        target_actor_url="https://remote.example/users/remote_user",
        target_actor_data={"preferredUsername": "remote_user"}
    )
    
    json_ld = build_follow_activity_json_ld(activity)
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Follow"
    assert json_ld["id"] == build_activity_id(activity.id)
    assert json_ld["actor"] == build_actor_id(source_actor.id)
    assert json_ld["object"]["id"] == "https://remote.example/users/remote_user"
    assert json_ld["object"]["preferredUsername"] == "remote_user"

# Test Outbox JSON-LD builder with multiple activities
@pytest.mark.django_db
def test_build_outbox_json_ld(outbox, create_activity, like_activity, follow_activity):
    # Add activities to outbox
    outbox.add_activity(create_activity)
    outbox.add_activity(like_activity)
    outbox.add_activity(follow_activity)
    
    json_ld = build_outbox_json_ld(outbox)
    
    # Check outbox structure
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "OrderedCollection"
    assert json_ld["id"] == build_outbox_id(outbox.actor.id)
    assert isinstance(json_ld["totalItems"], int)
    assert isinstance(json_ld["items"], list)
    
    # Verify each item has required fields
    for item in json_ld["items"]:
        assert "@context" in item
        assert "type" in item
        assert "id" in item
        assert "actor" in item
        assert "published" in item
        assert "visibility" in item
    
    # Verify activity types are present
    activity_types = {item["type"] for item in json_ld["items"]}
    assert "Create" in activity_types
    assert "Like" in activity_types
    assert "Follow" in activity_types
