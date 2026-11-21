import base64
import hashlib
import logging
from urllib.parse import parse_qs, quote_plus, urlencode, urlsplit

import pytest
import requests
from django.test import Client
from django.urls import reverse
from oauth2_provider.models import get_refresh_token_model

from testbed.core.factories import (
    ApplicationFactory,
    SourceClientCredentialsFactory,
    TransferJobFactory,
    UserWithActorsFactory,
)
from testbed.core.models import Actor, TokenActorBinding, TransferJob
from testbed.core.tests.helpers import destination_actor_for, source_actor_for
from testbed.core.transfer import auth
from testbed.core.transfer.discovery import discover

SOURCE = "https://source.example"
ACTOR = f"{SOURCE}/api/actors/1/"
TOKEN_RESPONSE = {
    "access_token": "access-token-value",
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": "activitypub_account_portability",
    "refresh_token": "refresh-token-value",
}


# Starting the authorization

def test_the_authorization_url_carries_a_state_kept_on_the_job(discovered_job):
    # The endpoint's own query is kept, except a parameter of ours it tries to set
    discovered_job.authorization_endpoint = f"{SOURCE}/oauth/authorize/?tenant=1&code_challenge_method=plain"
    discovered_job.save()
    client = discovered_job.user.source_clients.get()

    url = urlsplit(auth.authorization_url(discovered_job))

    job = TransferJob.objects.get(pk=discovered_job.pk)
    # RFC 7636 §4.2: BASE64URL(SHA256(verifier)), without padding
    challenge = base64.urlsafe_b64encode(hashlib.sha256(job.pkce_verifier.encode()).digest()).rstrip(b"=").decode()
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{SOURCE}/oauth/authorize/"
    assert parse_qs(url.query) == {
        "tenant": ["1"],
        "response_type": ["code"],
        "client_id": [client.client_id],
        "redirect_uri": [auth.callback_url()],
        "scope": ["activitypub_account_portability"],
        "state": [job.oauth_state],
        "code_challenge": [challenge],
        "code_challenge_method": ["S256"],
    }
    assert 43 <= len(job.pkce_verifier) <= 128
    assert len(job.oauth_state) <= TransferJob._meta.get_field("oauth_state").max_length

    # A second start issues a fresh pair, and the first URL stops working
    first_state, first_verifier = job.oauth_state, job.pkce_verifier
    auth.authorization_url(job)
    reissued = TransferJob.objects.get(pk=job.pk)
    assert reissued.oauth_state != first_state
    assert reissued.pkce_verifier != first_verifier


@pytest.mark.parametrize(
    "case, reason",
    [
        ("not-discovered", "the source's endpoints have not been discovered"),
        ("another-origin", f"the authorization endpoint is not on {SOURCE}"),
        ("no-client", f"no client is registered for {SOURCE}"),
        ("another-users-client", f"no client is registered for {SOURCE}"),
        ("already-authorized", "this job is not waiting for authorization"),
        ("job-failed", "this job is not waiting for authorization"),
    ],
)
def test_authorization_cannot_start_without_what_it_needs(discovered_job, case, reason):
    job = discovered_job
    if case == "not-discovered":
        job.authorization_endpoint = None
    elif case == "another-origin":
        job.authorization_endpoint = "https://elsewhere.example/oauth/authorize/"
    elif case in ("no-client", "another-users-client"):
        job.user.source_clients.all().delete()
        if case == "another-users-client":
            SourceClientCredentialsFactory(source_base_url=SOURCE)
    elif case == "already-authorized":
        job.set_access_token("access-token-value")
    elif case == "job-failed":
        job.state, job.error = TransferJob.State.FAILED, "an earlier step failed"
    job.save()

    with pytest.raises(auth.AuthorizationError) as refused:
        auth.authorization_url(job)

    assert str(refused.value) == reason
    assert TransferJob.objects.get(pk=job.pk).oauth_state is None


# The callback only completes a job its owner is waiting on

