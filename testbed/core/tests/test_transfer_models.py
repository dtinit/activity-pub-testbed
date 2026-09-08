from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from testbed.core.factories import (
    TransferJobFactory,
    TransferredItemFactory,
    UserWithActorsFactory,
)
from testbed.core.models import Actor, TransferJob, TransferredItem


def destination_actor():
    # The signal already made one per user; a second would collide on the role invariant
    return UserWithActorsFactory().actors.get(role=Actor.ROLE_DESTINATION)


# Vocabulary


def test_state_is_coarse_and_has_exactly_three_values():
    assert set(TransferJob.State.values) == {"active", "finished", "failed"}


def test_item_collections_exclude_followers():
    # LOLA §6.6 Not Fetched: the Followers collection is reconstructed by followers choosing
    # to re-follow, never copied. The schema must not be able to record an imported follower.
    assert set(TransferredItem.Collection.values) == {
        "content",
        "outbox",
        "following",
        "blocked",
        "liked",
    }
    assert "followers" not in TransferredItem.Collection.values


# Ownership -- structural, not validated


def test_the_jobs_owner_follows_its_destination_actor():
    # There is only one owner link, so the two cannot drift apart
    job = TransferJobFactory()
    assert job.user == job.destination_actor.user

    someone_else = destination_actor()
    job.destination_actor = someone_else

    assert job.user == someone_else.user


# Creation and defaults


def test_a_job_starts_active_with_empty_state():
    # The starting contract other code depends on: the JSON columns are dicts, not None, which is
    # what the fallbacks in transfer/jobs.py assume
    job = TransferJobFactory()

    assert job.state == TransferJob.State.ACTIVE
    assert job.progress == {}
    assert job.artifacts == {}
    assert job.error == ""
    assert job.retry_when is None
    assert job.source_actor_url is None
    assert job.authorized_actor_url is None


def test_a_job_created_without_a_policy_defaults_to_dry_run():
    job = TransferJob.objects.create(
        destination_actor=destination_actor(),
        source_base_url="https://source.example",
    )

    assert job.policy == {"dry_run": True}
    assert job.policy.get("dry_run", True) is True


def test_url_fields_are_long_enough_for_activitypub_ids():
    assert TransferJob._meta.get_field("source_base_url").max_length == 500
    assert TransferJob._meta.get_field("authorized_actor_url").max_length == 500
    assert TransferredItem._meta.get_field("source_id").max_length == 500
    assert TransferredItem._meta.get_field("destination_id").max_length == 500


# A failed job must say why


def test_failing_a_job_without_a_reason_is_refused_by_the_database():
    # A CheckConstraint rather than a save() override: an override is bypassed by update(),
    # bulk_create() and raw SQL, and this model deliberately has no save() override any more.
    job = TransferJobFactory()
    job.state = TransferJob.State.FAILED

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            job.save()


def test_failing_a_job_with_a_reason_is_allowed():
    job = TransferJobFactory()
    job.state = TransferJob.State.FAILED
    job.error = "source unreachable"

    job.save()

    job.refresh_from_db()
    assert job.state == TransferJob.State.FAILED
    assert job.error == "source unreachable"


# Resuming


def test_jobs_ready_to_resume_is_a_single_queryset():
    actor = destination_actor()
    elapsed = TransferJobFactory(
        destination_actor=actor, retry_when=timezone.now() - timedelta(minutes=1)
    )
    TransferJobFactory(
        destination_actor=actor, retry_when=timezone.now() + timedelta(hours=1)
    )

    ready = TransferJob.objects.filter(
        state=TransferJob.State.ACTIVE, retry_when__lte=timezone.now()
    )

    assert list(ready) == [elapsed]


# The ledger


def test_items_are_reachable_from_the_job():
    job = TransferJobFactory()
    TransferredItemFactory(job=job, collection=TransferredItem.Collection.CONTENT)
    TransferredItemFactory(job=job, collection=TransferredItem.Collection.OUTBOX)
    TransferredItemFactory()  # a second job's item, must not leak in

    assert job.items.count() == 2
    assert job.items.filter(collection="outbox").count() == 1


def test_the_same_source_id_may_appear_in_two_collections():
    # A Note is served raw in `content` (fidelity, section 6.3) and Create-wrapped in `outbox`
    # (history), so two rows sharing a source_id is correct rather than duplication. This is one of
    # the reasons there is no unique constraint on (job, collection, source_id).
    job = TransferJobFactory()
    source_id = "https://source.example/notes/11"

    TransferredItemFactory(
        job=job, collection="content", source_id=source_id, object_type="Note"
    )
    TransferredItemFactory(
        job=job, collection="outbox", source_id=source_id, object_type="Create"
    )

    assert job.items.filter(source_id=source_id).count() == 2


def test_a_failed_item_carries_its_own_reason():
    # Per-object failures live here
    job = TransferJobFactory()
    TransferredItemFactory(
        job=job,
        collection="content",
        outcome=TransferredItem.Outcome.FAILED,
        destination_id=None,
        detail={"reason": "unparseable published date"},
    )
    TransferredItemFactory(
        job=job,
        collection="following",
        outcome=TransferredItem.Outcome.FAILED,
        destination_id=None,
        detail={"reason": "actor no longer resolves"},
    )

    reasons = {item.detail["reason"] for item in job.items.filter(outcome="failed")}
    assert len(reasons) == 2
    assert job.error == ""  # the job itself has not failed


def test_deleting_the_user_deletes_their_jobs_and_items():
    # Deleting an account takes its transfer history with it
    job = TransferJobFactory()
    TransferredItemFactory(job=job)

    job.user.delete()

    assert TransferJob.objects.count() == 0
    assert TransferredItem.objects.count() == 0
