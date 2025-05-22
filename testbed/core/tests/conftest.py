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

@pytest.fixture
def user():
    return UserFactory()

@pytest.fixture
def actor():
    # Explicitly create a source actor for consistency
    return ActorFactory(role=Actor.ROLE_SOURCE)

@pytest.fixture
def note(actor):
    return NoteFactory(actor=actor)

@pytest.fixture
def create_activity(actor, note):
    return CreateActivityFactory(actor=actor, note=note)

@pytest.fixture
def like_activity(actor, note):
    return LikeActivityFactory(actor=actor, note=note)

@pytest.fixture
def follow_activity(actor):
    target_actor = ActorFactory()  # Create another actor to follow
    return FollowActivityFactory(actor=actor, target_actor=target_actor)

@pytest.fixture
def outbox(actor):
    # The outbox should be created automatically for source actors
    return actor.portability_outbox