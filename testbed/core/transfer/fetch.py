"""
Reading collections off a source server, one page at a time.

Owns
    - Walking a collection from its `first` page through each `next` link until the links run out
    - Reading `orderedItems` (and the collection envelope generally) without assuming a page shape
    - Capturing each raw response as an artifact before anything interprets it
    - Counting items and pages for progress reporting
    - Reporting where a walk stopped so it can resume from that exact page

Must not
    - Import `testbed.core.models`. In loopback, the rows live in the same database as the
      fetching process, so a direct read is trivially available yet invisible in review and
      it silently drops the pagination, token, and envelope contracts in one line.
      Everything this module reads must arrive over HTTP via `transport.py`.
    - Treat an out-of-range page as an error. Terminates cleanly rather than mistaking the
      end of a collection for a failure.
    - Decide what a `429` means. The typed exception comes from `transport.py`; pausing the job and
      resuming it belongs to `jobs.py`.
    - Transform or save anything. What comes off the wire is recorded as fetched; rewriting is
      `transform.py`'s job and persisting is `storage.py`'s.
"""
