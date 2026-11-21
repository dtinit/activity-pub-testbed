import base64
import logging
from urllib.parse import parse_qs, quote_plus, urlencode

import pytest
import requests
from django.urls import reverse

from testbed.core.factories import TransferJobFactory
from testbed.core.models import TransferJob
from testbed.core.tests.helpers import destination_actor_for
from testbed.core.transfer import auth

SOURCE = "https://source.example"
ACTOR = f"{SOURCE}/api/actors/1/"
TOKEN_RESPONSE = {
    "access_token": "access-token-value",
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": "activitypub_account_portability",
    "refresh_token": "refresh-token-value",
}


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
