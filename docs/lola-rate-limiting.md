# LOLA Rate Limiting Implementation

## Overview

This document provides a comprehensive guide to the rate limiting system implemented in the ActivityPub LOLA testbed. The rate limiting middleware ensures LOLA specification compliance while protecting OAuth and API endpoints from abuse.

## Table of Contents

1. [LOLA Specification Requirements](#lola-specification-requirements)
2. [Design Goals](#design-goals)
3. [Implementation Architecture](#implementation-architecture)
4. [Rate Limit Configuration](#rate-limit-configuration)
5. [Client IP Detection](#client-ip-detection)
6. [The 429 Response Contract](#the-429-response-contract)
7. [Cloud Run and Per-Instance Counters](#cloud-run-and-per-instance-counters)
9. [Development Testing](#development-testing)

---

## LOLA Specification Requirements

LOLA §6.7, *Load Management During Fetching of Content*:

> The source server **MAY** rate limit requests by sending a 429 Too Many Requests response as defined in [RFC6585], with a Retry-After header. If the destination receives a 429 response status code, it **SHOULD** respect the Retry-After header and resume its requests after the chosen delay.

Parsed carefully, this is a very light obligation on a source server:

| Dimension | Obligation |
|---|---|
| Rate limit at all? | **Optional** — MAY. |
| Status code | `429` — required |
| `Retry-After` header | Required as part of the described mechanism |
| Explanatory body | SHOULD, per RFC6585 |
| Counting accuracy | **Unspecified** |
| Global consistency | **Unspecified** |
| Algorithm / limits / identity key | **Our choice** |

RFC6585 is explicit that it "does not define how the origin server identifies the user, nor how it counts requests." So the algorithm, the limit values, the identity key, the window and the consistency model are all implementation choices, not compliance requirements.

**The normative weight sits on the destination.** The only SHOULD in §6.7 is about destinations honoring `Retry-After`. That is what destination developers must implement — and this testbed exists so they can implement and verify it against a compliant source.

---

## Design Goals

Because compliance is nearly free here, the design optimizes for something else: **usefulness to destination implementers.**

1. **Predictable, correlatable 429s.** A destination developer must be able to trigger a 429, read `Retry-After`, back off, retry, and confirm their logic works. A limiter that fires for reasons unrelated to the caller's own request pattern is worse than no limiter, because backoff logic cannot be developed against an arbitrary signal.
2. **A machine-readable body.** The 429 uses the same JSON error contract as every other endpoint, so it can be parsed rather than pattern-matched.
3. **Light abuse dampening.** Secondary. This is a testbed, not an enforcement boundary.

Accuracy of counting is explicitly *not* a goal — see Cloud Run and per-instance counters.

---

## Implementation Architecture

Implemented in `testbed/core/middleware/rate_limiting.py` as `RateLimitingMiddleware`, registered in `settings/base.py` early in the `MIDDLEWARE` list.

### Per-(rule, client) fixed-window counters

Each request resolves to exactly one **rule** by longest matching path prefix. Counting happens against a bucket keyed by that rule *and* the client:

```
ratelimit:<rule_name>:<client_ip>
```

Keying by rule is what keeps budgets isolated. Traffic to `/api/actors/` can never consume the `/oauth/authorize/` allowance.

Each bucket is a single integer stored with a TTL equal to the rule's window:

- The first request of a window creates it with `cache.add(key, 1, window)`
- Later requests use `cache.incr(key)`
- Expiry is the cache's responsibility, so there is no cleanup pass and no unbounded growth

A companion `<key>:reset` entry records when the window ends, so `Retry-After` reports the true remaining time rather than a whole window.

### Accepted trade-off: fixed vs sliding window

A fixed window permits up to 2× the limit across a boundary — N requests just before it, N just after. A sliding window is more precise.

For a dampening signal under a MAY, that imprecision is irrelevant and the simplicity is worth it. This is a deliberate choice, not an oversight.

### Backend constraint

The design relies on `incr()` **preserving the key's TTL**, so that continued traffic cannot extend a window. If hammering while blocked pushed the window out, `Retry-After` would become a lie — and §6.7 asks destinations to trust that value.

`LocMemCache`, the default and what this deployment uses, preserves it: `incr()` writes straight to its internal dict under a lock and never touches the expiry table. Django's **database cache backend does not**. It inherits `BaseCache.incr`, which does `get()` then `set()` without a timeout, resetting the TTL to `DEFAULT_TIMEOUT`. Swapping to it would quietly turn this into a sliding window, and no test would fail — so do not change the cache backend without first checking that its `incr()` leaves the TTL alone.

### Fail-open

If the cache raises for any reason, the middleware logs and allows the request. A limiter is a dampening signal under a MAY; it must never take down the endpoints it protects.

---

## Rate Limit Configuration

All values live in `settings/base.py`, which every environment module inherits. The middleware keeps no copies of the tuned values — identical numbers in two files drift, and settings is where an operator looks to change them.

| Setting | If absent | Purpose |
|---|---|---|
| `RATE_LIMIT_ENABLED` | defaults to `True` | Master switch |
| `RATE_LIMIT_RULES` | defaults to `[]` | Per-path rules; longest prefix wins |
| `RATE_LIMIT_DEFAULT` | **required** — raises | Fallback rule for unmatched paths |
| `RATE_LIMIT_EXEMPT_PREFIXES` | **required** — raises | Paths that never count |
| `RATE_LIMIT_TRUSTED_PROXY_DEPTH` | defaults to `0` | Trusted trailing `X-Forwarded-For` entries |

The two inline defaults encode a **safety posture** rather than configuration: limiting stays on, and `X-Forwarded-For` stays untrusted, unless a deployment says otherwise. The two required settings deliberately have no fallback, so a missing value fails loudly instead of silently applying a number hidden in code.

### Default rules

| Rule | Prefix | Limit | Window |
|---|---|---|---|
| `oauth_authorize` | `/oauth/authorize/` | 60 | 300s |
| `oauth_token` | `/oauth/token/` | 120 | 300s |
| `lola_discovery` | `/.well-known/oauth-authorization-server` | 60 | 60s |
| `lola_api` | `/api/actors/` | 120 | 60s |
| *(fallback)* | everything else | 300 | 60s |

Limits are deliberately generous. One interactive OAuth authorization spans several requests — consent page, approval POST, redirect, token exchange — and this testbed exists for people to exercise that flow repeatedly. A limit that throttles honest integration testing would defeat its purpose.

Longest-prefix matching means rules can be declared in any order; specificity decides.

### Per-environment behaviour

| Environment | Enabled | Notes |
|---|---|---|
| Development | **No** | `DEBUG=True` serves static through Django, so a page load would spend a dozen requests of budget. Set `DJANGO_RATE_LIMIT_ENABLED=1` to exercise it. |
| Test | **No** | Prevents unrelated suites being throttled. `test_rate_limiting.py` re-enables explicitly via `override_settings`. |
| CI | Yes | Inherits base defaults |
| Staging / Production | Yes | Plus `RATE_LIMIT_TRUSTED_PROXY_DEPTH=1` |

### Exemptions

Static and media matter only in development, where Django serves them; in staging and production they come from Cloud Storage and never reach this middleware. Health checks belong to Cloud Run rather than to any user and must not exhaust a user's allowance.

---

## Client IP Detection

`X-Forwarded-For` is **appended to** by each proxy in a chain, so its leftmost entry is whatever the client sent and is entirely under the client's control. Reading index 0 lets a client mint a fresh bucket per request simply by varying the header.

`RATE_LIMIT_TRUSTED_PROXY_DEPTH` is the number of proxies that append to the header in front of this application. The real client sits that many entries in **from the right**, so anything injected by a client lands further left and is ignored.

```
depth = 1, well-formed:   "203.0.113.5, 130.211.0.1"
                            ^^^^^^^^^^^ client (index -2)

depth = 1, client injects: "1.1.1.1, 203.0.113.5, 130.211.0.1"
                                     ^^^^^^^^^^^ still the client
```

**Default is 0**, meaning `X-Forwarded-For` is not trusted at all and `REMOTE_ADDR` is used. Every deployment opts in by declaring how deep its own chain is.

If the observed chain is shorter than the configured depth, the middleware logs a warning and falls back to `REMOTE_ADDR`, since the header is not the shape the deployment expects.

The warning only fires when the chain is *shorter* than configured. A depth set too **high** fails silently, and lets a caller mint a fresh bucket per request by padding the header.

> **Verify before relying on it.** Production sets `1`, but that is a considered bet rather than a documented fact: Google specifies the `<client>, <load-balancer>` format for external Application Load Balancers, which this service does not use, and documents no stable layout for the `run.app` / domain-mapping path. Send one request with no `X-Forwarded-For` and read `client resolution: xff_entries=N` from the logs, then set the depth to `N - 1`. Check on production via the custom domain — staging has no custom domain, so it cannot exercise that path. Correctable via `DJANGO_RATE_LIMIT_TRUSTED_PROXY_DEPTH` without a redeploy.

---

## The 429 Response Contract

Built by `build_rate_limit_error` in `testbed/core/utils/errors.py`. The whole response is the template — status, body and headers.

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 47
Cache-Control: no-store
Access-Control-Allow-Origin: *
Access-Control-Expose-Headers: Retry-After
```

```json
{
  "error_code": "rate_limit_exceeded",
  "detail": "Request rate limit exceeded",
  "timestamp": "2026-07-27T14:33:05.123456+00:00",
  "hint": "Too many requests: the limit is 60 per 300 seconds. Please wait 47 seconds before retrying",
  "remediation": "Honor the Retry-After header, then resume with exponential backoff",
  "endpoint": "/oauth/authorize/",
  "method": "GET",
  "request_id": "5f3c2e91-..."
}
```

Why each header is present:

- **`Retry-After`** — §6.7 describes rate limiting as a 429 "with a Retry-After header"; destinations SHOULD honor it.
- **`Cache-Control: no-store`** — 429 is not in HTTP's heuristically-cacheable set, so a compliant cache would not store it anyway. Stating it explicitly is cheap defence against a non-compliant intermediary replaying a stale 429 at a client that has already backed off.
- **`Access-Control-Expose-Headers`** — ActivityPub federation clients are frequently browser-based. `Retry-After` is unreadable to `fetch()` unless explicitly exposed, which would leave a destination unable to honor the SHOULD above.

The body uses the same `build_error_payload` as every other error in the project, so clients see one contract regardless of which layer rejected them.

---

## Cloud Run and Per-Instance Counters

Counters live in Django's cache. Under the default `LocMemCache` that is **per-process**, and Cloud Run autoscales. The effective ceiling is therefore:

```
limit × gunicorn_workers × running_cloud_run_instances
```

Threads do not multiply it — they share one process's memory, which is exactly why `incr()` has to be atomic. Worker processes and Cloud Run instances do. The container currently runs `--workers 1`, so today this reduces to `limit × instances`.

Two consequences, stated plainly:

**These limits are best-effort dampening, not an enforcement boundary.** §6.7's MAY is what makes that acceptable rather than a compliance gap. Nothing in LOLA or RFC6585 asks for globally consistent counting.

**The multiplier has no stated upper bound, deliberately.** No `--max-instances` is configured on the Cloud Run service, so the platform default applies. Capping instances was considered and **declined**.

**In practice the testbed usually runs a single instance**, where counters are effectively global. The multiplier only appears under concurrent load — which is also the situation where letting some extra traffic through matters least.

Other platform interactions worth knowing:

- **Cold starts reset counters.** A scale-to-zero followed by a new instance starts every bucket empty. Acceptable under a MAY.
- **Static files never reach this middleware in staging/production**, because they are served from Cloud Storage. They only count in development, where `DEBUG=True` makes Django serve them.
- **Health checks are exempt** so platform probes do not consume user budget.

---

## Development Testing

Coverage lives in `testbed/core/tests/test_rate_limiting.py` (18 tests). Rate limiting is disabled by default in the test settings, so each test enables it explicitly with its own small rule set rather than depending on production limits.

Areas covered:

- **Bucket isolation** — traffic on one rule never drains another, and one client never affects another
- **Limit boundary** — N allowed, N+1 rejected, rejected requests never reach the view
- **Window semantics** — hammering while blocked does not extend `Retry-After`
- **429 contract** — JSON body keys, `Retry-After` range, cache and CORS headers
- **Client identification** — depth-0 ignores `X-Forwarded-For`; depth-1 counts in from the right and ignores injected entries; short chains fall back to `REMOTE_ADDR`
- **Exemptions** — static and health paths never count
- **Operational safety** — disabled switch, and fail-open on cache failure
- **Wiring** — one integration test through the real client proving the middleware is installed in `MIDDLEWARE`

### Exercising it by hand

```bash
# Enable locally, then hammer an endpoint
DJANGO_RATE_LIMIT_ENABLED=1 python manage.py runserver

# Watch the limit engage
for i in $(seq 1 70); do
  curl -s -o /dev/null -w "%{http_code} " http://127.0.0.1:8000/oauth/authorize/
done
echo

# Inspect the 429 body and headers
curl -i http://127.0.0.1:8000/oauth/authorize/
```

---

### Log messages

| Level | Message | Meaning |
|---|---|---|
| `INFO` | `Rate limit client resolution: xff_entries=… configured_depth=… resolved=…` | Emitted once per process on the first counted request. The chain shape this deployment actually sees — how you check the proxy depth without forcing a 429 |
| `WARNING` | `Rate limit exceeded ip=… rule=… path=…` | A request was rejected; includes limit, window and retry-after |
| `WARNING` | `X-Forwarded-For shorter than RATE_LIMIT_TRUSTED_PROXY_DEPTH` | Depth set too high; fell back to `REMOTE_ADDR`. Note the reverse case — depth too low — produces no warning |
| `ERROR` | `Rate limiting check failed, allowing request` | Cache failure; request was allowed (fail-open) |
