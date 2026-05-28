import base64
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import Client
from django.urls import reverse

from oauth2_provider.models import Application, get_access_token_model

from testbed.core.factories import AccessTokenFactory, UserWithActorsFactory
from testbed.core.models import Actor, TokenActorBinding
from testbed.core.oauth.views import ACTIVITYPUB_ACTOR_PARAM

LOLA_SCOPE = "activitypub_account_portability"
REDIRECT_URI = "https://destination.example/callback"


def _make_application(owner, *, skip_authorization=False, client_secret="test-secret"):
    # Create a confidential authorization-code application registered for the LOLA redirect URI.
    return Application.objects.create(
        name="Destination Service",
        user=owner,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris=REDIRECT_URI,
        skip_authorization=skip_authorization,
        client_secret=client_secret,
    )


def _authorize_params(application, *, scope=LOLA_SCOPE, state="state-xyz", **extra):
    # Standard query/form params for an authorization request
    params = {
        "client_id": application.client_id,
        "response_type": "code",
        "scope": scope,
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }
    params.update(extra)
    return params


def _redirect_query(response):
    # Parse the query dict out of a redirect response's Location header
    location = response["Location"]
    return parse_qs(urlparse(location).query)


# 1. form_valid (POST approval) path


@pytest.mark.django_db
def test_form_valid_redirect_includes_activitypub_actor():
    # POST approval redirect carries code, state, and activitypub_actor
    user = UserWithActorsFactory()
    source_actor = user.actors.get(role=Actor.ROLE_SOURCE)
    application = _make_application(user)

    client = Client()
    client.force_login(user)

    form_data = _authorize_params(application)
    form_data["allow"] = "True"
    response = client.post(reverse("oauth2_provider:authorize"), data=form_data)

    assert response.status_code == 302
    query = _redirect_query(response)

    assert "code" in query
    assert query["state"] == ["state-xyz"]

    assert ACTIVITYPUB_ACTOR_PARAM in query
    actor_url = query[ACTIVITYPUB_ACTOR_PARAM][0]
    assert actor_url.startswith("http")
    assert actor_url.endswith(f"/api/actors/{source_actor.pk}/")


@pytest.mark.django_db
def test_form_valid_denied_authorization_has_no_actor():
    # A denied authorization is an error redirect, no actor URL
    user = UserWithActorsFactory()
    application = _make_application(user)

    client = Client()
    client.force_login(user)

    form_data = _authorize_params(application)
    response = client.post(reverse("oauth2_provider:authorize"), data=form_data)

    assert response.status_code == 302
    query = _redirect_query(response)
    assert "error" in query
    assert ACTIVITYPUB_ACTOR_PARAM not in query


# 2. skip_authorization branch (GET)


@pytest.mark.django_db
def test_skip_authorization_redirect_includes_activitypub_actor():
    # GET with skip_authorization app redirects with activitypub_actor
    user = UserWithActorsFactory()
    source_actor = user.actors.get(role=Actor.ROLE_SOURCE)
    application = _make_application(user, skip_authorization=True)

    client = Client()
    client.force_login(user)

    response = client.get(
        reverse("oauth2_provider:authorize"), data=_authorize_params(application)
    )

    assert response.status_code == 302
    query = _redirect_query(response)
    assert "code" in query
    assert query["state"] == ["state-xyz"]
    assert query[ACTIVITYPUB_ACTOR_PARAM][0].endswith(
        f"/api/actors/{source_actor.pk}/"
    )


# 3. approval_prompt


@pytest.mark.django_db
def test_auto_approval_redirect_includes_activitypub_actor():
    # GET with approval_prompt=auto reuses a prior matching access token and redirects without a form, still carrying activitypub_actor
    
    user = UserWithActorsFactory()
    source_actor = user.actors.get(role=Actor.ROLE_SOURCE)
    application = _make_application(user)

    client = Client()
    client.force_login(user)

    AccessTokenFactory(user=user, application=application, lola_scope=True)

    response = client.get(
        reverse("oauth2_provider:authorize"),
        data=_authorize_params(application, approval_prompt="auto"),
    )

    assert response.status_code == 302
    query = _redirect_query(response)
    assert "code" in query
    assert query[ACTIVITYPUB_ACTOR_PARAM][0].endswith(
        f"/api/actors/{source_actor.pk}/"
    )


