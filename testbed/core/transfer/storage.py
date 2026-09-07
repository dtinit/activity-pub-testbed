"""
Writing transformed objects into this server's own tables.

Owns
    - Persisting a transformed object against the destination Actor
    - Recording the source-to-destination ID mapping that the result report is built from
    - Detecting an object already imported by an earlier job
    - Reporting a per-item outcome (imported, skipped, duplicate, failed) rather than raising past the first failure

Must not
    - Read source-actor rows. This module may import `testbed.core.models` to write the destination
      side; anything belonging to the source must arrive over HTTP, as a stranger's would
    - Transform. What arrives here is already final
    - Abort the whole transfer on one bad item. A single object that will not save is an item outcome, not a job failure
"""
