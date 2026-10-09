import pytest
from datetime import datetime, timezone
from testbed.core.json_ld_builders import (
    NOTE_METADATA,
    build_actor_json_ld,
    build_note_json_ld,
    build_create_activity_json_ld,
    build_like_activity_json_ld,
    build_follow_activity_json_ld,
    build_outbox_json_ld
)
from testbed.core.json_ld_utils import (
    ACTIVITY_STREAM_CONTEXT,
    PREVIOUSLY_TERM,
    build_basic_context,
    build_actor_context,
    build_actor_id,
    build_note_id,
    build_activity_id,
    build_outbox_id
)
from testbed.core.factories import (
    ActorFactory,
    IsolatedActorFactory,
    LikeActivityFactory,
    FollowActivityFactory,
    CreateActivityFactory,
    NoteFactory
)
from testbed.core.models import Actor, CreateActivity, LikeActivity, FollowActivity, Note

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
    assert json_ld["id"] == build_note_id(note, mock_request)
    assert json_ld["attributedTo"] == build_actor_id(note.actor.id, mock_request)
    assert json_ld["content"] == note.content
    assert json_ld["visibility"] == note.visibility
    # Empty metadata is left out entirely, so locally authored Notes keep exactly these keys
    assert set(json_ld) == {"@context", "type", "id", "attributedTo", "content", "published", "visibility"}

# LOLA §6.3: a copied Note serves every metadata field as stored, and keeps its original `published` (§7.1.7)
@pytest.mark.django_db
def test_build_note_json_ld_serves_copied_metadata(actor, basic_auth_context):
    published = datetime(2016, 5, 1, 12, 0, tzinfo=timezone.utc)
    note = NoteFactory(actor=actor, copied=True, published=published)
    json_ld = build_note_json_ld(note, basic_auth_context)

    for key, column in NOTE_METADATA.items():
        assert json_ld[key] == getattr(note, column)
    assert json_ld["published"] == published.isoformat()
    assert json_ld["@context"] == [ACTIVITY_STREAM_CONTEXT, PREVIOUSLY_TERM]

# A new Note column fails here until someone decides whether it goes on the wire
def test_every_note_column_has_a_wire_disposition():
    always_served = {"actor", "content", "published", "visibility"}
    served_when_set = set(NOTE_METADATA.values())
    internal = {"id"}
    columns = [field.name for field in Note._meta.concrete_fields]

    assert always_served | served_when_set | internal == set(columns)
    # With the union equal, equal sizes mean no column sits in two groups
    assert len(always_served) + len(served_when_set) + len(internal) == len(columns)

# Test building JSON-LD for note creation activity
@pytest.mark.django_db
def test_build_create_activity_json_ld_note(actor, basic_auth_context, mock_request):
    note = NoteFactory(actor=actor)
    activity = CreateActivityFactory(actor=actor, note=note)
    json_ld = build_create_activity_json_ld(activity, basic_auth_context)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Create"
    assert json_ld["id"] == build_activity_id("create", activity, mock_request)
    assert json_ld["actor"] == build_actor_id(actor.id, mock_request)
    assert json_ld["object"]["type"] == "Note"
    assert json_ld["object"]["id"] == build_note_id(note, mock_request)

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
    assert json_ld["id"] == build_activity_id("create", activity, mock_request)
    assert json_ld["actor"] == build_actor_id(actor.id, mock_request)
    assert json_ld["object"]["type"] == "Person"
    assert json_ld["object"]["id"] == build_actor_id(actor.id, mock_request)

# Test building JSON-LD for local like activity
@pytest.mark.django_db
def test_build_like_activity_json_ld_local(actor, basic_auth_context, mock_request):
    # Only a public Note is embedded. The non-public case is test_like_of_another_accounts_private_note_is_served_as_id_only
    note = NoteFactory(actor=actor, visibility="public")
    activity = LikeActivityFactory(actor=actor, note=note)
    json_ld = build_like_activity_json_ld(activity, basic_auth_context)
    
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "Like"
    assert json_ld["id"] == build_activity_id("like", activity, mock_request)
    assert json_ld["actor"] == build_actor_id(actor.id, mock_request)
    assert json_ld["object"]["type"] == "Note"
    assert json_ld["object"]["id"] == build_note_id(note, mock_request)

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
    assert json_ld["id"] == build_activity_id("like", activity, mock_request)
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
    assert json_ld["id"] == build_activity_id("follow", activity, mock_request)
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
    assert json_ld["id"] == build_activity_id("follow", activity, mock_request)
    assert json_ld["actor"] == build_actor_id(actor.id, mock_request)
    assert json_ld["object"]["id"] == "https://remote.example/users/remote_user"
    assert json_ld["object"]["preferredUsername"] == "remote_user"

# LOLA §7.1.8: an activity serves its breadcrumbs and the term defining them, or neither
@pytest.mark.django_db
@pytest.mark.parametrize("activity_factory, build, related", [
    (CreateActivityFactory, build_create_activity_json_ld, {"note": None}),
    (LikeActivityFactory, build_like_activity_json_ld, {"remote": True}),
    (FollowActivityFactory, build_follow_activity_json_ld, {"remote": True}),
])
def test_activity_serves_breadcrumbs_only_when_present(actor, basic_auth_context, activity_factory, build, related):
    breadcrumbs = [{"actor": "https://mistywing.example/", "id": "https://mistywing.example/cherry/228"}]
    with_breadcrumbs = build(activity_factory(actor=actor, previously=breadcrumbs, **related), basic_auth_context)
    without = build(activity_factory(actor=actor, **related), basic_auth_context)

    assert with_breadcrumbs["previously"] == breadcrumbs
    assert with_breadcrumbs["@context"] == [ACTIVITY_STREAM_CONTEXT, PREVIOUSLY_TERM]
    assert "previously" not in without
    assert without["@context"] == ACTIVITY_STREAM_CONTEXT

# Test Outbox JSON-LD builder with multiple activities
@pytest.mark.django_db
def test_build_outbox_json_ld(lola_auth_context, mock_request):
    # Create actors with the helper function that ensures unique usernames
    actor = IsolatedActorFactory(prefix="json_ld_outbox_test")
    target_actor = IsolatedActorFactory(prefix="json_ld_target_test")
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
    assert isinstance(json_ld["orderedItems"], list)
    
    # Verify each item has required fields
    for item in json_ld["orderedItems"]:
        assert "@context" in item
        assert "type" in item
        assert "id" in item
        assert "actor" in item
        assert "published" in item
        assert "visibility" in item
    
    # Verify activity types are present
    activity_types = {item["type"] for item in json_ld["orderedItems"]}
    assert "Create" in activity_types
    assert "Like" in activity_types
    assert "Follow" in activity_types
