import pytest


# Test that an Actor is created correctly
@pytest.mark.django_db
def test_actor_creation(actor):
    assert actor.username == 'testactor'
    assert actor.full_name == 'Test Actor'
    assert actor.user.username == 'testuser'

# Test that the Actor's JSON-LD representation is correct
@pytest.mark.django_db
def test_actor_json_ld(actor):
    expected = {
        "@context": [
            "https://www.w3.org/ns/activitystreams",
            "https://swicg.github.io/activitypub-data-portability/lola.jsonld",
        ],
        "type": "Person",
        "id": "https://example.com/users/testactor",
        "preferredUsername": "testactor",
        "name": "testactor",
        "previously": {},
    }
    assert actor.get_json_ld() == expected

# Test that a Portability Outbox is linked to an Actor
@pytest.mark.django_db
def test_outbox_creation(outbox):
    assert outbox.actor.username == 'testactor'
    assert outbox.actor.full_name == 'Test Actor'
    assert outbox.actor.user.username == 'testuser'
    assert outbox.actor.user.actor == outbox.actor
    assert outbox.actor.actor_activities.count() == 0
