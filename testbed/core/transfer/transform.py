"""
Rewriting a fetched object into the one this server will publish.

Owns
    - Generating a new object ID for every copied object
    - Setting the actor ID to the destination Actor for the standard account-migration case
    - Adding and preserving `previously` breadcrumbs
    - Preserving metadata that LOLA §7 names (`published`, `to`, `inReplyTo`, likes, replies)
    - Building the wrapper activity for the destination outbox
    - Applying the decided rule for attributes it does not recognise

Must not
    - Reuse a source object's ID. LOLA §7.1.1: the destination "MUST create or choose a new
      context-appropriate Object ID for each object … since it is making a copy of an object that
      still exists elsewhere it can't use the exact same object ID.".
    - Drop breadcrumbs. §7.1.5 is a SHOULD, both for adding one and for preserving those
      already present, newest first.
    - Silently keep everything it does not recognise. §7.1.10 leaves this open. The default is to
      drop unrecognised attributes from the saved object while retaining them in the artifact.
    - Import `testbed.core.models` or touch the database. It takes fetched shapes and returns
      transformed ones; persistence is `storage.py`'s.
"""
