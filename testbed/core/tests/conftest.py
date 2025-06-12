import pytest
from testbed.core.factories import (
    UserOnlyFactory,
    UserWithActorsFactory,
    ActorFactory,
    NoteFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
)
from testbed.core.models import Actor

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
    return ActorFactory()

# Returns another actor for interaction testing
@pytest.fixture
def other_actor():
    return ActorFactory()

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
    source_actor = ActorFactory(role=Actor.ROLE_SOURCE)
    return source_actor.portability_outbox