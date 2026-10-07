import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from testbed.core.factories import (
    CreateActivityFactory,
    FollowActivityFactory,
    IsolatedActorFactory,
    LikeActivityFactory,
    NoteFactory,
)
from testbed.core.json_ld_builders import (
    build_create_activity_json_ld,
    build_follow_activity_json_ld,
    build_like_activity_json_ld,
    build_note_json_ld,
)
from testbed.core.tests.helpers import lola_client


def detail_url(route, obj, actor=None):
    return reverse(route, kwargs={"pk": (actor or obj.actor).pk, "object_pk": obj.pk})


# ActivityPub §3.1: an object dereferences, and a public one is served to anyone exactly as the collections serve it.
@pytest.mark.django_db
@pytest.mark.parametrize("route, object_factory, related, build", [
    ("note-detail", NoteFactory, {}, build_note_json_ld),
    ("create-activity-detail", CreateActivityFactory, {"note": None}, build_create_activity_json_ld),
    ("like-activity-detail", LikeActivityFactory, {"remote": True}, build_like_activity_json_ld),
    ("follow-activity-detail", FollowActivityFactory, {"remote": True}, build_follow_activity_json_ld),
])
def test_public_object_is_served_to_anyone(basic_auth_context, route, object_factory, related, build):
    obj = object_factory(actor=IsolatedActorFactory(prefix="object_owner"), visibility="public", **related)

    response = APIClient().get(detail_url(route, obj), HTTP_ACCEPT="application/activity+json")

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "application/activity+json"
    assert response.data == build(obj, basic_auth_context)
    # The id is where the object lives, it names the URL just fetched
    assert response.data["id"] == response.wsgi_request.build_absolute_uri()


# Anything other than "public" is strict. Only a token bound to the owner gets through
@pytest.mark.django_db
@pytest.mark.parametrize("visibility", ["private", "followers-only"])
def test_non_public_object_is_seen_only_by_its_owner(visibility):
    owner = IsolatedActorFactory(prefix="hidden_owner")
    other = IsolatedActorFactory(prefix="hidden_other")
    url = detail_url("note-detail", NoteFactory(actor=owner, visibility=visibility))

    assert APIClient().get(url).status_code == status.HTTP_404_NOT_FOUND
    assert lola_client(other).get(url).status_code == status.HTTP_404_NOT_FOUND
    assert lola_client(owner).get(url).status_code == status.HTTP_200_OK


# A hidden object, a missing one and one under another actor all give the same 404
@pytest.mark.django_db
def test_hidden_missing_and_misplaced_objects_answer_alike():
    owner = IsolatedActorFactory(prefix="alike_owner")
    other = IsolatedActorFactory(prefix="alike_other")
    hidden = NoteFactory(actor=owner, visibility="private")
    public = NoteFactory(actor=owner, visibility="public")

    responses = [
        APIClient().get(detail_url("note-detail", hidden)),
        lola_client(other).get(detail_url("note-detail", hidden)),
        APIClient().get(reverse("note-detail", kwargs={"pk": owner.pk, "object_pk": 999999})),
        APIClient().get(detail_url("note-detail", public, actor=other)),
    ]

    answers = {(r.status_code, r.data["error_code"], r.data["detail"]) for r in responses}
    assert len(answers) == 1
    assert answers.pop()[:2] == (status.HTTP_404_NOT_FOUND, "object_not_found")


# LOLA §5: a token bound to another actor is refused on a public object, as on every dual-mode endpoint
@pytest.mark.django_db
def test_public_object_refuses_another_actors_token():
    owner = IsolatedActorFactory(prefix="refuse_owner")
    other = IsolatedActorFactory(prefix="refuse_other")
    url = detail_url("note-detail", NoteFactory(actor=owner, visibility="public"))

    response = lola_client(other).get(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["error_code"] == "actor_mismatch"
