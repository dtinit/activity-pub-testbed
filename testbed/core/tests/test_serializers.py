import pytest
from django.contrib.auth.models import User
from testbed.core.serializers import ActorSerializer, UserRegistrationSerializer, LoginSerializer


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

# Login serializer test
@pytest.mark.django_db
def test_login_serializer_valid():
    # Create test user
    user = User.objects.create_user(
        username='testuser',
        password='testpass123',
    )

    data = {
        'username': 'testuser',
        'password': 'testpass123'
    }
    serializer = LoginSerializer(data=data)

    assert serializer.is_valid()
    assert 'user' in serializer.validated_data
    assert serializer.validated_data['user'] == user

@pytest.mark.django_db
def test_login_serializer_invalid_credentials():
    data = {
        'username': 'testuser',
        'password': 'wrongpassword'
    }
    serializer = LoginSerializer(data=data)

    assert not serializer.is_valid()
    assert 'Invalid username or password.' in str(serializer.errors)

@pytest.mark.django_db
def test_login_serializer_inactive_user():
    # Create inactive user
    user = User.objects.create_user(
        username='inactiveuser',
        password='testpass123',
        # is_active=False
    )

    # Deactivate user after creation
    user.is_active = False
    user.save()

    data = {
        'username': 'inactiveuser',
        'password': 'testpass123'
    }
    serializer = LoginSerializer(data=data)

    assert not serializer.is_valid()
    # assert 'User account is disabled.' in str(serializer.errors)
    assert 'Invalid username or password.' in str(serializer.errors)
