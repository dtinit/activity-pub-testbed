import json
import logging

import pytest
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from testbed.core.middleware import rate_limiting
from testbed.core.middleware.rate_limiting import RateLimitingMiddleware

LOGGER_NAME = "testbed.core.middleware.rate_limiting"

TEST_RULES = [
    {"name": "oauth_authorize", "prefix": "/oauth/authorize/", "limit": 2, "window": 300},
    {"name": "lola_api", "prefix": "/api/actors/", "limit": 5, "window": 60},
]

TEST_DEFAULT = {"name": "default", "limit": 50, "window": 60}

rate_limiting_enabled = override_settings(
    RATE_LIMIT_ENABLED=True,
    RATE_LIMIT_RULES=TEST_RULES,
    RATE_LIMIT_DEFAULT=TEST_DEFAULT,
    RATE_LIMIT_EXEMPT_PREFIXES=["/static/", "/health"],
    RATE_LIMIT_TRUSTED_PROXY_DEPTH=0,
)

CLIENT_IP = "203.0.113.5"
OTHER_IP = "198.51.100.7"

AUTHORIZE = "/oauth/authorize/"


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    cache.clear()
    yield
    cache.clear()


def make_middleware():
    """
    Return (middleware, downstream_paths).

    downstream_paths records every request that reached the wrapped view, so tests
    can distinguish "allowed" from "short-circuited with 429" without relying only
    on status codes.
    """
    downstream_paths = []

    def get_response(request):
        downstream_paths.append(request.path)
        return HttpResponse("ok")

    return RateLimitingMiddleware(get_response), downstream_paths


def send(middleware, path, ip=CLIENT_IP, **extra):
    # Drive a single GET through the middleware and return the response
    request = RequestFactory().get(path, REMOTE_ADDR=ip, **extra)
    return middleware(request)


def exhaust(middleware, path=AUTHORIZE, ip=CLIENT_IP, times=2):
    # Consume a rule's whole budget so the next request is rejected
    for _ in range(times):
        send(middleware, path, ip=ip)


# Bucket isolation


@rate_limiting_enabled
def test_traffic_to_other_paths_does_not_consume_the_oauth_budget():
    """
    Counters are keyed by rule as well as by client. Drop the rule from that key and
    every path shares one budget, so unrelated traffic silently eats a stricter
    rule's allowance.

    The count is what makes this trigger: 12 requests on the default rule is
    well past oauth_authorize's entire budget of 2, so a shared counter would already
    be over the line by the time the first OAuth request arrives. Keep it above
    oauth_authorize's limit or this stops testing anything.
    """
    middleware, downstream = make_middleware()

    # A page load's worth of unrelated requests, all on the default rule
    for _ in range(12):
        assert send(middleware, "/").status_code == 200

    # First ever request to the OAuth endpoint must be allowed
    assert send(middleware, AUTHORIZE).status_code == 200
    assert downstream[-1] == AUTHORIZE


@rate_limiting_enabled
def test_each_rule_keeps_an_independent_budget():
    # Exhausting one rule must leave every other rule untouched
    middleware, _ = make_middleware()

    exhaust(middleware)
    assert send(middleware, AUTHORIZE).status_code == 429

    # Other rules are unaffected
    assert send(middleware, "/api/actors/1/").status_code == 200
    assert send(middleware, "/").status_code == 200


@rate_limiting_enabled
def test_budgets_are_per_client():
    # One client exhausting a rule must not affect a different client
    middleware, _ = make_middleware()

    exhaust(middleware)
    assert send(middleware, AUTHORIZE).status_code == 429

    assert send(middleware, AUTHORIZE, ip=OTHER_IP).status_code == 200


# Limit behaviour


@rate_limiting_enabled
def test_limit_boundary_allows_exactly_the_configured_count():
    # A limit of N allows N requests and rejects the N+1th
    middleware, downstream = make_middleware()

    assert send(middleware, AUTHORIZE).status_code == 200
    assert send(middleware, AUTHORIZE).status_code == 200
    assert send(middleware, AUTHORIZE).status_code == 429

    # The rejected request never reached the view
    assert downstream.count(AUTHORIZE) == 2


@rate_limiting_enabled
def test_window_expiry_opens_a_fresh_budget():
    """
    Once the TTL lapses the counter is gone and cache.add() starts a new window.
    Expiry is the cache's job, so nothing in the middleware resets a counter --
    if the TTL handling broke, blocked clients would simply stay blocked forever.
    """
    middleware, _ = make_middleware()
    exhaust(middleware)
    assert send(middleware, AUTHORIZE).status_code == 429

    # Force the boundary the TTL would have reached
    for key in list(cache._expire_info):
        cache._expire_info[key] = 0

    assert send(middleware, AUTHORIZE).status_code == 200
    assert send(middleware, AUTHORIZE).status_code == 200
    assert send(middleware, AUTHORIZE).status_code == 429


