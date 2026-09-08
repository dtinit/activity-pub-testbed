"""
The lifecycle of one transfer: what stage it is in, and what the next bounded step is.

Owns
    - Deriving the working phase from the job's data rather than storing it, so that no crash
      between a data write and a status write can leave a row describing a phase its data does not
      support. Only the coarse `TransferJob.state` is persisted, and only because a computed
      property cannot be indexed or filtered. The five conditions, and what each one reads:

          no endpoints              -> discover              (no field yet)
          endpoints, no token       -> a human is clicking   (no field yet)
          collections remaining     -> fetch the next one    `progress`
          none remaining            -> finished              `progress`
          retry_when in the future  -> not ready, come back  `retry_when`

      All five sit inside `ACTIVE`, and are only asked while a job is there. Four say where inside
      it; "none remaining" is the one that ends it, writing `FINISHED`. `FAILED` is not among them, it
      comes from a step recording an `error` and can interrupt any of the five rather than
      following one. So `state` answers "should anyone still be working on this" and the conditions
      answer "what is the next unit of work", with the second only asked when the first says yes.
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

import logging

logger = logging.getLogger(__name__)

# The single key this module owns inside TransferJob.progress
COLLECTIONS_KEY = "collections"

# Saving progress touches two columns and no others. `updated_at` has to be named explicitly --
# auto_now only fires for fields included in a partial save, and a job whose updated_at stops moving
# is how the status page and the job-timeout rule recognise a stuck run.
_PROGRESS_UPDATE_FIELDS = ["progress", "updated_at"]


def get_collection_progress(job, collection):
    """
    Return one collection's resume state, or an empty dict if it has none yet.

    The return value is a copy. Callers that mutate what they read would otherwise change the
    job in memory without persisting it, which produces a resume position that exists in the
    process and not in the database, which is the precise failure this whole model set exists to prevent.
    """
    progress = job.progress or {}
    collections = progress.get(COLLECTIONS_KEY, {})
    entry = collections.get(collection, {})

    return dict(entry)


def set_collection_progress(job, collection, **values):
    """
    Merge `values` into one collection's resume state and persist immediately.

    Nothing here mutates what the job already holds. Every level is copied before it is changed, and
    the new value is only adopted if the save succeeds, so a job in memory can never carry a resume
    position the row does not have, which is the failure `get_collection_progress` describes.

    Returns a copy of the collection's state after the merge.
    """
    # Copy at each level rather than mutating in place. Leaves the job's own dict untouched until we commit
    progress = dict(job.progress or {})
    collections = dict(progress.get(COLLECTIONS_KEY, {}))
    entry = dict(collections.get(collection, {}))
    entry.update(values)
    collections[collection] = entry
    progress[COLLECTIONS_KEY] = collections

    # Adopt the new values only if they reach the database. If the save raises, put back what the
    # job had before, so the in-memory object and the row fail together instead of drifting apart.

    # `updated_at` has to be restored as well as `progress`. It is auto_now, and Django's pre_save
    # sets it on the instance before the UPDATE is attempted. Without this the failed job would
    # carry a fresher timestamp than its row does, which is how the status page and the job-timeout rule recognise a stuck run.
    previous_progress = job.progress
    previous_updated_at = job.updated_at
    job.progress = progress
    try:
        job.save(update_fields=_PROGRESS_UPDATE_FIELDS)
    except Exception:
        job.progress = previous_progress
        job.updated_at = previous_updated_at
        raise

    logger.debug(
        "Transfer job %s: progress updated for collection '%s' (keys: %s)",
        job.pk,
        collection,
        ", ".join(sorted(values)) or "none",
    )

    return dict(entry)
