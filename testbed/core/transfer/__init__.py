"""
The destination half of the testbed: everything this server does when it acts as a LOLA *destination*, pulling an account from a source server.

Everything under `testbed/core/` outside this package is the source server. This package is its client.

Module ownership:

    transport.py   HTTP client, scheme policy, retry and backoff, 429 handling
    discovery.py   RFC8414 metadata, public Actor, authenticated Actor, migration URL resolution
    auth.py        Authorization URL construction, state, callback parsing, token exchange
    fetch.py       Collection walking, pagination traversal, raw artifact capture
    transform.py   ID generation, breadcrumbs, metadata preservation, wrapper activities
    storage.py     Persisting transformed objects to destination models
    jobs.py        The Collection vocabulary, and the two progress accessors

`Actor` already carries `ROLE_DESTINATION`, and a destination Actor is created for every user at signup.
This package is what will eventually give them behaviour.
"""

__all__ = []
