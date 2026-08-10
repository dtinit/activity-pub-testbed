"""
OAuth application settings form.
"""

import pytest

from django.conf import settings
from django.test import override_settings

from testbed.core.oauth.forms import OAuthApplicationForm


DEFAULT_POLICY = settings.OAUTH2_PROVIDER
HTTPS_ONLY = {**settings.OAUTH2_PROVIDER, "ALLOWED_REDIRECT_URI_SCHEMES": ["https"]}


def _redirect_uri_errors(uri):
    # Bind the form with `uri` and return its redirect_uris error messages
    form = OAuthApplicationForm(
        data={
            "name": "Test ActivityPub Service",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "redirect_uris": uri,
        }
    )
    form.is_valid()
    return form.errors.get("redirect_uris", [])


# The scheme policy is per environment, so the same URI is valid or not
# depending on which settings module is active.
@pytest.mark.parametrize(
    "policy, uri, expected_message_fragment",
    [
        # Local development and CI register http://localhost callbacks.
        (DEFAULT_POLICY, "http://localhost:8000/callback", None),
        # If eberything is rejected it would break local development
        (HTTPS_ONLY, "https://example.com/callback", None),
        # With production policy http must be refused.
        (HTTPS_ONLY, "http://example.com/callback", "https://"),
    ],
)
@pytest.mark.django_db
def test_redirect_uri_scheme_policy_per_environment(policy, uri, expected_message_fragment):
    with override_settings(OAUTH2_PROVIDER=policy):
        errors = _redirect_uri_errors(uri)

    if expected_message_fragment is None:
        assert errors == [], f"{uri} should be accepted under this policy"
        return

    assert errors, f"{uri} should be rejected under this policy"
    # The message must describe the actual policy
    assert expected_message_fragment in errors[0]
    assert "http:// or" not in errors[0]
