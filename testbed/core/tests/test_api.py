import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from testbed.core.models import Actor
from testbed.core.json_ld_utils import (
    build_basic_context,
    build_actor_context,
    build_actor_id,
    build_outbox_id,
)


@pytest.mark.django_db
def test_actor_detail_api(actor):
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": actor.id})
    response = client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    
    # Check JSON-LD structure directly
    json_ld = response.data
    assert json_ld["@context"] == build_actor_context()
    assert json_ld["type"] == "Person"
    assert json_ld["id"] == build_actor_id(actor.id)
    assert json_ld["preferredUsername"] == actor.username
    assert json_ld["name"] == actor.username
    assert isinstance(json_ld["previously"], list)


@pytest.mark.django_db
def test_outbox_detail_api(actor):
    # Ensure we're using a source actor
    actor.role = Actor.ROLE_SOURCE
    actor.save()
    
    client = APIClient()
    url = reverse("actor-outbox", kwargs={"pk": actor.id})
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK

    # Check JSON-LD structure directly
    json_ld = response.data
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "OrderedCollection"
    assert json_ld["id"] == build_outbox_id(actor.id)
    assert isinstance(json_ld["totalItems"], int)
    assert isinstance(json_ld["items"], list)

    # Check items structure if any exist
    if json_ld["items"]:
        for item in json_ld["items"]:
            assert item["@context"] == build_basic_context()
            assert "type" in item
            assert "id" in item
            assert "actor" in item
            assert "published" in item
            assert "visibility" in item


@pytest.mark.django_db
def test_actor_detail_api_not_found():
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": 99999})
    response = client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_outbox_detail_api_not_found():
    client = APIClient()
    url = reverse("actor-outbox", kwargs={"pk": 99999})
    response = client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND