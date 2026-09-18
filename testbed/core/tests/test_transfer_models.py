from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from testbed.core.factories import TransferJobFactory
from testbed.core.models import TransferJob
from testbed.core.tests.helpers import destination_actor_for


# Vocabulary


def test_state_is_coarse_and_has_exactly_three_values():
    assert set(TransferJob.State.values) == {"active", "finished", "failed"}


# Ownership -- structural, not validated


def test_the_jobs_owner_follows_its_destination_actor():
    # There is only one owner link, so the two cannot drift apart
    job = TransferJobFactory()
    assert job.user == job.destination_actor.user

    someone_else = destination_actor_for()
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
        destination_actor=destination_actor_for(),
        source_base_url="https://source.example",
    )

    assert job.policy == {"dry_run": True}
    assert job.policy.get("dry_run", True) is True


def test_url_fields_are_long_enough_for_activitypub_ids():
    assert TransferJob._meta.get_field("source_base_url").max_length == 500
    assert TransferJob._meta.get_field("authorized_actor_url").max_length == 500


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
    actor = destination_actor_for()
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


def test_deleting_the_user_deletes_their_jobs():
    # Deleting an account takes its transfer history with it
    job = TransferJobFactory()

    job.user.delete()

    assert TransferJob.objects.count() == 0
