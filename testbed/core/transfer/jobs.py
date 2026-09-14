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

from django.db import models

logger = logging.getLogger(__name__)


class Collection(models.TextChoices):
    """
    `followers` is deliberately absent. LOLA §6.6 Not Fetched: the Followers collection
    "will be reconstructed to the extent that followers, if notified of the account move,
    choose to follow the account at its new location.". Fetching it for inspection is fine
    and its pages still land in artifacts; recording an imported follower is not, so the schema cannot express it.
    """

    CONTENT = "content", "Content"
    OUTBOX = "outbox", "Outbox"
    FOLLOWING = "following", "Following"
    BLOCKED = "blocked", "Blocked"
    LIKED = "liked", "Liked"


# The single key this module owns inside TransferJob.progress
COLLECTIONS_KEY = "collections"

# Saving progress touches two columns and no others. `updated_at` has to be named explicitly --
# auto_now only fires for fields included in a partial save, and a job whose updated_at stops moving
# is how the status page and the job-timeout rule recognise a stuck run.
_PROGRESS_UPDATE_FIELDS = ["progress", "updated_at"]


# Both `get_collection_progress()` and `set_collection_progress()` raise ValueError for a name outside Collection

def get_collection_progress(job, collection):
    """
    Return one collection's resume state, or an empty dict if it has none yet.

    The return value is a copy. Callers that mutate what they read would otherwise change the
    job in memory without persisting it, which produces a resume position that exists in the
    process and not in the database.
    """
    collection = Collection(collection)

    progress = job.progress or {}
    collections = progress.get(COLLECTIONS_KEY, {})
    entry = collections.get(collection, {})

    return dict(entry)

def set_collection_progress(job, collection, **values):
    """
    Merge `values` into one collection's resume state and persist immediately.

    Every level is copied before it is changed, so `job.progress` stays as it was until the
    assignment just before the save. That assignment is the line that applies the merge.

    If the save fails, the job in memory keeps progress its row does not have.
    The request ends, and the next one loads the job fresh from the database.

    Returns a copy of the collection's state after the merge.
    """
    collection = Collection(collection)

    # Copy at each level rather than mutating in place. Leaves the job's own dict untouched until we commit
    progress = dict(job.progress or {})
    collections = dict(progress.get(COLLECTIONS_KEY, {}))
    entry = dict(collections.get(collection, {}))
    entry.update(values)
    collections[collection] = entry
    progress[COLLECTIONS_KEY] = collections

    job.progress = progress
    job.save(update_fields=_PROGRESS_UPDATE_FIELDS)

    logger.debug(
        "Transfer job %s: progress updated for collection '%s' (keys: %s)",
        job.pk,
        collection,
        ", ".join(sorted(values)) or "none",
    )

    return dict(entry)
