import pytest
from django.contrib.auth.models import User
from testbed.core.models import Actor, PortabilityOutbox


# Create and return a user
@pytest.fixture
def user():
    return User.objects.create_user(username='testuser', password='testpass')

# Create and return an actor linked to the user
@pytest.fixture
def actor(user):
    return Actor.objects.create(user=user, username='testactor', full_name='Test Actor')

# Create and return a portability outbox linked to the actor
@pytest.fixture
def outbox(actor):
    return PortabilityOutbox.objects.create(actor=actor)


