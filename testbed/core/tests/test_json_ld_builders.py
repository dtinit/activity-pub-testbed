import pytest
from testbed.core.factories import (
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory
)
from testbed.core.json_ld_builders import (
    build_actor_json_ld,
    build_note_json_ld,
    build_create_activity_json_ld,
    build_like_activity_json_ld,
    build_follow_activity_json_ld,
    build_outbox_json_ld,
)
from testbed.core.json_ld_utils import (
    build_actor_context,
    build_basic_context,
    build_actor_id,
    build_note_id,
    build_activity_id,
    build_outbox_id,
)

# Test Actor JSON-LD builder
def test_build_actor_json_ld(actor):
    json_ld = build_actor_json_ld(actor)
    
    assert json_ld["@context"] == build_actor_context()
    assert json_ld["type"] == "Person"
    assert json_ld["id"] == build_actor_id(actor.id)
    assert json_ld["preferredUsername"] == actor.username
    assert json_ld["name"] == actor.username
    assert isinstance(json_ld["previously"], list)


def test_build_note_json_ld(note):
    json_ld = build_note_json_ld(note)

    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Note"
    assert json_ld["id"] == build_note_id(note.id)
    assert json_ld["actor"] == build_actor_id(note.actor.id)
    assert json_ld["content"] == note.content
    assert json_ld["published"] == note.published.isoformat()
    assert json_ld["visibility"] == note.visibility


def test_build_create_activity_json_ld_with_note(create_activity):
    json_ld = build_create_activity_json_ld(create_activity)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Create"
    assert json_ld["id"] == build_activity_id(create_activity.id)
    assert json_ld["actor"] == build_actor_id(create_activity.actor.id)
    assert json_ld["published"] == create_activity.timestamp.isoformat()
    assert json_ld["visibility"] == create_activity.visibility
    assert json_ld["object"]["type"] == "Note"

# Test Create Activity JSON-LD builder for actor creation
def test_build_create_activity_json_ld_actor_creation(actor):
    create_activity = CreateActivityFactory(
        actor=actor,
        note=None
    )
    json_ld = build_create_activity_json_ld(create_activity)
    
    assert json_ld["object"]["type"] == "Person"
    assert json_ld["object"]["id"] == build_actor_id(actor.id)

# Test Like Activity JSON-LD builder with local note
def test_build_like_activity_json_ld_local(like_activity):
    json_ld = build_like_activity_json_ld(like_activity)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Like"
    assert json_ld["id"] == build_activity_id(like_activity.id)
    assert json_ld["actor"] == build_actor_id(like_activity.actor.id)
    assert json_ld["object"]["type"] == "Note"

# Test Like Activity JSON-LD builder with remote object
def test_build_like_activity_json_ld_remote(actor):
    remote_data = {
        "type": "Note",
        "content": "Remote content"
    }
    like_activity = LikeActivityFactory(
        actor=actor,
        note=None,
        object_url="https://remote.example/notes/123",
        object_data=remote_data
    )
    
    json_ld = build_like_activity_json_ld(like_activity)
    assert json_ld["object"]["id"] == "https://remote.example/notes/123"
    assert json_ld["object"]["content"] == "Remote content"

# Test Follow Activity JSON-LD builder with local actor
def test_build_follow_activity_json_ld_local(follow_activity):
    json_ld = build_follow_activity_json_ld(follow_activity)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Follow"
    assert json_ld["id"] == build_activity_id(follow_activity.id)
    assert json_ld["actor"] == build_actor_id(follow_activity.actor.id)
    assert json_ld["object"]["type"] == "Person"

# Test Follow Activity JSON-LD builder with remote actor
def test_build_follow_activity_json_ld_remote(actor):
    remote_data = {
        "type": "Person",
        "preferredUsername": "remote_user"
    }
    follow_activity = FollowActivityFactory(
        actor=actor,
        target_actor=None,
        target_actor_url="https://remote.example/users/remote_user",
        target_actor_data=remote_data
    )
    
    json_ld = build_follow_activity_json_ld(follow_activity)
    assert json_ld["object"]["id"] == "https://remote.example/users/remote_user"
    assert json_ld["object"]["preferredUsername"] == "remote_user"

# Test Outbox JSON-LD builder with multiple activities
def test_build_outbox_json_ld(outbox, create_activity, like_activity, follow_activity):
    json_ld = build_outbox_json_ld(outbox)
    
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