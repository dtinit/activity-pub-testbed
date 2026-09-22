"""
Writing transformed objects into this server's own tables.

Owns
    - Persisting a transformed object against the destination Actor
    - Nothing else about the source-to-destination mapping. The saved object is the record,
      its own new `id` is the destination side, and the breadcrumb `transform` prepended to
      `previously` is the source side (§7.1.8).
    - Continuing past an item that will not save, rather than failing the whole job
    - Detecting an object already imported by an earlier job, and recording a per-item outcome.    

Must not
    - Read source-actor rows. This module may import `testbed.core.models` to write the destination
      side; anything belonging to the source must arrive over HTTP, as a stranger's would
    - Transform. What arrives here is already final
    - Abort the whole transfer on one bad item. A single object that will not save is an item outcome, not a job failure
"""
