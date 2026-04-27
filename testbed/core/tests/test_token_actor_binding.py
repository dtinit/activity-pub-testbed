import pytest
from unittest.mock import MagicMock, patch

from django.db import IntegrityError
from django.test import RequestFactory
from django.urls import reverse

from oauth2_provider.oauth2_validators import OAuth2Validator
from rest_framework import status
from rest_framework.test import APIClient

from testbed.core.factories import (
    AccessTokenFactory,
    TokenActorBindingFactory,
    UserOnlyFactory,
)
from testbed.core.models import Actor, TokenActorBinding
from testbed.core.oauth.validators import ActivityPubOAuth2Validator
from testbed.core.views.decorators import validate_lola_access


# Model

@pytest.mark.django_db
def test_one_token_one_binding_enforced():
    """OneToOneField prevents a second binding for the same token."""
    binding = TokenActorBindingFactory()

    other_user = UserOnlyFactory()
    other_actor = Actor.objects.create(
        user=other_user,
        username=f"{other_user.username}_src",
        role=Actor.ROLE_SOURCE,
    )

    with pytest.raises(IntegrityError):
        TokenActorBinding.objects.create(token=binding.token, actor=other_actor)


# Validator

@pytest.mark.django_db
def test_validator_creates_binding_for_portability_token():
    """_save_bearer_token creates a TokenActorBinding for portability-scoped tokens."""
    user = UserOnlyFactory()
    # Use the source Actor the post_save signal auto-created for this user.
    # _resolve_bound_actor's fallback path does Actor.objects.get(user=...,
    # role=ROLE_SOURCE) and requires exactly one source actor per user.
    actor = user.actors.get(role=Actor.ROLE_SOURCE)
    access_token = AccessTokenFactory(user=user, lola_scope=True)

    mock_request = MagicMock()
    mock_request.user = user
    # MagicMock auto-creates attributes, which would push _resolve_bound_actor
    # into the preferred-id branch. Force the fallback path explicitly.
    mock_request.activitypub_bound_actor_id = None

    token_dict = {"access_token": access_token.token, "scope": access_token.scope}

    validator = ActivityPubOAuth2Validator()

    # Patch super() — AccessToken already exists, avoid duplicate creation.
    with patch.object(OAuth2Validator, "_save_bearer_token"):
        validator._save_bearer_token(token_dict, mock_request)

    assert TokenActorBinding.objects.filter(token=access_token, actor=actor).exists()


@pytest.mark.django_db
def test_validator_skips_binding_for_non_portability_token():
    """_save_bearer_token does not create a binding for tokens without portability scope."""
    user = UserOnlyFactory()
    # The signal already created a source actor; don't duplicate it.
    user.actors.get(role=Actor.ROLE_SOURCE)
    access_token = AccessTokenFactory(user=user, scope="read write")

    mock_request = MagicMock()
    mock_request.user = user
    mock_request.activitypub_bound_actor_id = None

    token_dict = {"access_token": access_token.token, "scope": "read write"}

    validator = ActivityPubOAuth2Validator()

    with patch.object(OAuth2Validator, "_save_bearer_token"):
        validator._save_bearer_token(token_dict, mock_request)

    assert not TokenActorBinding.objects.filter(token=access_token).exists()


# Decorator

def _make_lola_request(actor, token):
    """Build a fake request with portability scope targeting the given actor pk."""
    rf = RequestFactory()
    request = rf.get(f"/api/actors/{actor.pk}/followers/")
    request.is_oauth_authenticated = True
    request.has_portability_scope = True
    request.auth = token
    request.resolver_match = MagicMock()
    request.resolver_match.kwargs = {"pk": actor.pk}
    return request


@pytest.mark.django_db
def test_same_actor_access_succeeds():
    """Token bound to actor A may access actor A."""
    binding = TokenActorBindingFactory()
    request = _make_lola_request(binding.actor, binding.token)

    result = validate_lola_access(request)
    assert result["valid"] is True


@pytest.mark.django_db
def test_cross_actor_access_denied():
    """Token bound to actor A is rejected when accessing actor B."""
    binding = TokenActorBindingFactory()

    user_b = UserOnlyFactory()
    actor_b = Actor.objects.create(
        user=user_b, username=f"{user_b.username}_src", role=Actor.ROLE_SOURCE
    )

    rf = RequestFactory()
    request = rf.get(f"/api/actors/{actor_b.pk}/followers/")
    request.is_oauth_authenticated = True
    request.has_portability_scope = True
    request.auth = binding.token
    request.resolver_match = MagicMock()
    request.resolver_match.kwargs = {"pk": actor_b.pk}

    result = validate_lola_access(request)
    assert result["valid"] is False
    assert result["error_response"].status_code == 403
    assert result["error_response"].data["error_code"] == "actor_mismatch"


@pytest.mark.django_db
def test_unbound_token_denied():
    """A portability token with no binding row is rejected (fail closed)."""
    user = UserOnlyFactory()
    actor = Actor.objects.create(
        user=user, username=f"{user.username}_src", role=Actor.ROLE_SOURCE
    )
    token = AccessTokenFactory(user=user, lola_scope=True)
    # Intentionally: no TokenActorBinding created.

    request = _make_lola_request(actor, token)

    result = validate_lola_access(request)
    assert result["valid"] is False
    assert result["error_response"].status_code == 403
    assert result["error_response"].data["error_code"] == "actor_mismatch"


@pytest.mark.django_db
def test_missing_url_pk_fails_closed():
    """A LOLA request without a URL pk is rejected (fail closed, no silent skip)."""
    binding = TokenActorBindingFactory()

    rf = RequestFactory()
    request = rf.get("/api/unexpected/")
    request.is_oauth_authenticated = True
    request.has_portability_scope = True
    request.auth = binding.token
    request.resolver_match = MagicMock()
    request.resolver_match.kwargs = {}  # no "pk" key

    result = validate_lola_access(request)
    assert result["valid"] is False
    assert result["error_response"].status_code == 403
    assert result["error_response"].data["error_code"] == "actor_mismatch"


# Integration

@pytest.mark.django_db
def test_bearer_same_actor_succeeds():
    """End-to-end: Bearer token bound to actor A can access actor A's followers."""
    binding = TokenActorBindingFactory()

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {binding.token.token}")
    response = client.get(
        reverse("followers-collection", kwargs={"pk": binding.actor.pk})
    )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_bearer_cross_actor_denied():
    """End-to-end: Bearer token bound to actor A cannot access actor B's followers."""
    binding = TokenActorBindingFactory()

    user_b = UserOnlyFactory()
    actor_b = Actor.objects.create(
        user=user_b, username=f"{user_b.username}_src", role=Actor.ROLE_SOURCE
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {binding.token.token}")
    response = client.get(
        reverse("followers-collection", kwargs={"pk": actor_b.pk})
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["error_code"] == "actor_mismatch"
