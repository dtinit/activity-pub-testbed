import pytest
from testbed.core.serializers import ActorSerializer, UserRegistrationSerializer


# Test that the ActorSerializer returns the correct data
@pytest.mark.django_db
def test_actor_serializer(actor):
    serializer = ActorSerializer(actor)
    expected = {
        "id": actor.id,
        "json_ld": actor.get_json_ld(),
    }
    assert serializer.data == expected


# Tester registration serializer test
@pytest.mark.django_db
def test_user_registration_serializer():
    data = {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'testpass123'
    }
    serializer = UserRegistrationSerializer(data=data)
    assert serializer.is_valid()
    assert 'password' not in serializer.data # password is write_only
