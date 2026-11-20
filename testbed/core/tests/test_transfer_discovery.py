import logging
import pytest

from testbed.core.factories import TransferJobFactory
from testbed.core.transfer.discovery import DiscoveryError, discover

SOURCE = "https://source.example"
ACTOR = f"{SOURCE}/api/actors/1/"
METADATA = {
    "issuer": SOURCE,
    "authorization_endpoint": f"{SOURCE}/oauth/authorize/",
    "token_endpoint": f"{SOURCE}/oauth/token/",
    "activitypub_account_portability": f"{SOURCE}/oauth/authorize/",
}


# Loopback asks like any other source

def test_loopback_discover_by_asking_not_from_settings(fake_source, settings):
    base = "http://localhost:8000"
    settings.BASE_URL == base
    job = TransferJobFactory(source_base_url=base, source_actor_url=f"{base}/api/actors/1/")
    fake_source.respond(json={
        "issuer": base,
        "token_endpoint": f"{base}/elsewhere/token/",
        "activitypub_account_portability": f"{base}/elsewhere/authorize/",
    })
    fake_source.respond(json={"endpoints": {"oauthMigrationEndpoint": f"{base}/elsewhere/authorize/"}})

    discover(job)
    job.refresh_from_db()

    assert [request.url for request in fake_source.sent] == [
        f"{base}/.well-known/oauth-authorization-server",
        f"{base}/api/actors/1/",
    ]
    assert not any("Authorization" in request.headers for request in fake_source.sent)
    assert job.authorization_endpoint == f"{base}/elsewhere/authorize/"
    assert job.token_endpoint == f"{base}/elsewhere/token/"
    assert set(job.artifacts) == {"well-known", "actor-public"}


# Where the Actor gives no endpoint the metada should be used

@pytest.mark.parametrize(
    "actor_url, requests_sent",
    [(ACTOR, 2), (None, 1)],
    ids=["actor-lacks-the-endpoint", "only-the-domain-is-known"],
)
def test_the_metadata_endpoint_is_used_when_the_actor_gives_none(fake_source, actor_url, requests_sent):
    job = TransferJobFactory(source_actor_url=actor_url)
    fake_source.respond(json=METADATA)
    fake_source.respond(json={"endpoints": {}})

    discover(job)
    job.refresh_from_db()

    assert job.authorization_endpoint == METADATA["activitypub_account_portability"]
    assert len(fake_source.sent) == requests_sent

def test_a_disagreement_uses_the_actors_endpoint_and_names_both(fake_source, caplog):
    from_actor = f"{SOURCE}/per-actor/authorize/"
    job = TransferJobFactory(source_actor_url=ACTOR)
    fake_source.respond(json=METADATA)
    fake_source.respond(json={"endpoints": {"oauthMigrationEndpoint": from_actor}})

    with caplog.at_level(logging.WARNING, logger="testbed.core.transfer.discovery"):
        discover(job)

    job.refresh_from_db()
    assert job.authorization_endpoint == from_actor
    assert from_actor in caplog.text
    assert METADATA["activitypub_account_portability"] in caplog.text


# Unusable metadata fails with a reason, never a KeyError

@pytest.mark.parametrize(
    "status, document, reason",
    [
        (404, {}, "no RFC 8414 metadata"),
        (200, {**METADATA, "issuer": "<https://elsewhere.example>"}, "different issuer"),
        (200, {**METADATA, "token_endpoint": None}, "no token_endpoint"),
        (200, {**METADATA, "activitypub_account_portability": None}, "no portability authorization endpoint"),
        (200, {**METADATA, "activitypub_account_portability": "http://source.example/oauth/authorize/"}, "plaintext"),
    ],
    ids=["missing", "other-issuer", "no-token-endpoint", "no-portability-endpoint", "plaintext-endpoint"],
)
def test_unusable_metadata_fails_with_a_reason(fake_source, status, document, reason):
    job = TransferJobFactory()
    fake_source.respond(status, json=document)

    with pytest.raises(DiscoveryError, match=reason):
        discover(job)

    job.refresh_from_db()
    assert (job.authorization_endpoint, job.token_endpoint) == (None, None)
    assert "well-known" in job.artifacts  # the evidence is kept even when refused
