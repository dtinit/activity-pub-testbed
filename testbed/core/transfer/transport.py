"""
The one HTTP client every destination module uses to reach a source server.

Owns
    - The requests session and its configuration, including the scheme policy
    - The `Authorization: Bearer` header
    - `Accept` negotiation for ActivityPub content types
    - Timeouts on every call; retry and backoff
    - Detection of `429` and parsing of `Retry-After` into a typed exception
    - The descriptive `User-Agent` that lets a source operator see who is fetching
    - And capture of every exchange (method, URL, status, headers, body) as a replayable artifact

Must not be bypassed. LOLA §6.1 makes two MUST claims:
    - "The destination MUST fetch data using HTTPS, not HTTP"
    - "It MUST provide the account migration authorization token in requests even when it
      believes the requests are for public content"

Both are auditable only while there is exactly one exit point, which is why this module exists.

Must not
    - Relax the scheme policy beyond loopback. HTTPS is required unless the host resolves to
      loopback and the environment permits it (true in development, test and CI; false in staging and production).
"""
