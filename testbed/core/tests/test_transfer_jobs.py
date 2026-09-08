from unittest.mock import patch

import pytest
from django.db import DatabaseError

from testbed.core.factories import TransferJobFactory
from testbed.core.models import TransferJob
from testbed.core.transfer.jobs import (
    get_collection_progress,
    set_collection_progress,
)


def test_unrecorded_collection_reads_as_empty():
    job = TransferJobFactory()

    assert get_collection_progress(job, "content") == {}


def test_set_persists_to_the_database():
    # The whole point of the model: state must survive the request that wrote it
    job = TransferJobFactory()

    set_collection_progress(job, "content", cursor="page-2", seen=20)

    reloaded = TransferJob.objects.get(pk=job.pk)
    assert get_collection_progress(reloaded, "content") == {
        "cursor": "page-2",
        "seen": 20,
    }


def test_set_merges_rather_than_replaces():
    job = TransferJobFactory()
    set_collection_progress(job, "content", cursor="page-1", seen=10)

    set_collection_progress(job, "content", seen=20)

    reloaded = TransferJob.objects.get(pk=job.pk)
    assert get_collection_progress(reloaded, "content") == {
        "cursor": "page-1",
        "seen": 20,
    }


def test_writing_one_collection_leaves_its_siblings_alone():
    # A fetch walk moves through collections one at a time.
    # Recording outbox's position must not lose where content got to
    job = TransferJobFactory()
    set_collection_progress(job, "content", cursor="page-3")
    set_collection_progress(job, "following", cursor="page-1")

    set_collection_progress(job, "outbox", cursor="page-1")

    reloaded = TransferJob.objects.get(pk=job.pk)
    assert get_collection_progress(reloaded, "content") == {"cursor": "page-3"}
    assert get_collection_progress(reloaded, "following") == {"cursor": "page-1"}
    assert get_collection_progress(reloaded, "outbox") == {"cursor": "page-1"}


def test_both_accessors_return_copies():
    # A caller mutating what either function handed back would change the job in memory without
    # persisting it, giving a resume position that exists in the process and not in the database.
    job = TransferJobFactory()
    set_collection_progress(job, "content", cursor="page-1")

    from_get = get_collection_progress(job, "content")
    from_set = set_collection_progress(job, "content", seen=5)

    assert from_set == {"cursor": "page-1", "seen": 5}  # set returns the merged state

    from_get["cursor"] = "page-99"
    from_set["seen"] = 999

    assert get_collection_progress(job, "content") == {"cursor": "page-1", "seen": 5}


def test_set_writes_only_the_progress_column():
    job = TransferJobFactory()
    TransferJob.objects.filter(pk=job.pk).update(state=TransferJob.State.FINISHED)

    # `job` still holds the stale in-memory state
    set_collection_progress(job, "content", cursor="page-1")

    reloaded = TransferJob.objects.get(pk=job.pk)
    assert reloaded.state == TransferJob.State.FINISHED
    assert get_collection_progress(reloaded, "content") == {"cursor": "page-1"}


def test_set_refreshes_updated_at():
    job = TransferJobFactory()
    before = TransferJob.objects.get(pk=job.pk).updated_at

    set_collection_progress(job, "content", cursor="page-1")

    assert TransferJob.objects.get(pk=job.pk).updated_at > before


def test_a_failed_save_leaves_memory_and_row_in_agreement():
    job = TransferJobFactory()
    set_collection_progress(job, "content", cursor="page-2")

    with patch.object(TransferJob, "save", side_effect=DatabaseError("boom")):
        with pytest.raises(DatabaseError):
            set_collection_progress(job, "outbox", cursor="page-3")

    row = TransferJob.objects.get(pk=job.pk)
    assert job.progress == row.progress
    assert job.updated_at == row.updated_at

    assert get_collection_progress(job, "outbox") == {}
    assert get_collection_progress(row, "outbox") == {}
