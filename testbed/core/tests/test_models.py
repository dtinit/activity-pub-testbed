import pytest
from django.core.exceptions import ValidationError
from testbed.core.factories import ActorFactory


def test_actor_creation(actor):
    assert actor.user is not None
    assert actor.username == actor.user.username
    assert actor.full_name is not None

def test_actor_str_representation(actor):
    assert str(actor) == actor.username

@pytest.mark.parametrize('invalid_username', [
    'user space', # Contains space
    'ab', # Too short
    'user@name' # Non-alphanumeric
])
def test_username_validation(invalid_username):
    with pytest.raises(ValidationError):
        actor =ActorFactory(username=invalid_username)
        actor.full_clean()  # This triggers the validation

def test_portability_outbox_creation(actor):
    assert actor.portability_outbox.count() == 1
    outbox = actor.portability_outbox.first()
    assert outbox.activities.count() == 1 # Initial Create activity
    assert outbox.activities.first().type == 'Create'