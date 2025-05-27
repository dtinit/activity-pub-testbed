import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from testbed.core.models import Actor


@pytest.mark.django_db
def test_actor_detail_api(actor):
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": actor.id})
    response = client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == actor.id
    
    # Check JSON-LD response
    json_ld = response.data["json_ld"]
    assert json_ld["@context"] == [
        "https://www.w3.org/ns/activitystreams",
        "https://swicg.github.io/activitypub-data-portability/lola.jsonld",
    ]
    assert json_ld["type"] == "Person"
    assert json_ld["id"] == f"https://example.com/actors/{actor.id}"
    assert json_ld["preferredUsername"] == actor.username
    assert json_ld["name"] == actor.username
    assert json_ld["previously"] == actor.previously


@pytest.mark.django_db
def test_outbox_detail_api(actor):
    # Ensure we're using a source actor
    actor.role = Actor.ROLE_SOURCE
    actor.save()
    
    client = APIClient()
    url = reverse("actor-outbox", kwargs={"pk": actor.id})
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "json_ld" in response.data

    # Check JSON-LD structure
    json_ld = response.data["json_ld"]
    assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["type"] == "OrderedCollection"
    # assert json_ld["id"] == f"https://example.com/users/{actor.user.username}/outbox"
    assert json_ld["id"] == f"https://example.com/actors/{actor.id}/outbox"
    assert isinstance(json_ld["totalItems"], int)
    assert isinstance(json_ld["items"], list)

    # Check items structure if any exist
    if json_ld["items"]:
        for item in json_ld["items"]:
            assert "@context" in item
            assert "type" in item
            assert "id" in item
            assert "actor" in item
            assert "published" in item
            assert "visibility" in item