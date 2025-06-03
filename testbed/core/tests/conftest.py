import pytest
from testbed.core.factories import (
    UserFactory,
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
    return UserFactory(with_actors=False)

# Creates a user with both source and destination actors
@pytest.fixture
def user_with_actors():
    return UserFactory(with_actors=True)

# Creates a pair of actors (source and destination) for a new user
@pytest.fixture
def actor_pair():
    return ActorFactory.create_pair()

# Returns the source actor from the pair
@pytest.fixture
def source_actor(actor_pair):
    return actor_pair[0]

# Returns the destination actor from the pair
@pytest.fixture
def destination_actor(actor_pair):
    return actor_pair[1]

# Creates another source actor for interaction testing
@pytest.fixture
def another_source_actor():
    return ActorFactory.create_source_actor()

# Creates another destination actor for interaction testing
@pytest.fixture
def another_destination_actor():
    return ActorFactory.create_destination_actor()

# Creates a note from a source actor
@pytest.fixture
def note(source_actor):
    return NoteFactory(actor=source_actor)

# Creates a Create activity for a note.
@pytest.fixture
def create_activity(source_actor, note):
    return CreateActivityFactory(actor=source_actor, note=note)

# Creates a Create activity for actor creation
@pytest.fixture
def actor_create_activity(source_actor):
    return CreateActivityFactory.create_for_actor(source_actor)

# Creates a Like activity for a note
@pytest.fixture
def like_activity(source_actor, note):
    return LikeActivityFactory(actor=source_actor, note=note)

# Creates a Follow activity from source to destination actor
@pytest.fixture
def follow_activity(source_actor, another_destination_actor):
    return FollowActivityFactory(
        actor=source_actor,
        target_actor=another_destination_actor
    )

# Returns the outbox of a source actor
@pytest.fixture
def outbox(source_actor):
    return source_actor.portability_outbox