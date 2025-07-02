import pytest
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from oauth2_provider.models import get_application_model
from testbed.core.utils.oauth_validators import ActivityPubOAuth2Validator

User = get_user_model()
Application = get_application_model()


# The validator must ensure that clients request the appropriate scopes and use registered redirect URI

# Creates an instance of custom validator
@pytest.fixture
def oauth_validator():
    return ActivityPubOAuth2Validator()

# Represents a client service registered with the testbed
@pytest.fixture
def oauth_application(user):
    return Application.objects.create(
        name='Test ActivityPub Service',
        user=user,
        client_type='confidential',
        authorization_grant_type='authorization-code',
        client_id='test-client-id',
        client_secret='test-client-secret',
        redirect_uris='https://example.com/callback'
    )

# Simulates the client making the request
@pytest.fixture
def oauth_client():
    client = MagicMock()
    client.client_id = 'test-client-id'
    return client

# Simulates the HTTP request in the OAuth flow
@pytest.fixture
def mock_request():
    return MagicMock()

# Test that validator accepts the activitypub_account_portability scope
# The destination service must request this specific scope to indicate it wants to perform account portability operations
@pytest.mark.django_db
def test_validate_scopes_with_valid_scope(oauth_validator, oauth_application, oauth_client, mock_request):  
    scopes = ['activitypub_account_portability']
    result = oauth_validator.validate_scopes(
        oauth_application.client_id, 
        scopes, 
        oauth_client, 
        mock_request
    )
    assert result, "The validator should accept the activitypub_account_portability scope"

# Test that validator rejects empty scopes
@pytest.mark.django_db
def test_validate_scopes_with_no_scopes(oauth_validator, oauth_application, oauth_client, mock_request):
    scopes = []
    result = oauth_validator.validate_scopes(
        oauth_application.client_id, 
        scopes, 
        oauth_client, 
        mock_request
    )
    assert not result, "The validator should reject empty scopes"

# Test that validator rejects scopes without activitypub_account_portability
# This prevents services from using our OAuth endpoints for purposes other than account portability
@pytest.mark.django_db
def test_validate_scopes_with_invalid_scopes(oauth_validator, oauth_application, oauth_client, mock_request):
    scopes = ['read', 'write']
    result = oauth_validator.validate_scopes(
        oauth_application.client_id, 
        scopes, 
        oauth_client, 
        mock_request
    )
    assert not result, "The validator should reject scopes without activitypub_account_portability"

# Test that validator accepts a valid redirect URI
@pytest.mark.django_db
def test_validate_redirect_uri_with_valid_uri(oauth_validator, oauth_application, mock_request):
    with patch.object(oauth_validator.__class__.__bases__[0], 'validate_redirect_uri', return_value=True):
        result = oauth_validator.validate_redirect_uri(
            oauth_application.client_id,
            'https://example.com/callback',
            mock_request
        )
        assert result, "The validator should accept a valid redirect URI"

# Test that validator rejects an invalid redirect URI
# When a user authorizes a destination service, the authorization code must only be sent to
# the destination's registered redirect URL to prevent malicious services from intercepting the flow.
@pytest.mark.django_db
def test_validate_redirect_uri_with_invalid_uri(oauth_validator, oauth_application, mock_request):
    
    with patch.object(oauth_validator.__class__.__bases__[0], 'validate_redirect_uri', return_value=False):
        result = oauth_validator.validate_redirect_uri(
            oauth_application.client_id,
            'https://malicious-site.com/callback',
            mock_request
        )
        assert not result, "The validator should reject an invalid redirect URI"
