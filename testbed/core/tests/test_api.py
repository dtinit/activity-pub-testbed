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

# Test actor detail API endpoint for source actors
@pytest.mark.django_db
def test_source_actor_detail_api(source_actor):
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": source_actor.id})
    response = client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    
    # Check JSON-LD structure
    json_ld = response.data
    assert json_ld["@context"] == build_actor_context()
    assert json_ld["type"] == "Person"
    assert json_ld["id"] == build_actor_id(source_actor.id)
    assert json_ld["preferredUsername"] == source_actor.username
    assert json_ld["name"] == source_actor.username
    assert isinstance(json_ld["previously"], list)

# Test actor detail API endpoint for destination actors
@pytest.mark.django_db
def test_destination_actor_detail_api(destination_actor):
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": destination_actor.id})
    response = client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    
    json_ld = response.data
    assert json_ld["@context"] == build_actor_context()
    assert json_ld["type"] == "Person"
    assert json_ld["id"] == build_actor_id(destination_actor.id)
    assert json_ld["preferredUsername"] == destination_actor.username
    assert json_ld["name"] == destination_actor.username
    assert isinstance(json_ld["previously"], list)

# Test outbox detail API endpoint (only available for source actors)
@pytest.mark.django_db
def test_outbox_detail_api(source_actor):
    client = APIClient()
    url = reverse("actor-outbox", kwargs={"pk": source_actor.id})
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK

    # Check JSON-LD structure
    json_ld = response.data
    assert json_ld["@context"] == build_basic_context()
    assert json_ld["type"] == "OrderedCollection"
    assert json_ld["id"] == build_outbox_id(source_actor.id)
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

# Test that outbox is not available for destination actors
@pytest.mark.django_db
def test_destination_actor_outbox_api(destination_actor):
    client = APIClient()
    url = reverse("actor-outbox", kwargs={"pk": destination_actor.id})
    response = client.get(url)
    
    # Should return 404 as destination actors don't have outboxes
    assert response.status_code == status.HTTP_404_NOT_FOUND

# Test 404 response for non-existent actor
@pytest.mark.django_db
def test_actor_detail_api_not_found():
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": 99999})
    response = client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

# Test 404 response for non-existent outbox
@pytest.mark.django_db
def test_outbox_detail_api_not_found():
    client = APIClient()
    url = reverse("actor-outbox", kwargs={"pk": 99999})
    response = client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND