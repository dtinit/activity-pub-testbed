import io
import json as json_lib
import random

from requests import Response
from requests.structures import CaseInsensitiveDict
from rest_framework.test import APIClient
from urllib3.response import HTTPResponse

from testbed.core.factories import (
    AccessTokenFactory,
    FollowActivityFactory,
    IsolatedActorFactory,
    LikeActivityFactory,
    TokenActorBindingFactory,
    UserWithActorsFactory,
)
from testbed.core.models import Actor


# Actor construction


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
    actor = IsolatedActorFactory(prefix=username_prefix)
    return LikeActivityFactory(
        actor=actor,
        note=None,
        object_url=f"https://remote.example/notes/{random.randint(1000, 9999)}",
        object_data={"content": "Remote note content"},
        visibility="public"
    )


def create_isolated_remote_follow(username_prefix="remote_follow_test"):
    # Creates a FollowActivity for a remote actor with an isolated actor
    actor = IsolatedActorFactory(prefix=username_prefix)
    return FollowActivityFactory(
        actor=actor,
        target_actor=None,
        target_actor_url=f"https://remote.example/users/user_{random.randint(1000, 9999)}",
        target_actor_data={"preferredUsername": f"remote_user_{random.randint(1000, 9999)}"},
        visibility="public"
    )


# A source server on the other side of transfer/transport.py


class FakeSource:
    """
    A source server that answers from a script, in place of the network.

    `respond()` queues a response and `fail()` queues an exception, answered in order.
    `sent` holds each request as requests prepared it, so a test asserts on what would have gone on the wire.
    `timeouts` holds the timeout each one carried.
    """

    def __init__(self):
        self.sent = []
        self.timeouts = []
        self._script = []

    def respond(self, status=200, *, json=None, body=b"", headers=None):
        headers = dict(headers or {})
        if json is not None:
            body = json_lib.dumps(json).encode()
            headers.setdefault("Content-Type", "application/activity+json")
        self._script.append((status, headers, body))

    def fail(self, exception):
        self._script.append(exception)

    def send(self, request, timeout=None, **kwargs):
        self.sent.append(request)
        self.timeouts.append(timeout)
        assert self._script, f"unexpected request: {request.method} {request.url}"

        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step

        status, headers, body = step
        response = Response()
        response.status_code = status
        response.headers = CaseInsensitiveDict(headers)
        response.raw = HTTPResponse(
            body=io.BytesIO(body) if isinstance(body, bytes) else body,
            headers=headers,
            status=status,
            preload_content=False,
        )
        response.url = request.url
        response.request = request
        return response
