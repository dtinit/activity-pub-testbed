import random

from rest_framework.test import APIClient

from testbed.core.factories import (
    AccessTokenFactory,
    FollowActivityFactory,
    LikeActivityFactory,
    TokenActorBindingFactory,
    UserOnlyFactory,
    UserWithActorsFactory,
)
from testbed.core.models import Actor


# Actor construction


def create_isolated_actor(username_prefix, role=None):
    role = role or Actor.ROLE_SOURCE
    user = UserOnlyFactory(username=f"{username_prefix}_user")
    return Actor.objects.create(
        user=user,
        username=f"{username_prefix}_actor",
        role=role
    )


def _actor_for(user, role):
    user = user or UserWithActorsFactory()
    return user.actors.get(role=role)


def source_actor_for(user=None):
    return _actor_for(user, Actor.ROLE_SOURCE)


def destination_actor_for(user=None):
    return _actor_for(user, Actor.ROLE_DESTINATION)


# Portability tokens and authenticated clients


def bind_portability_token(actor, user=None):
    """
    Create a portability token bound to an actor.

    Both the strict and the dual-mode LOLA endpoints enforce token-to-actor binding.

    When `user` is given, the token is issued for that user so token.user matches actor.user;
    otherwise the factory creates a fresh token user. Only the token<->actor binding is what
    lola_access_error() checks, so both shapes satisfy the gate.
    """
    if user is not None:
        token = AccessTokenFactory(lola_scope=True, user=user)
        TokenActorBindingFactory(token=token, actor=actor)
        return token
    return TokenActorBindingFactory(actor=actor).token


def lola_client(actor, user=None):
    """
    An `APIClient` carrying a LOLA-scoped bearer token already bound to `actor`.

    This is the happy path only - a valid, correctly scoped, correctly bound credential.

    `user` is forwarded to `bind_portability_token()` for the cases needing the token issued to the
    actor's own user rather than a fresh one.
    """
    token = bind_portability_token(actor, user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.token}")
    return client


# Remote-object activities


def create_isolated_remote_like(username_prefix="remote_like_test"):
    # Creates a LikeActivity for a remote object with an isolated actor
    actor = create_isolated_actor(username_prefix)
    return LikeActivityFactory(
        actor=actor,
        note=None,
        object_url=f"https://remote.example/notes/{random.randint(1000, 9999)}",
        object_data={"content": "Remote note content"},
        visibility="public"
    )


def create_isolated_remote_follow(username_prefix="remote_follow_test"):
    # Creates a FollowActivity for a remote actor with an isolated actor
    actor = create_isolated_actor(username_prefix)
    return FollowActivityFactory(
        actor=actor,
        target_actor=None,
        target_actor_url=f"https://remote.example/users/user_{random.randint(1000, 9999)}",
        target_actor_data={"preferredUsername": f"remote_user_{random.randint(1000, 9999)}"},
        visibility="public"
    )
