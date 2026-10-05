from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from testbed.core.models import Actor, Blocked, Following, LikeActivity, Note
from testbed.core.tests.helpers import lola_client, source_actor_for
from testbed.core.utils.provisioning import LIKE_COUNT, VISIBILITIES, provision_actor_content


# production refuses `seed`, so what a signup provisions for itself is all its collections will ever hold
@pytest.mark.django_db
def test_signup_fills_every_collection_without_seed(settings):
    settings.ALLOWED_SEED_COMMAND = False
    actor = source_actor_for()
    client = lola_client(actor)

    for name in (
        "content-collection",
        "following-collection",
        "followers-collection",
        "blocked-collection",
        "liked-collection",
    ):
        assert client.get(reverse(name, kwargs={"pk": actor.pk})).data["totalItems"] > 0, name


# A destination preserving `published` (§7.1.7) needs dates worth preserving
@pytest.mark.django_db
def test_provisioned_notes_span_months():
    published = source_actor_for().notes.values_list("published", flat=True)

    assert max(published) - min(published) > timedelta(days=90)


# Provisioned Likes span every visibility. A new account exercises the owner's full liked collection (LOLA §6.4)
@pytest.mark.django_db
def test_every_provisioned_like_reaches_its_owner():
    actor = source_actor_for()
    visibilities = set(LikeActivity.objects.filter(actor=actor).values_list("visibility", flat=True))
    liked = lola_client(actor).get(reverse("liked-collection", kwargs={"pk": actor.pk})).data

    assert visibilities == set(VISIBILITIES)
    assert liked["totalItems"] == LIKE_COUNT


@pytest.mark.django_db
def test_scope_unlocks_more_of_the_outbox():
    actor = source_actor_for()
    client = lola_client(actor)
    url = reverse("actor-outbox", kwargs={"pk": actor.pk})

    assert APIClient().get(url).data["totalItems"] < client.get(url).data["totalItems"]


# A re-run replaces instead of doubling, and leaves the seeded population's local rows alone
@pytest.mark.django_db
def test_reprovisioning_is_idempotent():
    actor = source_actor_for()
    local = Following.objects.create(actor=actor, target_actor=source_actor_for())

    def counts():
        outbox = actor.portability_outbox
        return [
            actor.notes.count(),
            actor.following_relationships.count(),
            actor.follower_relationships.count(),
            actor.blocking_relationships.count(),
            outbox.activities_create.count(),
            outbox.activities_like.count(),
            outbox.activities_follow.count(),
        ]

    before = counts()
    provision_actor_content(actor)

    assert counts() == before
    assert Following.objects.filter(pk=local.pk).exists()


@pytest.mark.django_db
def test_provisioning_failure_at_signup_propagates_and_rolls_back(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("provisioning failed")

    monkeypatch.setattr(Blocked.objects, "bulk_create", fail)

    with pytest.raises(RuntimeError):
        User.objects.create_user("broken", "broken@example.com", "x")

    assert Actor.objects.filter(user__username="broken").count() == 2
    assert not Note.objects.filter(actor__user__username="broken").exists()


# Seed fabricates accounts with known passwords, so it must keep refusing where it is not allowed
@pytest.mark.django_db
def test_seed_is_refused_where_not_allowed(settings):
    settings.ALLOWED_SEED_COMMAND = False

    call_command("seed", "--no-prompt", stdout=StringIO())

    assert not User.objects.exists()