@rate_limiting_enabled
def test_blocked_requests_do_not_extend_the_window():
    """
    incr() must preserve the key's TTL. If it reset it, continued hammering would
    keep pushing the window out and Retry-After would become a lie.
    """
    middleware, _ = make_middleware()
    exhaust(middleware)

    first_retry_after = int(send(middleware, AUTHORIZE)["Retry-After"])

    # Hammer while blocked
    for _ in range(20):
        response = send(middleware, AUTHORIZE)
        assert response.status_code == 429

    # Time only moves forward, so Retry-After must not have grown
    assert int(response["Retry-After"]) <= first_retry_after


# The 429 contract (LOLA Section 6.7 / RFC6585)


@rate_limiting_enabled
def test_429_carries_the_standard_json_error_contract():
    # The 429 must be machine-readable, on the same contract as every other error
    middleware, _ = make_middleware()
    exhaust(middleware)

    response = send(middleware, AUTHORIZE)

    assert response.status_code == 429
    assert response["Content-Type"] == "application/json"

    body = json.loads(response.content)
    assert body["error_code"] == "rate_limit_exceeded"
    assert body["detail"]
    assert body["hint"]
    assert body["remediation"]
    assert body["endpoint"] == AUTHORIZE
    assert body["method"] == "GET"
    assert body["request_id"]
    assert body["timestamp"]


@rate_limiting_enabled
def test_429_carries_retry_after_and_federation_headers():
    """
    Retry-After is what Section 6.7 asks destinations to honor, and browser-based
    federation clients cannot read it unless it is explicitly exposed via CORS.
    """
    middleware, _ = make_middleware()
    exhaust(middleware)

    response = send(middleware, AUTHORIZE)

    assert 1 <= int(response["Retry-After"]) <= 300  # within the configured window
    assert response["Cache-Control"] == "no-store"
    assert response["Access-Control-Allow-Origin"] == "*"
    assert response["Access-Control-Expose-Headers"] == "Retry-After"


@rate_limiting_enabled
def test_429_hint_reports_the_limit_that_was_hit():
    # The body should say which budget was exhausted, not just that one was
    middleware, _ = make_middleware()
    exhaust(middleware)

    hint = json.loads(send(middleware, AUTHORIZE).content)["hint"]

    assert "2" in hint and "300" in hint


# Client identification


@rate_limiting_enabled
def test_forwarded_for_is_ignored_when_no_proxy_is_trusted():
    """
    At depth 0 the header is not trusted at all, so varying it cannot mint a fresh
    bucket. Reading the leftmost entry instead would hand a caller exactly that.
    """
    middleware, _ = make_middleware()

    for i in range(2):
        response = send(middleware, AUTHORIZE, HTTP_X_FORWARDED_FOR=f"198.51.100.{i}")
        assert response.status_code == 200

    # Same real client, brand new spoofed header: still blocked
    response = send(middleware, AUTHORIZE, HTTP_X_FORWARDED_FOR="198.51.100.99")
    assert response.status_code == 429


@override_settings(RATE_LIMIT_TRUSTED_PROXY_DEPTH=1)
def test_client_ip_is_counted_in_from_the_right():
    """
    With one trusted trailing entry, the caller is the one just before it. Anything
    the caller injects lands further left and must be ignored.
    """
    middleware, _ = make_middleware()
    factory = RequestFactory()

    # Well-formed chain
    request = factory.get(
        "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.5, 130.211.0.1"
    )
    assert middleware.get_client_ip(request) == "203.0.113.5"

    # Client injects an entry; the real client is still one in from the right
    request = factory.get(
        "/",
        REMOTE_ADDR="10.0.0.1",
        HTTP_X_FORWARDED_FOR="1.1.1.1, 203.0.113.5, 130.211.0.1",
    )
    assert middleware.get_client_ip(request) == "203.0.113.5"


@override_settings(RATE_LIMIT_TRUSTED_PROXY_DEPTH=1)
def test_short_forwarded_for_chain_falls_back_to_remote_addr():
    """
    A chain shorter than the configured depth means the header is not the shape this
    deployment expects, so fall back to the value a client cannot forge.
    """
    middleware, _ = make_middleware()

    request = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.1.1.1"
    )
    assert middleware.get_client_ip(request) == "10.0.0.1"


