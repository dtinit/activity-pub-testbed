"""
Direct tests for the demo session token helpers in oauth/utils.py.

These cover the NON-NORMATIVE session credential path. LOLA §5 makes the
Authorization header the normative one:
"This header MUST be included in feature discovery and data access requests".
The session path exists only so the demo browser can follow a collection link without re-sending a header.
"""

import pytest
from django.test import RequestFactory

from testbed.core.oauth.authentication import OptionalOAuth2Authentication
from testbed.core.oauth.utils import (
    DEMO_ACCESS_TOKEN_SESSION_KEY,
    store_demo_session_token,
)


@pytest.fixture
def demo_session_request():
    request = RequestFactory().get("/api/actors/1/")
    request.session = {}

    return request


# Storing a token response that includes a scope must not persist the scope.
# The authoritative scope is AccessToken.scope, read through oauth/scopes.py;
# a copy in the client-held session would be a second, unverified source of truth.
def test_only_the_token_string_is_persisted(demo_session_request):
    store_demo_session_token(
        demo_session_request,
        {
            "access_token": "demo-token",
            "scope": "activitypub_account_portability read write",
            "expires_in": 3600,
        },
    )

    # Asserting the exact key set, not just the absence of a scope key, so any
    # future stray write to the session fails this test too.
    assert list(demo_session_request.session) == [DEMO_ACCESS_TOKEN_SESSION_KEY]


# read_demo_session_token returns whatever string the session holds without
# validating it, so the fail-closed guarantee has to live in the auth class.
# A token with no database row must be refused and evicted, so a dead token is
# not re-checked on every later request from that browser.
@pytest.mark.django_db
def test_unknown_token_is_refused_and_evicted(demo_session_request):
    store_demo_session_token(demo_session_request, {"access_token": "no-such-token"})

    result = OptionalOAuth2Authentication()._try_session_auth(demo_session_request)

    assert result is None
    assert demo_session_request.session == {}
