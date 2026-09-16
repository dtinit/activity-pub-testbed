"""
The OAuth authorization process, seen from the destination side.

Owns
    - Building the authorization URL (`client_id`, `redirect_uri`, `scope`, `state`)
    - Generating and validating `state`
    - Parsing the callback's `code`, `state` and `activitypub_actor`
    - The token exchange
    - And for Mode B (serve as a Destination Server only), the per-source-server client credentials this
      server holds as a registered OAuth client on that source server.

Must not
    - Prefer the Actor ID the user typed over the `activitypub_actor` returned with the
      authorization code. LOLA §5.3: the destination "MUST use the Actor ID provided with the
      authorization code rather than the original one the user communicated.".
    - Accept a callback whose `state` does not match the one issued for that job
"""
