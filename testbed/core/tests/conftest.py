import pytest
import random
from testbed.core.factories import (
    UserOnlyFactory,
    UserWithActorsFactory,
    ActorFactory,
    NoteFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
)
from testbed.core.models import Actor, User
from testbed.core.utils.actor_utils import populate_source_actor_outbox

# Helper function to create an isolated actor (no signals triggered)
def create_isolated_actor(username_prefix, role=None):
    # Creates an actor without triggering signals for additional objects
    role = role or Actor.ROLE_SOURCE  # Default to source
    user = UserOnlyFactory(username=f"{username_prefix}_user")
    return Actor.objects.create(
        user=user,
        username=f"{username_prefix}_actor",
        role=role
    )

# Helper function to create an isolated LikeActivity with remote object
def create_isolated_remote_like(username_prefix="remote_like_test"):
    # Creates a LikeActivity for a remote object with an isolated actor
    actor = create_isolated_actor(username_prefix)
    return LikeActivityFactory(
        actor=actor,
        note=None,
        object_url=f"https://remote.example/notes/{random.randint(1000, 9999)}",
        object_data={"content": "Remote note content"},
        visibility="public"
    )

# Helper function to create an isolated FollowActivity with remote target
def create_isolated_remote_follow(username_prefix="remote_follow_test"):
    # Creates a FollowActivity for a remote actor with an isolated actor
    actor = create_isolated_actor(username_prefix)
    return FollowActivityFactory(
        actor=actor,
        target_actor=None,
        target_actor_url=f"https://remote.example/users/user_{random.randint(1000, 9999)}",
        target_actor_data={"preferredUsername": f"remote_user_{random.randint(1000, 9999)}"},
        visibility="public"
    )

# Creates an isolated actor with note for validation tests
@pytest.fixture
def isolated_actor_with_note():
    actor = create_isolated_actor("isolated_note_test")
    note = NoteFactory(actor=actor)
    return {"actor": actor, "note": note}

# Creates a user without actors
@pytest.fixture
def user():
    return UserOnlyFactory()

# Creates a user with associated actors
@pytest.fixture
def user_with_actors():
    return UserWithActorsFactory()

# Returns an actor for testing
@pytest.fixture
def actor():
    # Create a unique user for this actor
    user = UserOnlyFactory(username="fixture_test_user")
    return Actor.objects.create(
        user=user,
        username="fixture_test_actor_source",
        role=Actor.ROLE_SOURCE,
    )

# Returns another actor for interaction testing
@pytest.fixture
def other_actor():
    # Create a unique user for this actor
    user = UserOnlyFactory(username="fixture_other_user")
    return Actor.objects.create(
        user=user,
        username="fixture_test_actor_dest",
        role=Actor.ROLE_DESTINATION,
    )

# Creates a note from an actor
@pytest.fixture
def note(actor):
    return NoteFactory(actor=actor)

# Creates a Create activity for a note
@pytest.fixture
def create_activity(actor, note):
    return CreateActivityFactory(actor=actor, note=note)

# Creates a Create activity for actor creation
@pytest.fixture
def actor_create_activity(actor):
    return CreateActivityFactory(
        actor=actor,
        note=None,  # No note means this is an Actor creation activity
        visibility="public"
    )

# Creates a Like activity for a note
@pytest.fixture
def like_activity(actor, note):
    return LikeActivityFactory(actor=actor, note=note)

# Creates a Follow activity between actors
@pytest.fixture
def follow_activity(actor, other_actor):
    return FollowActivityFactory(
        actor=actor,
        target_actor=other_actor
    )

# Returns the actor's outbox
@pytest.fixture
def outbox():
    # Create a unique user for this actor's outbox
    user = UserOnlyFactory(username="fixture_outbox_user")
    source_actor = Actor.objects.create(
        user=user,
        username="fixture_outbox_actor",
        role=Actor.ROLE_SOURCE,
    )
    return source_actor.portability_outbox

# Creates a user via the User model directly to test signal-based actor creation
@pytest.fixture
def user_created_via_signal():
    user = User.objects.create_user(
        username="signal_test_user",
        email="signal_test@example.com",
        password="testpass123"
    )
    return user

# Creates a source actor with populated outbox for testing
@pytest.fixture
def populated_source_actor():
    # Get an existing source actor
    source_actor = User.objects.create_user(
        username=f"populate_test_user_{random.randint(1000, 9999)}",
        email="populate_test@example.com",
        password="testpass123"
    ).actors.get(role=Actor.ROLE_SOURCE)
    
    # Now manually repopulate the outbox with our controlled content for testing
    # First clear the existing content
    source_actor.portability_outbox.activities_create.all().delete()
    source_actor.portability_outbox.activities_like.all().delete()
    source_actor.portability_outbox.activities_follow.all().delete()
    
    # Now populate with known content
    populate_source_actor_outbox(
        source_actor=source_actor,
        num_notes=3,
        include_local_interactions=True
    )
    
    return source_actor
