import base64
import gzip
import io
import logging
from datetime import UTC, datetime, timedelta

import pytest
import requests

from testbed.core.transfer import transport
from testbed.core.transfer.transport import TransportError

SOURCE = "https://source.example"
TOKEN = "tok-12345"


# The URL policy should be refused before any socket opens
@pytest.mark.parametrize(
    "url",
    [
        "http://source.example/actor",  # plaintext to a remote host (LOLA §6.1)
        "http://testserver/actor",  # BASE_URL in test.py and ci.py which is a name, not a loopback host
        "ftp://source.example/actor",
    ],
)
def test_a_disallowed_url_is_refused_before_any_request(fake_source, url):
    with pytest.raises(TransportError, match="^refused"):
        transport.get(url, token=TOKEN)
    assert fake_source.sent == []


def test_plaintext_to_loopback_is_allowed_where_the_environment_permits_it(fake_source):
    fake_source.respond(json={})

    transport.get("http://localhost:8000/actor", token=TOKEN)

    assert len(fake_source.sent) == 1


def test_plaintext_to_loopback_is_refused_under_the_deployed_policy(fake_source, https_only):
    with pytest.raises(TransportError):
        transport.get("http://localhost:8000/actor", token=TOKEN)

    assert fake_source.sent == []


def test_credentials_in_a_url_are_refused_and_never_echoed(fake_source):
    # requests would turn them into a Basic header that replaces the bearer
    with pytest.raises(TransportError) as refused:
        transport.get("https://someone:hunter2@source.example/actor", token=TOKEN)

    assert "hunter2" not in str(refused.value)
    assert fake_source.sent == []


# The token should go in the header, never in the URL
def test_the_token_travels_only_in_the_authorization_header(fake_source):
    fake_source.respond(json={})

    transport.get(f"{SOURCE}/outbox?page=2", token=TOKEN)

    sent = fake_source.sent[0]
    assert sent.headers["Authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in sent.url


# The client credentials go in the Basic header and the code in the body, and the log holds neither
def test_a_post_sends_its_form_with_basic_credentials_and_logs_neither(fake_source, caplog):
    fake_source.respond(json={})

    with caplog.at_level(logging.DEBUG):
        transport.post(f"{SOURCE}/oauth/token/", data={"code": "c0de"}, auth=("client", "s3cret"))

    sent = fake_source.sent[0]
    assert sent.method == "POST"
    assert sent.url == f"{SOURCE}/oauth/token/"
    assert sent.headers["Authorization"] == "Basic " + base64.b64encode(b"client:s3cret").decode()
    assert sent.headers["Accept"] == "application/json"
    assert sent.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert sent.body == "code=c0de"
    assert f"Transport POST {SOURCE}/oauth/token/ -> 200" in caplog.text
    assert "c0de" not in caplog.text
    assert "s3cret" not in caplog.text


# What every request carries

def test_a_request_asks_for_activitypub_names_itself_and_sets_the_timeout(fake_source):
    fake_source.respond(json={})

    transport.get(f"{SOURCE}/actor", token=TOKEN)

    sent = fake_source.sent[0]
    assert sent.headers["Accept"] == transport.ACCEPT
    assert sent.headers["User-Agent"] == transport.USER_AGENT
    assert fake_source.timeouts == [transport.TIMEOUT]  # requests' own default is no timeout at all

def test_a_network_failure_is_a_transport_error(fake_source):
    fake_source.fail(requests.ConnectTimeout("connect timed out"))

    with pytest.raises(TransportError):
        transport.get(f"{SOURCE}/actor", token=TOKEN)


# A body whose first read times out, as a source that stops sending mid-response would
class _StallingBody(io.RawIOBase):
    def readable(self):
        return True

    def readinto(self, buffer):
        raise TimeoutError("timed out")


def test_a_read_that_stalls_mid_body_is_a_transport_error(fake_source):
    fake_source.respond(body=_StallingBody())

    with pytest.raises(TransportError):
        transport.get(f"{SOURCE}/actor", token=TOKEN)


# The body cap

def test_the_cap_counts_decoded_bytes(fake_source):
    compressed = gzip.compress(b"\0" * (transport.MAX_BODY_BYTES + 1))
    assert len(compressed) < transport.MAX_BODY_BYTES // 100
    fake_source.respond(body=compressed, headers={"Content-Encoding": "gzip"})

    with pytest.raises(TransportError):
        transport.get(f"{SOURCE}/actor", token=TOKEN)

def test_a_declared_length_past_the_cap_is_refused_before_reading(fake_source):
    fake_source.respond(
        body=_StallingBody(), headers={"Content-Length": str(transport.MAX_BODY_BYTES + 1)}
    )

    with pytest.raises(TransportError, match="declares more than"):
        transport.get(f"{SOURCE}/actor", token=TOKEN)


# What comes back

def test_every_status_comes_back_for_the_caller_to_judge(fake_source):
    fake_source.respond(404, body=b"<html>Not Found</html>", headers={"Content-Type": "text/html"})

    fetched = transport.get(f"{SOURCE}/.well-known/oauth-authorization-server", token=None)

    assert fetched.status == 404
    assert fetched.body is None
    assert fetched.text == "<html>Not Found</html>"


# Following a redirect would resend the token, or a POST's form and credentials, wherever it points
@pytest.mark.parametrize(
    "send",
    [
        lambda url: transport.get(url, token=TOKEN),
        lambda url: transport.post(url, data={"code": "c0de"}, auth=("client", "s3cret")),
    ],
    ids=["get", "post"],
)
def test_a_redirect_comes_back_unfollowed(fake_source, send):
    fake_source.respond(307, headers={"Location": "https://elsewhere.example/collect"})

    fetched = send(f"{SOURCE}/oauth/token/")

    assert fetched.status == 307
    assert len(fake_source.sent) == 1


# A 429

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)

@pytest.mark.parametrize(
    "value, expected",
    [
        ("120", NOW + timedelta(seconds=120)),  # delay-seconds
        ("Fri, 25 Sep 2026 12:05:00 GMT", NOW + timedelta(minutes=5)),  # an HTTP-date
        ("Thu, 24 Sep 2026 12:00:00 GMT", NOW),  # a date already past: now, never earlier
        (None, NOW + transport.DEFAULT_RETRY_AFTER),  # absent: RFC 6585 lets a 429 leave it out
        ("soon", NOW + transport.DEFAULT_RETRY_AFTER),  # unparseable: the default, never 1970
        ("172800", NOW + transport.MAX_RETRY_AFTER),  # 48 hours asked for, 24 given
        ("9" * 12, NOW + transport.MAX_RETRY_AFTER),  # unclamped, this overflows a datetime
        ("9" * 5000, NOW + transport.MAX_RETRY_AFTER),  # past Python's 4,300-digit int() limit
    ],
)
def test_retry_after_becomes_a_bounded_retry_when(value, expected):
    assert transport.retry_when_from(value, now=NOW) == expected