@pytest.mark.parametrize(
    "case, status",
    [
        ("anonymous", 302),
        ("post", 405),
        ("no-state", 404),
        ("unknown-state", 404),
        ("another-users-job", 404),
        ("job-not-active", 404),
    ],
)
def test_a_callback_naming_no_waiting_job_changes_nothing(client, waiting_job, fake_source, case, status):
    issued = waiting_job.oauth_state
    params = {"state": issued, "code": "c0de", "activitypub_actor": ACTOR}
    user = waiting_job.user
    if case == "no-state":
        del params["state"]
        # Without the guard, the missing state would match this job's NULL one
        TransferJobFactory(destination_actor=waiting_job.destination_actor)
    elif case == "unknown-state":
        params["state"] = "never-issued"
    elif case == "another-users-job":
        user = destination_actor_for().user
    elif case == "job-not-active":
        TransferJob.objects.filter(pk=waiting_job.pk).update(state=TransferJob.State.FINISHED)
    if case != "anonymous":
        client.force_login(user)

    url = reverse("transfer-callback")
    if case == "post":
        # The same query, sent as a POST
        response = client.post(f"{url}?{urlencode(params)}")
    else:
        response = client.get(url, params)

    assert response.status_code == status
    assert fake_source.sent == []
    assert not TransferJob.objects.exclude(encrypted_access_token="").exists()
    assert TransferJob.objects.get(pk=waiting_job.pk).oauth_state == issued


# A callback for the waiting job that cannot complete fails it, and leaves nothing usable

@pytest.mark.parametrize(
    "query, answer, reason",
    [
        pytest.param(
            {"error": "access_denied", "error_description": "<b>no</b>"},
            None,
            "the source refused authorization (access_denied)",
            id="access-denied",
        ),
        pytest.param(
            {"error": "<b>bad</b>"},
            None,
            "the source refused authorization (unrecognised error)",
            id="unknown-error",
        ),
        pytest.param(
            {"code": "c0de"},
            None,
            "the source named no authorized Actor (activitypub_actor, LOLA §5.3)",
            id="no-actor",
        ),
        pytest.param(
            {"code": "c0de", "activitypub_actor": "https://elsewhere.example/api/actors/1/"},
            None,
            f"the authorized Actor is not on {SOURCE}",
            id="actor-off-origin",
        ),
        pytest.param(
            {"code": "c0de", "activitypub_actor": "http://[bad"},
            None,
            f"the authorized Actor is not on {SOURCE}",
            id="actor-malformed",
        ),
        pytest.param(
            {"code": "c0de", "activitypub_actor": ACTOR + "a" * 500},
            None,
            "the authorized Actor's URL is too long to keep",
            id="actor-too-long",
        ),
        pytest.param(
            {"code": "c0de", "activitypub_actor": ACTOR},
            (400, {"error": "invalid_grant"}),
            "the token endpoint refused the code (400, invalid_grant)",
            id="code-refused",
        ),
        pytest.param(
            {"code": "c0de", "activitypub_actor": ACTOR},
            requests.ConnectionError("down"),
            f"could not fetch {SOURCE}/oauth/token/ (ConnectionError)",
            id="token-endpoint-unreachable",
        ),
        pytest.param(
            {"code": "c0de", "activitypub_actor": ACTOR},
            (200, {**TOKEN_RESPONSE, "token_type": "mac"}),
            "the token endpoint returned no bearer token",
            id="not-a-bearer-token",
        ),
        pytest.param(
            {"code": "c0de", "activitypub_actor": ACTOR},
            (200, {"token_type": "Bearer", "scope": "activitypub_account_portability"}),
            "the token endpoint returned no bearer token",
            id="no-access-token",
        ),
        pytest.param(
            {"code": "c0de", "activitypub_actor": ACTOR},
            (200, {**TOKEN_RESPONSE, "scope": "read"}),
            "the source granted a scope without account portability",
            id="scope-without-portability",
        ),
    ],
)
def test_a_callback_that_cannot_complete_fails_the_job(client, waiting_job, fake_source, query, answer, reason):
    if isinstance(answer, Exception):
        fake_source.fail(answer)
    elif answer:
        fake_source.respond(answer[0], json=answer[1])
    client.force_login(waiting_job.user)

    response = client.get(reverse("transfer-callback"), {"state": waiting_job.oauth_state, **query})

    job = TransferJob.objects.get(pk=waiting_job.pk)
    assert response.status_code == 302
    assert response.url == reverse("home")
    assert (job.state, job.error) == (TransferJob.State.FAILED, reason)
    assert (job.oauth_state, job.get_access_token()) == (None, None)


