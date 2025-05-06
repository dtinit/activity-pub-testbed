import pytest
from testbed.core.factories import (
    TesterUserFactory,
    ActorFactory,
    NoteFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
)

@pytest.fixture
def tester():
    return TesterUserFactory()

@pytest.fixture
def actor():
    return ActorFactory()


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
    return actor.portability_outbox.first()
