import pytest
from testbed.core.factories import UserFactory, ActorFactory, NoteFactory, ActivityFactory


@pytest.fixture
def user():
    return UserFactory()

@pytest.fixture
def actor():
    return ActorFactory()

@pytest.fixture
def note(actor):
    return NoteFactory(actor=actor)

@pytest.fixture
def activity(actor, note):
    return ActivityFactory(actor=actor, note=note)

@pytest.fixture
def outbox(actor):
    return actor.portability_outbox.first()
