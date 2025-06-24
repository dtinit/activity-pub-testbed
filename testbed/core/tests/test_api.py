import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from testbed.core.models import Actor
from testbed.core.factories import ActorFactory
from testbed.core.tests.conftest import create_isolated_actor
from testbed.core.json_ld_utils import (
    build_basic_context,
    build_actor_context,
    build_actor_id,
    build_outbox_id,
)

# Test actor detail API endpoint
@pytest.mark.django_db
def test_actor_detail_api(actor):
    response = APIClient().get(reverse("actor-detail", kwargs={"pk": actor.id}))
    
    assert response.status_code == status.HTTP_200_OK
    
    # Check JSON-LD structure
    json_ld = response.data
    assert json_ld["@context"] == build_actor_context()
    assert json_ld["type"] == "Person"
    assert json_ld["id"] == build_actor_id(actor.id)
    assert json_ld["preferredUsername"] == actor.username
    assert json_ld["name"] == actor.username
    assert isinstance(json_ld["previously"], list)

# Test outbox detail API endpoint
@pytest.mark.django_db
def test_outbox_api_for_source_actor():
    # Create an actor with the helper function that ensures unique usernames
    actor = create_isolated_actor("api_test")
    response = APIClient().get(reverse("actor-outbox", kwargs={"pk": actor.id}))

    assert response.status_code == status.HTTP_200_OK

    # Check JSON-LD structure
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

# Test 404 response for non-existent actor
@pytest.mark.django_db
def test_actor_not_found():
    response = APIClient().get(reverse("actor-detail", kwargs={"pk": 99999}))
    assert response.status_code == status.HTTP_404_NOT_FOUND

# Test 404 response for non-existent outbox
@pytest.mark.django_db
def test_outbox_not_found():
    response = APIClient().get(reverse("actor-outbox", kwargs={"pk": 99999}))
    assert response.status_code == status.HTTP_404_NOT_FOUND