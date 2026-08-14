import pytest
from unittest.mock import MagicMock, patch

from django.conf import settings

from testbed.core.factories import ApplicationFactory
from testbed.core.oauth.scopes import LOLA_PORTABILITY_SCOPE, scope_grants_portability
from testbed.core.oauth.validators import ActivityPubOAuth2Validator


# The validator must ensure that clients request the appropriate scopes and use registered redirect URI

# Creates an instance of custom validator
@pytest.fixture
def oauth_validator():
    return ActivityPubOAuth2Validator()

# Represents a client service registered with the testbed
@pytest.fixture
def oauth_application(user):
    return ApplicationFactory(
        user=user,
        name='Test ActivityPub Service',
        redirect_uris='https://example.com/callback'
    )

# Simulates the client making the request
@pytest.fixture
def oauth_client(oauth_application):
    # client_id is read back from the application because the factory generates it,
    # so the mock cannot drift from the registered client.
    client = MagicMock()
    client.client_id = oauth_application.client_id
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

# scope_grants_portability() is the single membership test behind all four LOLA scope decisions,
# so it has to give the same answer for every shape the OAuth flow produces.
@pytest.mark.parametrize(
    "scopes, expected",
    [
        # Shapes that DO grant portability
        ([LOLA_PORTABILITY_SCOPE], True),
        (LOLA_PORTABILITY_SCOPE, True),
        (f"{LOLA_PORTABILITY_SCOPE} read write", True),
        ([LOLA_PORTABILITY_SCOPE, "read"], True),
        (f"  {LOLA_PORTABILITY_SCOPE}  read ", True),
        # Shapes that do NOT
        (None, False),
        ("", False),
        ([], False),
        ("read write", False),
        (["read", "write"], False),
    ],
)
def test_scope_grants_portability_across_input_shapes(scopes, expected):
    assert scope_grants_portability(scopes) is expected


# A scope whose name merely CONTAINS the portability scope must not pass.

"""
This guard matters because the shapes reaching validate_scopes are normalized by django-oauth-toolkit,
not by us: DOT's OAuthLibMixin does # `scopes.split(" ")` on a line carrying a "TO DO: move this scopes conversion" comment.

If a future DOT release drops that, this test fails here rather than silently widening the LOLA gate.
"""
@pytest.mark.parametrize(
    "lookalike",
    [
        f"{LOLA_PORTABILITY_SCOPE}_admin",                 # suffix, as a string
        [f"{LOLA_PORTABILITY_SCOPE}_admin"],               # suffix, as a list
        f"x{LOLA_PORTABILITY_SCOPE}",                      # prefix
        f"{LOLA_PORTABILITY_SCOPE}_admin read",            # suffix alongside a real token
    ],
)
def test_lookalike_scope_is_rejected(lookalike):
    assert scope_grants_portability(lookalike) is False


# The scope literal in OAUTH2_PROVIDER["SCOPES"] cannot import LOLA_PORTABILITY_SCOPE
# so the two are kept in sync by this guard instead.
def test_settings_scope_registry_matches_constant():
    assert LOLA_PORTABILITY_SCOPE in settings.OAUTH2_PROVIDER["SCOPES"], (
        "OAUTH2_PROVIDER['SCOPES'] must advertise the scope LOLA_PORTABILITY_SCOPE names "
        "(LOLA Section 5: the advertised endpoint MUST support this scope)"
    )

# The lookalike must be rejected by OUR check, not incidentally by DOT.
@pytest.mark.django_db
def test_validate_scopes_rejects_lookalike_scope(oauth_validator, oauth_application, oauth_client, mock_request):
    with patch.object(oauth_validator.__class__.__bases__[0], 'validate_scopes', return_value=True):
        result = oauth_validator.validate_scopes(
            oauth_application.client_id,
            [f"{LOLA_PORTABILITY_SCOPE}_admin"],
            oauth_client,
            mock_request
        )
    assert not result, "A scope that merely contains the portability scope must not be accepted"
