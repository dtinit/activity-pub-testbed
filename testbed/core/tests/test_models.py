import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from testbed.core.models import Actor, Note, CreateActivity, LikeActivity, FollowActivity, PortabilityOutbox
from testbed.core.factories import (
    UserOnlyFactory,
    ActorFactory,
    NoteFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
)
from testbed.core.tests.conftest import (
    create_isolated_actor,
    create_isolated_remote_like,
    create_isolated_remote_follow,
)

# Test basic actor creation
def test_actor_creation(actor):
    assert actor.user is not None
    assert actor.role in [Actor.ROLE_SOURCE, Actor.ROLE_DESTINATION]

# Test actor string representation
def test_actor_str_representation(actor):
    assert str(actor) == f"{actor.user.username}'s {actor.role} actor"

# Test that a user cannot have multiple actors with the same role
def test_actor_unique_role_constraint():
    # Create a user directly
    user = UserOnlyFactory(username="unique_role_test_user")
    
    # Create first actor manually
    first_actor = Actor.objects.create(
        user=user,
        username="unique_role_test_source",
        role=Actor.ROLE_SOURCE
    )
    
    # Try to create another actor with the same role for same user
    second_actor = Actor(
        user=user,
        username="unique_role_test_source2",
        role=Actor.ROLE_SOURCE
    )
    
    with pytest.raises(ValidationError):
        second_actor.clean()

# Test recording actor movement history
def test_actor_move_history(actor):
    test_date = timezone.now()
    
    actor.record_move("old-server.com", "old_username", test_date)
    assert len(actor.previously) == 1
    assert actor.previously[0]["type"] == "Move"
    assert actor.previously[0]["object"] == "https://old-server.com/users/old_username"
    assert actor.previously[0]["published"] == test_date.isoformat()

# Test basic note creation
def test_note_creation(note):
    assert note.content is not None
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
    # Create isolated actor using helper function
    actor = create_isolated_actor("like_validation_test")
    
    # Create invalid activity (no note and no remote object data)
    activity = LikeActivity(
        actor=actor,
        note=None,
        object_url=None,
        visibility="public"
    )
    
    with pytest.raises(ValidationError):
        activity.clean()

# Test Like activity with remote object data
def test_like_activity_remote_object_validation():
    # Use helper function that creates isolated actor and uses factory
    activity = create_isolated_remote_like()
    
    # Verify remote object data
    assert activity.object_url.startswith("https://remote.example/notes/")
    assert activity.object_data["content"] == "Remote note content"

# Test that Follow activity requires either target_actor or remote actor data
def test_follow_activity_validation():
    # Create isolated actor using helper function
    actor = create_isolated_actor("follow_validation_test")
    
    # Create invalid activity (no target_actor and no remote actor data)
    activity = FollowActivity(
        actor=actor,
        target_actor=None,
        target_actor_url=None,
        target_actor_data=None,
        visibility="public"
    )
    
    with pytest.raises(ValidationError):
        activity.clean()

# Test Follow activity with remote actor data
def test_follow_activity_remote_actor_validation():
    # Use helper function that creates isolated actor and uses factory
    activity = create_isolated_remote_follow()
    
    # Verify remote actor data
    assert activity.target_actor_url.startswith("https://remote.example/users/")
    assert "preferredUsername" in activity.target_actor_data

# Test outbox is created automatically for actors
def test_portability_outbox_creation():
    from testbed.core.utils.actor_utils import populate_source_actor_outbox
    from testbed.core.models import Note, CreateActivity
    
    # Create an isolated actor for testing
    actor = create_isolated_actor("outbox_test")
    
    # Actor should have an outbox created automatically
    assert actor.portability_outbox is not None
    
    # The outbox should have the actor creation activity
    assert actor.portability_outbox.activities_create.count() >= 1
    
    # At least one Create activity should be for actor creation (no note)
    actor_create_activities = actor.portability_outbox.activities_create.filter(note__isnull=True)
    assert actor_create_activities.count() >= 1
    
    # Manually populate the outbox with additional content for testing
    populate_source_actor_outbox(actor, num_notes=2)
    
    # Now verify we have notes
    note_activities = actor.portability_outbox.activities_create.filter(note__isnull=False)
    assert note_activities.count() > 0
    
    # And we should have likes and follows
    assert actor.portability_outbox.activities_like.count() > 0
    assert actor.portability_outbox.activities_follow.count() > 0

# Test adding different types of activities to outbox
def test_outbox_activity_types():
    # Create isolated actors using helper functions
    actor = create_isolated_actor("types_test")
    target_actor = create_isolated_actor("target_test")
    
    # Create a note for the like activity
    note = NoteFactory(actor=actor, content="Test note for liking")
    
    outbox = actor.portability_outbox
    initial_create_count = outbox.activities_create.count()
    initial_like_count = outbox.activities_like.count()
    initial_follow_count = outbox.activities_follow.count()

    # Use factories but pass in our manually created actors
    create_activity = CreateActivityFactory(actor=actor, note=note)
    like_activity = LikeActivityFactory(actor=actor, note=note)
    follow_activity = FollowActivityFactory(actor=actor, target_actor=target_actor)

    outbox.add_activity(create_activity)
    outbox.add_activity(like_activity)
    outbox.add_activity(follow_activity)

    # Check that counts have increased by 1
    assert outbox.activities_create.count() == initial_create_count + 1
    assert outbox.activities_like.count() == initial_like_count + 1
    assert outbox.activities_follow.count() == initial_follow_count + 1

# Test adding multiple activities to outbox
def test_outbox_activity_addition():
    # Create isolated actors using helper functions
    actor = create_isolated_actor("addition_test")
    target_actor = create_isolated_actor("target_addition_test")
    
    # Create a note for the like activity
    note = NoteFactory(actor=actor, content="Test note for addition")
    
    outbox = actor.portability_outbox
    
    activities = [
        CreateActivityFactory(actor=actor, note=note),
        LikeActivityFactory(actor=actor, note=note),
        FollowActivityFactory(actor=actor, target_actor=target_actor)
    ]
    
    for activity in activities:
        outbox.add_activity(activity)
        
    assert activities[0] in outbox.activities_create.all()
    assert activities[1] in outbox.activities_like.all()
    assert activities[2] in outbox.activities_follow.all()
