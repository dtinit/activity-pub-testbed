import pytest

from testbed.core.factories import TransferJobFactory
from testbed.core.models import TransferJob
from testbed.core.transfer.jobs import Collection


# The collection vocabulary


def test_collections_exclude_followers():
    # LOLA §6.6 Not Fetched: the Followers collection is reconstructed by followers choosing
    # to re-follow, never copied.
    assert set(Collection.values) == {
        "content",
        "outbox",
        "following",
        "blocked",
        "liked",
    }
    assert "followers" not in Collection.values


def test_an_unknown_collection_is_rejected_on_write():
    # Without this a typo writes progress under a key nothing ever reads, and that collection
    # silently restarts from page 1 on every resume, re-importing what it already imported
    job = TransferJobFactory()

    with pytest.raises(ValueError):
        job.set_collection_progress("contnet", cursor="page-2")


def test_an_unknown_collection_is_rejected_on_read():
    # Reading is validated too. An unknown name would otherwise return {}, which is
    # indistinguishable from "this collection has not started yet"
    job = TransferJobFactory()

    with pytest.raises(ValueError):
        job.get_collection_progress("contnet")


# Reading and writing resume state


def test_unrecorded_collection_reads_as_empty():
    job = TransferJobFactory()

    assert job.get_collection_progress("content") == {}


def test_set_persists_to_the_database():
    # The whole point of the model: state must survive the request that wrote it
    job = TransferJobFactory()

    job.set_collection_progress("content", cursor="page-2", seen=20)

    reloaded = TransferJob.objects.get(pk=job.pk)
    assert reloaded.get_collection_progress("content") == {
        "cursor": "page-2",
        "seen": 20,
    }


def test_set_merges_rather_than_replaces():
    job = TransferJobFactory()
    job.set_collection_progress("content", cursor="page-1", seen=10)

    job.set_collection_progress("content", seen=20)

    reloaded = TransferJob.objects.get(pk=job.pk)
    assert reloaded.get_collection_progress("content") == {
        "cursor": "page-1",
        "seen": 20,
    }


def test_writing_one_collection_leaves_its_siblings_alone():
    # A fetch walk moves through collections one at a time.
    # Recording outbox's position must not lose where content got to
    job = TransferJobFactory()
    job.set_collection_progress("content", cursor="page-3")
    job.set_collection_progress("following", cursor="page-1")

    job.set_collection_progress("outbox", cursor="page-1")

    reloaded = TransferJob.objects.get(pk=job.pk)
    assert reloaded.get_collection_progress("content") == {"cursor": "page-3"}
    assert reloaded.get_collection_progress("following") == {"cursor": "page-1"}
    assert reloaded.get_collection_progress("outbox") == {"cursor": "page-1"}


def test_both_accessors_return_copies():
    # A caller mutating what either function handed back would change the job in memory without
    # persisting it, giving a resume position that exists in the process and not in the database.
    job = TransferJobFactory()
    job.set_collection_progress("content", cursor="page-1")

    from_get = job.get_collection_progress("content")
    from_set = job.set_collection_progress("content", seen=5)

    assert from_set == {"cursor": "page-1", "seen": 5}  # set returns the merged state

    from_get["cursor"] = "page-99"
    from_set["seen"] = 999

    assert job.get_collection_progress("content") == {"cursor": "page-1", "seen": 5}


def test_set_writes_only_the_progress_column():
    job = TransferJobFactory()
    TransferJob.objects.filter(pk=job.pk).update(state=TransferJob.State.FINISHED)

    # `job` still holds the stale in-memory state
    job.set_collection_progress("content", cursor="page-1")

    reloaded = TransferJob.objects.get(pk=job.pk)
    assert reloaded.state == TransferJob.State.FINISHED
    assert reloaded.get_collection_progress("content") == {"cursor": "page-1"}


def test_set_refreshes_updated_at():
    job = TransferJobFactory()
    before = TransferJob.objects.get(pk=job.pk).updated_at

    job.set_collection_progress("content", cursor="page-1")

    assert TransferJob.objects.get(pk=job.pk).updated_at > before