@rate_limiting_enabled
def test_chain_shape_is_reported_once_per_process(caplog, monkeypatch):
    """
    RATE_LIMIT_TRUSTED_PROXY_DEPTH can only be validated against a real proxy chain,
    and a value that is too low fails silently. This line is the only way to observe
    what was resolved without deliberately triggering a 429.
    """
    # monkeypatch, not a bare assignment: the flag is module state and would
    # otherwise stay set for every test that runs after this one.
    monkeypatch.setattr(rate_limiting, "_chain_shape_logged", False)
    middleware, _ = make_middleware()

    # REMOTE_ADDR deliberately differs from every X-Forwarded-For entry, so the
    # report shows which source was actually used rather than a coincidental match.
    forwarded = "203.0.113.5, 10.0.0.1"
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        send(middleware, AUTHORIZE, ip="192.0.2.77", HTTP_X_FORWARDED_FOR=forwarded)
        send(middleware, AUTHORIZE, ip="192.0.2.77", HTTP_X_FORWARDED_FOR=forwarded)

    reports = [
        r.getMessage() for r in caplog.records if "client resolution" in r.getMessage()
    ]

    assert len(reports) == 1, "must report once per process, not per request"
    # The chain length is reported even at depth 0 -- that is what reveals a
    # deployment ignoring entries it ought to be trusting.
    assert "xff_entries=2" in reports[0]
    assert "configured_depth=0" in reports[0]
    assert "resolved=192.0.2.77" in reports[0]  # REMOTE_ADDR, not the header


# Exemptions


@rate_limiting_enabled
def test_exempt_paths_never_consume_a_budget():
    """
    Assets and platform health checks must not spend a user's allowance. In
    development DEBUG=True serves static through Django.
    """
    middleware, _ = make_middleware()

    for _ in range(50):
        assert send(middleware, "/static/css/main.css").status_code == 200

    for _ in range(50):
        assert send(middleware, "/health").status_code == 200

    # Every other budget is untouched.
    assert send(middleware, AUTHORIZE).status_code == 200


# Rule resolution


@rate_limiting_enabled
def test_longest_matching_prefix_wins():
    """
    Specificity, not declaration order, decides which rule applies.

    The rules must OVERLAP for this to test anything: with disjoint prefixes no path
    matches two rules, and first-match and longest-match become indistinguishable.
    Both declaration orders are checked, since order-independence is the point --
    reordering RATE_LIMIT_RULES must never change behaviour.
    """
    overlapping = [
        {"name": "lola_api", "prefix": "/api/actors/", "limit": 5, "window": 60},
        {
            "name": "migration",
            "prefix": "/api/actors/5/migration/",
            "limit": 1,
            "window": 60,
        },
    ]
    middleware, _ = make_middleware()

    for rules in (overlapping, list(reversed(overlapping))):
        with override_settings(RATE_LIMIT_RULES=rules):
            # Only the general prefix matches
            assert (
                middleware._rule_for_path("/api/actors/5/outbox/")["name"] == "lola_api"
            )
            # Both match; the more specific one must win
            assert (
                middleware._rule_for_path("/api/actors/5/migration/content/")["name"]
                == "migration"
            )
            # Neither matches.
            assert middleware._rule_for_path("/somewhere/else")["name"] == "default"


# Operational safety


@override_settings(RATE_LIMIT_ENABLED=False, RATE_LIMIT_RULES=TEST_RULES)
def test_disabled_middleware_allows_everything():
    middleware, downstream = make_middleware()

    for _ in range(20):
        assert send(middleware, AUTHORIZE).status_code == 200

    assert len(downstream) == 20


@rate_limiting_enabled
def test_cache_failure_fails_open(monkeypatch):
    """
    A limiter is a dampening signal under a Section 6.7 MAY. If the cache breaks it
    must let traffic through rather than take down the endpoints it protects.
    """
    middleware, downstream = make_middleware()

    def explode(*args, **kwargs):
        raise RuntimeError("cache unavailable")

    monkeypatch.setattr("testbed.core.middleware.rate_limiting.cache.add", explode)

    assert send(middleware, AUTHORIZE).status_code == 200
    assert downstream == [AUTHORIZE]


# Wiring


@pytest.mark.django_db
def test_middleware_is_wired_into_the_request_stack(client):
    """
    Everything above drives the middleware directly. This proves it is actually
    installed in settings.MIDDLEWARE and reached by real requests.
    """
    discovery = "/.well-known/oauth-authorization-server"

    with override_settings(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_RULES=[
            {
                "name": "lola_discovery",
                "prefix": discovery,
                "limit": 1,
                "window": 60,
            }
        ],
        RATE_LIMIT_DEFAULT=TEST_DEFAULT,
        RATE_LIMIT_EXEMPT_PREFIXES=[],
        RATE_LIMIT_TRUSTED_PROXY_DEPTH=0,
    ):
        assert client.get(discovery).status_code == 200

        response = client.get(discovery)
        assert response.status_code == 429
        assert response["Retry-After"]
        assert json.loads(response.content)["error_code"] == "rate_limit_exceeded"
