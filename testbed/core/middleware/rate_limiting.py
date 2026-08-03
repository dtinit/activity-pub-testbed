"""
Rate limiting middleware for LOLA source-server compliance.

LOLA Section 6.7, "Load Management During Fetching of Content":

    The source server MAY rate limit requests by sending a 429 Too Many Requests
    response as defined in [RFC6585], with a Retry-After header. If the destination
    receives a 429 response status code, it SHOULD respect the Retry-After header
    and resume its requests after the chosen delay.

The normative SHOULD lands on the destination server honoring Retry-After -- which is what
this testbed exists to let destination implementers exercise. That makes predictable,
correlatable 429s more valuable here than accurate ones: a destination cannot develop backoff
logic against a signal that fires for reasons unrelated to its own request pattern.

See docs/lola-rate-limiting.md for the design rationale.

What this middleware guarantees:
- A 429 carries Retry-After, a JSON response, CORS headers letting browser-based
  federation clients actually read Retry-After.
- Counting is per (rule, client IP). A request only consumes the budget of the
  rule matching its own path, never another path's.

A fixed window was implemented. Each (rule, ip) pair holds an integer counter stored
with a TTL equal to the rule's window. The first request of a window creates it with
cache.add(); later requests use cache.incr(). Expiry is the cache's responsibility,
so there is no cleanup pass and no unbounded growth.

It relies on incr() preserving the key's TTL, so that continued traffic cannot extend a
window (hammering while blocked must not lengthen a client's own lockout, or Retry-After
becomes a lie).

Counters live in Django's cache, which under the default LocMemCache is per-process,
so the effective ceiling is:

    limit x gunicorn_workers x running_cloud_run_instances

Threads do not multiply it -- they share one process's memory, which is exactly why
incr() has to be atomic. Worker processes and Cloud Run instances do. The container
currently runs --workers 1, so today this reduces to limit x instances.
"""

import logging
import time

from django.conf import settings
from django.core.cache import cache

from ..utils.errors import build_rate_limit_error

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "ratelimit"

# Set once per process by _log_chain_shape_once below.
_chain_shape_logged = False


def _log_chain_shape_once(entries, depth, client_ip):
    """
    Report the X-Forwarded-For shape this process actually observes, once.

    RATE_LIMIT_TRUSTED_PROXY_DEPTH cannot be validated from code -- only a real
    request through the real proxy chain reveals its length, and a wrong value
    fails silently when the chain is LONGER than configured. Without this the
    resolved IP is visible only when a 429 fires, so checking the setting would mean
    deliberately rate limiting production traffic.

    Once per process rather than once globally, so every Cloud Run instance reports
    the chain it sees while keeping the log quiet.
    """
    global _chain_shape_logged

    if _chain_shape_logged:
        return

    _chain_shape_logged = True
    logger.info(
        "Rate limit client resolution: xff_entries=%s configured_depth=%s resolved=%s",
        len(entries),
        depth,
        client_ip,
    )


