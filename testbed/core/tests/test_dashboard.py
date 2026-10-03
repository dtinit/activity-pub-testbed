import base64

import pytest
from django.urls import reverse
from oauth2_provider.models import Application

from testbed.core.oauth.utils import get_user_application
from testbed.core.tests.helpers import source_actor_for

# The secret the dashboard form shows must be one a destination can authenticate with.
@pytest.mark.django_db
def test_dashboard_shows_a_client_secret_that_authenticates(client):
    user = source_actor_for().user
    client.force_login(user)

    page = client.get(reverse("home"))
    secret = page.context["oauth_form"]["client_secret"].value()
    client_id = Application.objects.get(user=user).client_id

    assert secret in page.content.decode()
    assert "no-store" in page["Cache-Control"]

    credentials = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    exchange = client.post(
        reverse("oauth2_provider:token"),
        {"grant_type": "authorization_code", "code": "made-up", "redirect_uri": "http://localhost/callback"},
        HTTP_AUTHORIZATION=f"Basic {credentials}",
    )

    # The client authenticated, only the made-up code was refused
    assert exchange.json()["error"] == "invalid_grant"


# A client secret is shown to its owner and to nobody else
@pytest.mark.django_db
def test_dashboard_never_shows_another_users_client_secret(client):
    owner, other = source_actor_for().user, source_actor_for().user
    owners_secret = get_user_application(owner).raw_client_secret
    client.force_login(other)

    assert owners_secret not in client.get(reverse("home")).content.decode()
