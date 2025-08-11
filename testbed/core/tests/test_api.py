import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from oauth2_provider.models import Application, AccessToken
from testbed.core.models import Actor
from testbed.core.factories import ActorFactory, ApplicationFactory, AccessTokenFactory
from testbed.core.tests.conftest import create_isolated_actor
from testbed.core.json_ld_utils import (
    build_basic_context,
    build_actor_context,
    build_actor_id,
    build_outbox_id,
)

User = get_user_model()

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


# LOLA Authentication Tests

"""
Tests the complete request-response cycle with different authentication states
to verify that endpoints properly serve enhanced data for LOLA-authenticated requests.
"""
class TestLOLAAuthenticationAPI:
    # Constants for OAuth scopes
    LOLA_SCOPE = 'activitypub_account_portability read write'
    BASIC_SCOPE = 'read write'
    
    # Helper methods for repeated assertions

    # Helper to verify standard ActivityPub fields
    def assert_basic_activitypub_structure(self, data, actor):
        assert data["@context"] == build_actor_context()
        assert data["type"] == "Person"
        assert data["id"] == build_actor_id(actor.id)
        assert data["preferredUsername"] == actor.username
        
    # Helper to verify LOLA fields are absent
    def assert_no_lola_fields(self, data):
        lola_fields = ["accountPortabilityOauth", "content", "blocked", "migration"]
        for field in lola_fields:
            assert field not in data
            
    # Helper to verify LOLA fields are present and properly formatted        
    def assert_has_lola_fields(self, data, actor):
        assert "accountPortabilityOauth" in data
        assert "content" in data
        assert "blocked" in data
        assert "migration" in data
        
        # Verify LOLA URLs are properly formatted
        assert data["accountPortabilityOauth"].endswith("/oauth/authorize/")
        assert data["content"].endswith(f"/actors/{actor.id}/content")
        assert data["blocked"].endswith(f"/actors/{actor.id}/blocked")
        assert data["migration"].endswith(f"/actors/{actor.id}/outbox")
        
    # Helper to create authenticated client    
    def get_authenticated_client(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')
        return client
    
    # Test that unauthenticated requests return basic ActivityPub data only
    @pytest.mark.django_db
    def test_actor_detail_unauthenticated_returns_basic_activitypub(self):
        actor = create_isolated_actor("unauthenticated_test")
        client = APIClient()
        
        response = client.get(reverse("actor-detail", kwargs={"pk": actor.id}))
        
        # Should succeed with basic ActivityPub response
        assert response.status_code == status.HTTP_200_OK
        
        data = response.data
        # Use helper methods for assertions
        self.assert_basic_activitypub_structure(data, actor)
        self.assert_no_lola_fields(data)
    
    # Test that LOLA-authenticated requests return enhanced data with collection URLs
    @pytest.mark.django_db
    def test_actor_detail_with_lola_scope_returns_enhanced_data(self):
        actor = create_isolated_actor("lola_enhanced_test")
        lola_token = AccessTokenFactory(lola_scope=True)
        client = self.get_authenticated_client(lola_token)
        
        response = client.get(reverse("actor-detail", kwargs={"pk": actor.id}))
        
        # Should succeed with enhanced response
        assert response.status_code == status.HTTP_200_OK
        
        data = response.data
        # Use helper methods for assertions
        self.assert_basic_activitypub_structure(data, actor)
        self.assert_has_lola_fields(data, actor)
    
    # Test that authenticated requests without LOLA scope return basic data
    @pytest.mark.django_db
    def test_actor_detail_with_basic_token_returns_basic_data(self):
        actor = create_isolated_actor("basic_token_test")
        basic_token = AccessTokenFactory(scope=self.BASIC_SCOPE)
        client = self.get_authenticated_client(basic_token)
        
        response = client.get(reverse("actor-detail", kwargs={"pk": actor.id}))
        
        # Should succeed but return basic data (no LOLA scope)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.data
        # Use helper methods for assertions
        self.assert_basic_activitypub_structure(data, actor)
        self.assert_no_lola_fields(data)
    
    # Test that URL parameter authentication works for LOLA testing
    @pytest.mark.django_db
    def test_actor_detail_url_parameter_authentication(self):
        actor = create_isolated_actor("url_param_test")
        lola_token = AccessTokenFactory(lola_scope=True)
        client = APIClient()
        
        # Use auth_token URL parameter instead of Authorization header
        url = reverse("actor-detail", kwargs={"pk": actor.id})
        response = client.get(f"{url}?auth_token={lola_token.token}")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.data
        # Should have LOLA fields (proves URL parameter auth worked)
        self.assert_has_lola_fields(data, actor)
    
    # Test that outbox shows different content based on authentication
    @pytest.mark.django_db
    def test_outbox_content_filtering_by_authentication(self):
        actor = create_isolated_actor("outbox_filtering_test")
        lola_token = AccessTokenFactory(lola_scope=True)
        client = APIClient()
        
        # Test unauthenticated outbox (public activities only)
        public_response = client.get(reverse("actor-outbox", kwargs={"pk": actor.id}))
        assert public_response.status_code == status.HTTP_200_OK
        
        public_data = public_response.data
        public_count = public_data["totalItems"]
        
        # Test LOLA-authenticated outbox (all activities)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {lola_token.token}')
        lola_response = client.get(reverse("actor-outbox", kwargs={"pk": actor.id}))
        assert lola_response.status_code == status.HTTP_200_OK
        
        lola_data = lola_response.data
        lola_count = lola_data["totalItems"]
        
        # Both should have valid outbox structure
        assert public_data["@context"] == build_basic_context()
        assert public_data["type"] == "OrderedCollection"
        assert lola_data["@context"] == build_basic_context()
        assert lola_data["type"] == "OrderedCollection"
        
        # LOLA version should show >= public count (includes private activities)
        assert lola_count >= public_count
        
        # Both should have proper outbox ID
        expected_outbox_id = build_outbox_id(actor.id)
        assert public_data["id"] == expected_outbox_id
        assert lola_data["id"] == expected_outbox_id
    
    # Test that demonstrates clear differences between public and LOLA responses
    @pytest.mark.django_db
    def test_side_by_side_authentication_comparison(self):
        actor = create_isolated_actor("comparison_test")
        lola_token = AccessTokenFactory(lola_scope=True)
        
        # Public request
        public_client = APIClient()
        public_response = public_client.get(reverse("actor-detail", kwargs={"pk": actor.id}))
        public_data = public_response.data
        
        # LOLA request
        lola_client = self.get_authenticated_client(lola_token)
        lola_response = lola_client.get(reverse("actor-detail", kwargs={"pk": actor.id}))
        lola_data = lola_response.data
        
        # Both should succeed
        assert public_response.status_code == status.HTTP_200_OK
        assert lola_response.status_code == status.HTTP_200_OK
        
        # Both should have identical basic fields
        basic_fields = ["@context", "type", "id", "preferredUsername", "name", "previously"]
        for field in basic_fields:
            assert public_data[field] == lola_data[field]
        
        # Only LOLA should have enhanced fields
        lola_fields = ["accountPortabilityOauth", "content", "blocked", "migration"]
        for field in lola_fields:
            assert field not in public_data
            assert field in lola_data
            assert isinstance(lola_data[field], str)  # Should be URL strings
    
    # Test that invalid tokens gracefully degrade to unauthenticated behavior
    @pytest.mark.django_db
    def test_invalid_token_graceful_degradation(self):
        actor = create_isolated_actor("invalid_token_test")
        client = APIClient()
        
        # Use completely invalid token
        client.credentials(HTTP_AUTHORIZATION='Bearer invalid-nonexistent-token-xyz')
        response = client.get(reverse("actor-detail", kwargs={"pk": actor.id}))
        
        # Should succeed with public data (graceful degradation)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.data
        assert data["type"] == "Person"
        # Should NOT have LOLA fields (invalid token treated as unauthenticated)
        assert "accountPortabilityOauth" not in data
        assert "content" not in data
        assert "blocked" not in data
    
    # Test graceful handling of malformed authorization headers
    @pytest.mark.parametrize("malformed_header", [
        "Bearer",  # Missing token
        "Basic invalid-format",  # Wrong auth type
        "Bearer  ",  # Empty token
        "InvalidFormat token",  # Malformed header
    ])
    @pytest.mark.django_db
    def test_malformed_authorization_header_handling(self, malformed_header):
        actor = create_isolated_actor("malformed_header_test")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=malformed_header)
        
        response = client.get(reverse("actor-detail", kwargs={"pk": actor.id}))
        
        # Should succeed with public data for all malformed cases
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        self.assert_basic_activitypub_structure(data, actor)
        self.assert_no_lola_fields(data)
    
    # Test that content-type headers are set correctly for API responses
    @pytest.mark.django_db
    def test_content_type_headers_set_correctly(self):
        actor = create_isolated_actor("content_type_test")
        lola_token = AccessTokenFactory(lola_scope=True)
        client = self.get_authenticated_client(lola_token)
        
        # Request with format=json 
        response = client.get(reverse("actor-detail", kwargs={"pk": actor.id}), {"format": "json"})
        
        assert response.status_code == status.HTTP_200_OK
        # Should have JSON content type (DRF default for format=json)
        assert response["Content-Type"] == "application/json"
        # Should have CORS header for federation
        assert response["Access-Control-Allow-Origin"] == "*"
        
        # Should still have LOLA fields
        data = response.data
        assert "accountPortabilityOauth" in data
