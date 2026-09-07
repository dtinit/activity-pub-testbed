"""
The lifecycle of one transfer: what stage it is in, and what the next bounded step is.

Owns
    - Job state and its transitions (pending, discovering, authorizing, fetching, paused,
      dry_run_complete, committing, completed, failed).
    - `advance()`, which performs exactly one bounded unit of work and returns
    - resumption state, so a job paused on a `429` restarts at the page it stopped on rather than
      at the beginning; and the error and progress fields the status page reads.

Must not
    - Walk a whole collection inside one web request. `Dockerfile` runs `--workers 1 --threads 8`, so a Mode C
      self-call occupies one thread while waiting on another thread of the same service, and a multi-page fetch
      inside one request also risks Cloud Run's request timeout. Both failure modes are hangs rather than errors,
      which is why the unit of work is one collection page and the caller comes back for the next one.
    - Make HTTP calls, parse payloads, or transform objects. It sequences the modules that do.
    - Advance past a failure silently. A failed step is a recorded state, visible on the status page.
"""