# The code, the verifier and the client secret go to the token endpoint and nowhere else

def test_the_exchange_sends_secrets_only_where_they_belong(waiting_job, fake_source, caplog):
    state, verifier = waiting_job.oauth_state, waiting_job.pkce_verifier
    # The user typed another Actor than the one the source authorizes (LOLA §5.3)
    typed = f"{SOURCE}/api/actors/3/"
    waiting_job.source_actor_url = typed
    waiting_job.save()
    client = waiting_job.user.source_clients.get()
    fake_source.respond(json=TOKEN_RESPONSE)

    with caplog.at_level(logging.DEBUG):
        auth.complete_authorization(waiting_job, {"state": state, "code": "c0de-value", "activitypub_actor": ACTOR})

    sent = fake_source.sent[0]
    assert sent.url == f"{SOURCE}/oauth/token/"
    # RFC 6749 §2.3.1: form-encoded, then Basic
    basic = f"{quote_plus(client.client_id)}:{quote_plus('client+secret/value')}"
    assert sent.headers["Authorization"] == "Basic " + base64.b64encode(basic.encode()).decode()
    assert parse_qs(sent.body) == {
        "grant_type": ["authorization_code"],
        "code": ["c0de-value"],
        "redirect_uri": [auth.callback_url()],
        "code_verifier": [verifier],
    }

    job = TransferJob.objects.get(pk=waiting_job.pk)
    assert job.authorized_actor_url == ACTOR
    assert job.get_access_token() == "access-token-value"
    assert (job.oauth_state, job.pkce_verifier) == (None, "")

    assert f"the user gave {typed}, the source authorized {ACTOR}" in caplog.text
    assert "Transport POST" in caplog.text
    held = ["c0de-value", "client+secret/value", "access-token-value", "refresh-token-value", state, verifier]
    assert [secret for secret in held if secret in caplog.text] == []


# The whole conversation, against this server's own source

def test_loopback_authorization_keeps_the_callbacks_actor_over_the_typed_one(live_server, settings, caplog):
    settings.BASE_URL = live_server.url
    user = UserWithActorsFactory()
    approver = user.actors.get(role=Actor.ROLE_SOURCE)
    # The user typed someone else's Actor. The source authorizes the account that approves
    typed = source_actor_for()
    secret = "plain+secret/value"
    application = ApplicationFactory(
        user=user, redirect_uris=auth.callback_url(), skip_authorization=True, client_secret=secret
    )
    job = TransferJobFactory(
        destination_actor=user.actors.get(role=Actor.ROLE_DESTINATION),
        source_base_url=live_server.url,
        source_actor_url=f"{live_server.url}/api/actors/{typed.pk}/",
    )
    SourceClientCredentialsFactory(
        user=user, source_base_url=live_server.url, client_id=application.client_id, client_secret=secret
    )
    discover(job)
    browser = Client(HTTP_HOST=urlsplit(live_server.url).netloc)
    browser.force_login(user)

    with caplog.at_level(logging.DEBUG):
        start = auth.authorization_url(job)
        state, verifier = job.oauth_state, job.pkce_verifier
        consent = browser.get(start)
        callback = browser.get(consent["Location"])

    job.refresh_from_db()
    token = job.get_access_token()
    assert callback.status_code == 302
    assert callback.url == reverse("home")
    assert job.authorized_actor_url == f"{live_server.url}/api/actors/{approver.pk}/"
    assert job.authorized_actor_url != job.source_actor_url
    assert TokenActorBinding.objects.get(token__token=token).actor == approver
    assert (job.state, job.oauth_state, job.pkce_verifier) == (TransferJob.State.ACTIVE, None, "")

    code = parse_qs(urlsplit(consent["Location"]).query)["code"][0]
    refresh = get_refresh_token_model().objects.get(access_token__token=token).token
    assert [held for held in (secret, verifier, token, refresh) if held in caplog.text] == []
    elsewhere = [
        r.getMessage() for r in caplog.records if not r.name.startswith(("django_structlog", "oauthlib"))
    ]
    assert [held for held in (code, state) if any(held in line for line in elsewhere)] == []
