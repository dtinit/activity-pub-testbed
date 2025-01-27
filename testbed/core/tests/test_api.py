import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse

# Test that the Actor detail API returns the correct data
@pytest.mark.django_db
def test_actor_detail_api(actor):
    client = APIClient()
    url = reverse('actor-detail', kwargs={'pk': actor.id})
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data['id'] == actor.id
    assert response.data['json_ld'] == actor.get_json_ld()

# Test that the PortabilityOutbox detail API returns the correct data
@pytest.mark.django_db
def test_outbox_detail_api(outbox):
    client = APIClient()
    url = reverse('actor-outbox', kwargs={'pk': outbox.actor.id})
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert 'json_ld' in response.data

    # Check JSON-LD structure
    json_ld = response.data['json_ld']
    assert json_ld['type'] == 'OrderedCollection'
    assert json_ld['@context'] == 'https://www.w3.org/ns/activitystreams'
    assert json_ld['id'] == f'https://example.com/users/{outbox.actor.username}/outbox'
    assert json_ld['totalItems'] >= 0
    assert 'items' in json_ld