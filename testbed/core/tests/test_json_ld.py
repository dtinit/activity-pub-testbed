import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from django.test import RequestFactory
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

# Test complete flow from API to JSON-LD for Actor
@pytest.mark.django_db
def test_actor_json_ld_flow(actor, basic_auth_context):
    # Test JSON-LD generation with proper auth_context
    builder_json_ld = build_actor_json_ld(actor, basic_auth_context)
    
    # Test API response
    client = APIClient()
    url = reverse("actor-detail", kwargs={"pk": actor.id})
    response = client.get(url)
    
    # Both should match
    assert response.data == builder_json_ld
    assert response.data["type"] == "Person"
    assert response.data["preferredUsername"] == actor.username

# Test complete flow from API to JSON-LD for Outbox
@pytest.mark.django_db
def test_complete_outbox_json_ld_flow(outbox, basic_auth_context):
    # Test JSON-LD generation for outboxes with proper auth_context
    builder_json_ld = build_outbox_json_ld(outbox, basic_auth_context)
    
    # Test API response
    client = APIClient()
    url = reverse("actor-outbox", kwargs={"pk": outbox.actor.id})
    response = client.get(url)
    
    # Both should match
    assert response.data == builder_json_ld

# Test that all activity types appear correctly in outbox
@pytest.mark.django_db
def test_activity_types_in_outbox(outbox, create_activity, like_activity, follow_activity, lola_auth_context):
    # Add activities to outbox
    outbox.add_activity(create_activity)
    outbox.add_activity(like_activity)
    outbox.add_activity(follow_activity)

    # Use authenticated context to see all activities regardless of visibility
    json_ld = build_outbox_json_ld(outbox, lola_auth_context)
    
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
def test_json_ld_consistency(actor, note, create_activity, like_activity, follow_activity, basic_auth_context):
    # Test JSON-LD structure consistency across all builders
    builders_and_objects = [
        (build_actor_json_ld, actor),
        (build_note_json_ld, note),
        (build_create_activity_json_ld, create_activity),
        (build_like_activity_json_ld, like_activity),
        (build_follow_activity_json_ld, follow_activity),
    ]
    
    for builder, obj in builders_and_objects:
        json_ld = builder(obj, basic_auth_context)
        assert "@context" in json_ld
        assert "type" in json_ld
        assert "id" in json_ld

# Test JSON-LD for remote activities
@pytest.mark.django_db
def test_remote_activity_json_ld(actor, basic_auth_context):
    # Create activities with remote objects using factory traits
    like_activity = LikeActivityFactory(
        actor=actor,
        remote=True
    )
    
    follow_activity = FollowActivityFactory(
        actor=actor,
        remote=True
    )

    # Test JSON-LD generation
    like_json_ld = build_like_activity_json_ld(like_activity, basic_auth_context)
    follow_json_ld = build_follow_activity_json_ld(follow_activity, basic_auth_context)

    # Verify remote object structure
    assert like_json_ld["object"]["id"] == like_activity.object_url
    assert follow_json_ld["object"]["id"] == follow_activity.target_actor_url
