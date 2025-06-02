import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from testbed.core.json_ld_builders import (
    build_actor_json_ld,
    build_note_json_ld,
    build_create_activity_json_ld,
    build_like_activity_json_ld,
    build_follow_activity_json_ld,
    build_outbox_json_ld,
)
# Test complete flow from API to JSON-LD for Actor
@pytest.mark.django_db
def test_complete_actor_json_ld_flow(actor):
    # Test direct builder
    builder_json_ld = build_actor_json_ld(actor)
    
    # Test API response
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": actor.id})
    response = client.get(url)
    
    # Both should match
    assert response.data == builder_json_ld

# Test complete flow from API to JSON-LD for Outbox
@pytest.mark.django_db
def test_complete_outbox_json_ld_flow(outbox):
    # Test direct builder
    builder_json_ld = build_outbox_json_ld(outbox)
    
    # Test API response
    client = APIClient()
    url = reverse("actor-outbox", kwargs={"pk": outbox.actor.id})
    response = client.get(url)
    
    # Both should match
    assert response.data == builder_json_ld

# Test that all activity types appear correctly in outbox
@pytest.mark.django_db
def test_activity_types_in_outbox(outbox, create_activity, like_activity, follow_activity):

    outbox.add_activity(create_activity)
    outbox.add_activity(like_activity)
    outbox.add_activity(follow_activity)

    json_ld = build_outbox_json_ld(outbox)
    
    # Check that we have all activity types
    activity_types = {item["type"] for item in json_ld["items"]}
    assert "Create" in activity_types
    assert "Like" in activity_types
    assert "Follow" in activity_types
    
    # Check specific activities
    for item in json_ld["items"]:
        if item["type"] == "Create":
            assert "object" in item
        elif item["type"] == "Like":
            assert "object" in item
        elif item["type"] == "Follow":
            assert "object" in item

# Test that JSON-LD structure is consistent across all builders
@pytest.mark.django_db
def test_json_ld_consistency(actor, note, create_activity, like_activity, follow_activity):
    builders_and_objects = [
        (build_actor_json_ld, actor),
        (build_note_json_ld, note),
        (build_create_activity_json_ld, create_activity),
        (build_like_activity_json_ld, like_activity),
        (build_follow_activity_json_ld, follow_activity),
    ]
    
    for builder, obj in builders_and_objects:
        json_ld = builder(obj)
        assert "@context" in json_ld
        assert "type" in json_ld
        assert "id" in json_ld