class RateLimitingMiddleware:
    """
    Per-(rule, client IP) fixed-window rate limiting. Applied site-wide: unmatched
    paths fall to RATE_LIMIT_DEFAULT, so this governs more than the LOLA surface.

    Settings consumed (testbed/settings/base.py):
        RATE_LIMIT_ENABLED (bool)              -- optional, defaults True
        RATE_LIMIT_RULES (list[dict])          -- optional, defaults []
        RATE_LIMIT_DEFAULT (dict)              -- REQUIRED, rule for unmatched paths
        RATE_LIMIT_EXEMPT_PREFIXES (list[str]) -- REQUIRED, paths that never count
        RATE_LIMIT_TRUSTED_PROXY_DEPTH (int)   -- optional, defaults 0
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._enabled():
            return self.get_response(request)

        path = request.path

        if self._is_exempt(path):
            return self.get_response(request)

        rule = self._rule_for_path(path)
        client_ip = self.get_client_ip(request)
        key = f"{CACHE_KEY_PREFIX}:{rule['name']}:{client_ip}"

        try:
            allowed, retry_after = self._consume(key, rule["limit"], rule["window"])
        except Exception:
            # Fail open. A limiter is a dampening signal under a Section 6.7 MAY;
            # a cache failure must never take down the endpoints it protects.
            logger.exception(
                "Rate limiting check failed, allowing request path=%s rule=%s",
                path,
                rule["name"],
            )
            return self.get_response(request)

        if not allowed:
            logger.warning(
                "Rate limit exceeded ip=%s rule=%s path=%s limit=%s window=%ss "
                "retry_after=%ss",
                client_ip,
                rule["name"],
                path,
                rule["limit"],
                rule["window"],
                retry_after,
            )
            return build_rate_limit_error(
                retry_after_seconds=retry_after,
                request=request,
                limit=rule["limit"],
                window=rule["window"],
            )

        return self.get_response(request)

    # Configuration accessors

    def _enabled(self):
        return bool(getattr(settings, "RATE_LIMIT_ENABLED", True))

    def _rules(self):
        return getattr(settings, "RATE_LIMIT_RULES", [])

    def _fallback_rule(self):
        return settings.RATE_LIMIT_DEFAULT

    def _exempt_prefixes(self):
        return settings.RATE_LIMIT_EXEMPT_PREFIXES

    # Path resolution

    def _is_exempt(self, path):
        return any(path.startswith(prefix) for prefix in self._exempt_prefixes())

    def _rule_for_path(self, path):
        """
        Return the rule governing `path`, by longest matching prefix.

        Longest-match means a more specific prefix beats a more general one
        regardless of declaration order, so rules can be listed in any sequence.
        """
        best_rule = self._fallback_rule()
        best_length = 0

        for rule in self._rules():
            prefix = rule["prefix"]
            if path.startswith(prefix) and len(prefix) > best_length:
                best_rule = rule
                best_length = len(prefix)

        return best_rule

    # Client identity

    def get_client_ip(self, request):
        """
        Resolve the client IP by counting in from the RIGHT of X-Forwarded-For.

        Each proxy appends what it observed, so right-hand entries are facts while
        the leftmost is whatever the client sent. Reading index 0 would let a client
        mint a fresh bucket per request just by varying the header.

        RATE_LIMIT_TRUSTED_PROXY_DEPTH is how many proxies append in front of this
        app; the real client sits that many entries in from the right. Default 0
        means the header is not trusted at all, so each deployment opts in.

        Falls back to REMOTE_ADDR when the chain is shorter than the configured
        depth -- the header is then not the shape this deployment expects.

        Side effect: reports the observed chain shape once per process (see
        _log_chain_shape_once), so the configured depth can be checked without
        forcing a 429.
        """
        depth = int(getattr(settings, "RATE_LIMIT_TRUSTED_PROXY_DEPTH", 0) or 0)
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        entries = [part.strip() for part in forwarded_for.split(",") if part.strip()]

        if depth > 0 and len(entries) > depth:
            client_ip = entries[len(entries) - depth - 1]
        else:
            if depth > 0 and entries:
                logger.warning(
                    "X-Forwarded-For shorter than RATE_LIMIT_TRUSTED_PROXY_DEPTH "
                    "(%s entries, depth %s); falling back to REMOTE_ADDR",
                    len(entries),
                    depth,
                )
            client_ip = request.META.get("REMOTE_ADDR") or "unknown"

        _log_chain_shape_once(entries, depth, client_ip)
        return client_ip

    # Counting

    def _consume(self, key, limit, window):
        """
        Count one request against `key`; return (allowed, retry_after_seconds).

        A companion "<key>:reset" entry records when the window ends, so Retry-After
        reports true remaining time rather than a whole window -- destinations SHOULD
        honor that value (Section 6.7), so its accuracy is user-visible.

        Blocked requests still increment, which is harmless: incr() preserves the
        TTL, so hammering cannot extend a client's own lockout.
        """
        reset_key = f"{key}:reset"
        now = time.time()

        # add() succeeds only if the key is absent or expired: this opens a new
        # window. Atomic, so concurrent first-requests cannot both win.
        if cache.add(key, 1, window):
            cache.set(reset_key, now + window, window)
            return True, 0

        try:
            count = cache.incr(key)
        except ValueError:
            # Expired between add() and incr(); treat as a fresh window.
            cache.set(key, 1, window)
            cache.set(reset_key, now + window, window)
            return True, 0

        if count > limit:
            reset_at = cache.get(reset_key)
            # Reset marker gone: a full window is the safe over-estimate.
            retry_after = max(int(reset_at - now) + 1, 1) if reset_at else window
            return False, retry_after

        return True, 0
