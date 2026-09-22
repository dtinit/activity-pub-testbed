"""
Turning a source server into a set of URLs, by asking it rather than assuming.

Owns
    - Fetching `/.well-known/oauth-authorization-server` (RFC 8414)
    - Reading the authorization and token endpoints plus the advertised scopes
    - Fetching the public Actor and reading `endpoints.oauthMigrationEndpoint`
    - Re-fetching the Actor with the token
    - And resolving the scope-gated `migration` object into the four collection URLs (outbox, content, following, blocked)
    - Also owns starting from either a base URL or an Actor URL, since a user may supply either

Must not
    - Read `settings` for a URL that should have been discovered.
      In Mode C, this server already knows its own endpoints, so constructing one instead of fetching it
      silently deletes the discovery half of the protocol.
"""
