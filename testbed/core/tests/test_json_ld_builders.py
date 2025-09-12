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
    ActorFactory,
    LikeActivityFactory,
    FollowActivityFactory,
    CreateActivityFactory,
    NoteFactory
)
from testbed.core.tests.conftest import create_isolated_actor
from testbed.core.models import Actor, CreateActivity, LikeActivity, FollowActivity

# Test building JSON-LD for an actor
@pytest.mark.django_db
def test_build_actor_json_ld(actor, basic_auth_context, mock_request):
    json_ld = build_actor_json_ld(actor, basic_auth_context)
    
    assert json_ld["@context"] == build_actor_context()
    assert json_ld["type"] == "Person"
    assert json_ld["id"] == build_actor_id(actor.id, mock_request)
    assert json_ld["preferredUsername"] == actor.username
    assert json_ld["name"] == actor.username
    assert isinstance(json_ld["previously"], list)

# Test building JSON-LD for a note
@pytest.mark.django_db
def test_build_note_json_ld(note, basic_auth_context, mock_request):
    json_ld = build_note_json_ld(note, basic_auth_context)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Note"
    assert json_ld["id"] == build_note_id(note.id, mock_request)
    assert json_ld["actor"] == build_actor_id(note.actor.id, mock_request)
    assert json_ld["content"] == note.content
    assert json_ld["visibility"] == note.visibility

# Test building JSON-LD for note creation activity
@pytest.mark.django_db
def test_build_create_activity_json_ld_note(actor, basic_auth_context, mock_request):
    note = NoteFactory(actor=actor)
    activity = CreateActivityFactory(actor=actor, note=note)
    json_ld = build_create_activity_json_ld(activity, basic_auth_context)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Create"
    assert json_ld["id"] == build_activity_id(activity.id, mock_request)
    assert json_ld["actor"] == build_actor_id(actor.id, mock_request)
    assert json_ld["object"]["type"] == "Note"
    assert json_ld["object"]["id"] == build_note_id(note.id, mock_request)

# Test building JSON-LD for actor creation activity
@pytest.mark.django_db
def test_build_create_activity_json_ld_actor_creation(actor, basic_auth_context, mock_request):
    activity = CreateActivityFactory(
        actor=actor,
        note=None,
        visibility="public"
    )
    json_ld = build_create_activity_json_ld(activity, basic_auth_context)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Create"
    assert json_ld["id"] == build_activity_id(activity.id, mock_request)
    assert json_ld["actor"] == build_actor_id(actor.id, mock_request)
    assert json_ld["object"]["type"] == "Person"
    assert json_ld["object"]["id"] == build_actor_id(actor.id, mock_request)

# Test building JSON-LD for local like activity
@pytest.mark.django_db
def test_build_like_activity_json_ld_local(actor, basic_auth_context, mock_request):
    note = NoteFactory(actor=actor)
    activity = LikeActivityFactory(actor=actor, note=note)
    json_ld = build_like_activity_json_ld(activity, basic_auth_context)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Like"
    assert json_ld["id"] == build_activity_id(activity.id, mock_request)
    assert json_ld["actor"] == build_actor_id(actor.id, mock_request)
    assert json_ld["object"]["type"] == "Note"
    assert json_ld["object"]["id"] == build_note_id(note.id, mock_request)

# Test building JSON-LD for remote like activity
@pytest.mark.django_db
def test_build_like_activity_json_ld_remote(actor, basic_auth_context, mock_request):
    activity = LikeActivityFactory(
        actor=actor,
        note=None,
        object_url="https://remote.example/notes/123",
        object_data={"content": "Remote content"}
    )
    
    json_ld = build_like_activity_json_ld(activity, basic_auth_context)
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Like"
    assert json_ld["id"] == build_activity_id(activity.id, mock_request)
    assert json_ld["actor"] == build_actor_id(actor.id, mock_request)
    assert json_ld["object"]["id"] == "https://remote.example/notes/123"
    assert json_ld["object"]["content"] == "Remote content"

# Test building JSON-LD for local follow activity
@pytest.mark.django_db
def test_build_follow_activity_json_ld_local(actor, other_actor, basic_auth_context, mock_request):
    activity = FollowActivityFactory(
        actor=actor,
        target_actor=other_actor
    )
    
    json_ld = build_follow_activity_json_ld(activity, basic_auth_context)
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Follow"
    assert json_ld["id"] == build_activity_id(activity.id, mock_request)
    assert json_ld["actor"] == build_actor_id(actor.id, mock_request)
    assert json_ld["object"]["type"] == "Person"
    assert json_ld["object"]["id"] == build_actor_id(other_actor.id, mock_request)

# Test building JSON-LD for remote follow activity
@pytest.mark.django_db
def test_build_follow_activity_json_ld_remote(actor, basic_auth_context, mock_request):
    activity = FollowActivityFactory(
        actor=actor,
        target_actor=None,
        target_actor_url="https://remote.example/users/remote_user",
        target_actor_data={"preferredUsername": "remote_user"}
    )
    
    json_ld = build_follow_activity_json_ld(activity, basic_auth_context)
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Follow"
    assert json_ld["id"] == build_activity_id(activity.id, mock_request)
    assert json_ld["actor"] == build_actor_id(actor.id, mock_request)
    assert json_ld["object"]["id"] == "https://remote.example/users/remote_user"
    assert json_ld["object"]["preferredUsername"] == "remote_user"

# Test Outbox JSON-LD builder with multiple activities
@pytest.mark.django_db
def test_build_outbox_json_ld(lola_auth_context, mock_request):
    # Create actors with the helper function that ensures unique usernames
    actor = create_isolated_actor("json_ld_outbox_test")
    target_actor = create_isolated_actor("json_ld_target_test")
    outbox = actor.portability_outbox
    
    # Create a note for our tests
    note = NoteFactory(actor=actor, content="Test note for outbox")
    
    # Use factories to create activities but pass in our controlled actors
    create_activity = CreateActivityFactory(
        actor=actor,
        note=note
    )
    
    like_activity = LikeActivityFactory(
        actor=actor,
        note=note
    )
    
    follow_activity = FollowActivityFactory(
        actor=actor,
        target_actor=target_actor
    )
    
    # Add activities to outbox
    outbox.add_activity(create_activity)
    outbox.add_activity(like_activity)
    outbox.add_activity(follow_activity)
    
    # Use authenticated context to see all activities regardless of visibility
    json_ld = build_outbox_json_ld(outbox, lola_auth_context)
    
    # Check outbox structure
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "OrderedCollection"
    assert json_ld["id"] == build_outbox_id(outbox.actor.id, mock_request)
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
