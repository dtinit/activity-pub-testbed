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

def test_actor_creation_activity(actor):
    outbox = actor.portability_outbox.first()
    assert outbox is not None

    # Get initial Create activity
    activity = outbox.activities.first()
    assert activity is not None
    assert activity.type == 'Create'

    # Check Activity's JSON-LD
    json_ld = activity.get_json_ld()
    assert json_ld['type'] == 'Create'
    assert 'object' in json_ld

    # The object should be the Actor's JSON-LD
    actor_json_ld = actor.get_json_ld()
    assert json_ld['object'] == actor_json_ld

def test_actor_creation_activity_structure(actor):
    # Test the structure of the Create activity's JSON-LD
    activity = actor.portability_outbox.first().activities.first()
    json_ld = activity.get_json_ld()

    # Check required fields
    assert '@context' in json_ld
    assert 'type' in json_ld
    assert 'actor' in json_ld
    assert 'object' in json_ld
    assert 'published' in json_ld

    # Check specific values
    assert json_ld['type'] == 'Create'
    assert json_ld['actor'] == f'https://example.com/users/{actor.username}'
    assert json_ld['object']['type'] == 'Person'
    assert json_ld['object']['preferredUsername'] == actor.username

# Test that multiple actors each get their own Create activity
def test_multiple_actor_creations():
    actors = ActorFactory.create_batch(3)

    for actor in actors:
        outbox = actor.portability_outbox.first()
        activity = outbox.activities.first()

        json_ld = activity.get_json_ld()
        assert json_ld['object']['preferredUsername'] == actor.username
