import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth.models import User


# Test that the Actor detail API returns the correct data
@pytest.mark.django_db
def test_actor_detail_api(actor):
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": actor.id})
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == actor.id
    assert response.data["json_ld"] == actor.get_json_ld()


# Test that the PortabilityOutbox detail API returns the correct data
@pytest.mark.django_db
def test_outbox_detail_api(outbox):
    client = APIClient()
    url = reverse("actor-outbox", kwargs={"pk": outbox.actor.id})
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "json_ld" in response.data

    # Check JSON-LD structure
    json_ld = response.data["json_ld"]
    assert json_ld["type"] == "OrderedCollection"
    assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["id"] == f"https://example.com/users/{outbox.actor.username}/outbox"
    assert json_ld["totalItems"] >= 0
    assert "items" in json_ld


# Tester registration API test
@pytest.mark.django_db
def test_tester_registration_api():
    client = APIClient()
    url = reverse('register')
    data = {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'testpass123'
    }
    response = client.post(url, data)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['username'] == 'testuser'
    assert 'user_id' in response.data

# Login API test
@pytest.mark.django_db
def test_login_api_successful():
    User.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com'
    )

    client = APIClient()
    url = reverse('login')
    data = {
        'username': 'testuser',
        'password': 'testpass123'
    }
    response = client.post(url, data)

    assert response.status_code == status.HTTP_200_OK
    assert response.data['message'] == 'Login successful'
    assert response.data['username'] == 'testuser'
    assert response.data['email'] == 'test@example.com'
    assert 'user_id' in response.data

@pytest.mark.django_db
def test_login_api_invalid_credentials():
    client = APIClient()
    url = reverse('login')
    data = {
        'username': 'testuser',
        'password': 'wrongpassword'
    }
    response = client.post(url, data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'Invalid username or password.' in str(response.data)

@pytest.mark.django_db
def test_login_api_mising_fields():
    client = APIClient()
    url = reverse('login')

    # Test missing password
    response = client.post(url, {'username': 'testuser'})
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Test missing username
    response = client.post(url, {'password': 'testpass123'})
    assert response.status_code == status.HTTP_400_BAD_REQUEST