# Non-LOLA scope: regular OAuth untouched


@pytest.mark.django_db
def test_non_portability_scope_redirect_has_no_actor(settings):
    # An authorization without the portability scope must not get activitypub_actor, so regular OAuth flows are unaffected.
    settings.OAUTH2_PROVIDER = {
        **settings.OAUTH2_PROVIDER,
        "SCOPES": {**settings.OAUTH2_PROVIDER["SCOPES"], "read": "Read access"},
    }

    user = UserWithActorsFactory()
    application = _make_application(user)

    client = Client()
    client.force_login(user)

    form_data = _authorize_params(application, scope="read")
    form_data["allow"] = "True"
    response = client.post(reverse("oauth2_provider:authorize"), data=form_data)

    assert response.status_code == 302
    query = _redirect_query(response)
    assert ACTIVITYPUB_ACTOR_PARAM not in query


# Security: actor comes from the approving user, never the client/app owner


@pytest.mark.django_db
def test_actor_is_resolved_from_approving_user_not_app_owner():
    """
    The redirect actor must be the approving (logged-in) user's source actor,
    not the source actor of whoever registered the destination application.
    """
    app_owner = UserWithActorsFactory()
    approving_user = UserWithActorsFactory()
    approving_source = approving_user.actors.get(role=Actor.ROLE_SOURCE)
    app_owner_source = app_owner.actors.get(role=Actor.ROLE_SOURCE)

    application = _make_application(app_owner)

    client = Client()
    client.force_login(approving_user)

    form_data = _authorize_params(application)
    form_data["allow"] = "True"
    response = client.post(reverse("oauth2_provider:authorize"), data=form_data)

    query = _redirect_query(response)
    actor_url = query[ACTIVITYPUB_ACTOR_PARAM][0]
    assert actor_url.endswith(f"/api/actors/{approving_source.pk}/")
    assert not actor_url.endswith(f"/api/actors/{app_owner_source.pk}/")


# Alignment: redirect actor == token-bound actor (end-to-end)


@pytest.mark.django_db
def test_redirect_actor_matches_token_bound_actor():
    """
    End-to-end: the activitypub_actor in the approval redirect identifies the
    same Actor the issued token is bound to via TokenActorBinding (LOLA §5).
    """
    user = UserWithActorsFactory()
    source_actor = user.actors.get(role=Actor.ROLE_SOURCE)
    client_secret = "exchange-secret"
    application = _make_application(user, client_secret=client_secret)

    client = Client()
    client.force_login(user)

    # Approve and capture both code and the redirect actor URL.
    form_data = _authorize_params(application)
    form_data["allow"] = "True"
    approve = client.post(reverse("oauth2_provider:authorize"), data=form_data)
    query = _redirect_query(approve)
    code = query["code"][0]
    redirect_actor_url = query[ACTIVITYPUB_ACTOR_PARAM][0]

    # Exchange the code for a token (confidential client -> HTTP Basic auth).
    basic = base64.b64encode(
        f"{application.client_id}:{client_secret}".encode()
    ).decode()
    token_response = client.post(
        reverse("oauth2_provider:token"),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        HTTP_AUTHORIZATION=f"Basic {basic}",
    )

    assert token_response.status_code == 200
    access_token_str = token_response.json()["access_token"]

    access_token = get_access_token_model().objects.get(token=access_token_str)
    binding = TokenActorBinding.objects.get(token=access_token)

    # Binding actor and redirect actor are the same source actor.
    assert binding.actor_id == source_actor.pk
    assert redirect_actor_url.endswith(f"/api/actors/{binding.actor_id}/")
