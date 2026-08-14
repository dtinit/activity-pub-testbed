# LOLA §5: "The advertised OAuth endpoint MUST support the `activitypub_account_portability` scope."

LOLA_PORTABILITY_SCOPE = "activitypub_account_portability"


def _normalize_scopes(scopes):
    """
    Normalize any scope shape seen in the OAuth flow into a set of scope tokens.

    Shapes actually produced by the OAuth flow:
        - None / ""     -> empty set   (missing scope on a token or request)
        - "a b c"       -> {"a", "b", "c"}   (token dict, AccessToken.scope, form/querystring)
        - ["a", "b"]    -> {"a", "b"}        (oauthlib, at validate_scopes)

    Args:
        scopes: None, a space-delimited scope string, or an iterable of scope tokens.

    Returns:
        set: the exact scope tokens present.
    """
    if not scopes:
        return set()

    if isinstance(scopes, str):
        # RFC 6749 §3.3 separates scope tokens with a single space.
        # Split first so comparisons match whole tokens, never substrings.
        tokens = set()

        for token in scopes.strip().split(" "):
            if token:
                tokens.add(token)

        return tokens

    # Already an iterable of tokens
    return set(scopes)


def scope_grants_portability(scopes):
    """
    Return True when `scopes` grants the LOLA portability scope.

    Called by four scope decisions:
        - authorization-time validation (validate_scopes)
        - token-issuance binding (_save_bearer_token)
        - request-time authentication (_has_portability_scope)
        - Section 5.3 `activitypub_actor` redirect decision (_prepare_actor_binding).

    Args:
        scopes: None, a space-delimited scope string, or an iterable of scope tokens.

    Returns:
        bool: True only when an exact `activitypub_account_portability` scope token is present.
    """
    return LOLA_PORTABILITY_SCOPE in _normalize_scopes(scopes)
