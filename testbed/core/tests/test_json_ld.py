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
from testbed.core.factories import (
    LikeActivityFactory,
    FollowActivityFactory
)

# Test complete flow from API to JSON-LD for Source Actor
@pytest.mark.django_db
def test_source_actor_json_ld_flow(source_actor):
    # Test JSON-LD generation for source actors
    builder_json_ld = build_actor_json_ld(source_actor)
    
    # Test API response
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": source_actor.id})
    response = client.get(url)
    
    # Both should match
    assert response.data == builder_json_ld
    assert response.data["type"] == "Person"
    assert response.data["preferredUsername"] == source_actor.username
    # assert response.data["role"] == source_actor.role

# Test complete flow from API to JSON-LD for Destination Actor
@pytest.mark.django_db
def test_destination_actor_json_ld_flow(destination_actor):
    # Test JSON-LD generation for destination actors
    builder_json_ld = build_actor_json_ld(destination_actor)
    
    # Test API response
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": destination_actor.id})
    response = client.get(url)
    
    # Both should match
    assert response.data == builder_json_ld
    assert response.data["type"] == "Person"
    assert response.data["preferredUsername"] == destination_actor.username
    # assert response.data["role"] == destination_actor.role

# Test complete flow from API to JSON-LD for Outbox
@pytest.mark.django_db
def test_complete_outbox_json_ld_flow(outbox):
    # Test JSON-LD generation for outboxes
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
    # Test all activity types in outbox JSON-LD
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
def test_json_ld_consistency(source_actor, note, create_activity, like_activity, follow_activity):
    # Test JSON-LD structure consistency across all builders
    builders_and_objects = [
        (build_actor_json_ld, source_actor),
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

# Test JSON-LD for remote activities
@pytest.mark.django_db
def test_remote_activity_json_ld(source_actor):
    # Test JSON-LD generation for activities with remote objects
    # Create activities with remote objects
    like_activity = LikeActivityFactory(
        actor=source_actor,
        note=None,
        object_url="https://remote.example/notes/123",
        object_data={"content": "Remote content"}
    )
    
    follow_activity = FollowActivityFactory(
        actor=source_actor,
        target_actor=None,
        target_actor_url="https://remote.example/users/remote_user",
        target_actor_data={"preferredUsername": "remote_user"}
    )

    # Test JSON-LD generation
    like_json_ld = build_like_activity_json_ld(like_activity)
    follow_json_ld = build_follow_activity_json_ld(follow_activity)

    # Verify remote object structure
    assert like_json_ld["object"]["id"] == "https://remote.example/notes/123"
    assert follow_json_ld["object"]["id"] == "https://remote.example/users/remote_user"