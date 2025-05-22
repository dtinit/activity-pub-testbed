from testbed.core.models import LikeActivity


def test_actor_json_ld(actor):
    json_ld = actor.get_json_ld()
    assert json_ld["@context"] == [
        "https://www.w3.org/ns/activitystreams",
        "https://swicg.github.io/activitypub-data-portability/lola.jsonld",
    ]
    assert json_ld["type"] == "Person"
    assert json_ld["preferredUsername"] == actor.user.username
    assert json_ld["name"] == actor.user.get_full_name() or actor.user.username
    assert json_ld["previously"] == actor.previously
    assert json_ld["id"] == f"https://example.com/users/{actor.user.username}"


def test_note_json_ld(note):
    json_ld = note.get_json_ld()
    assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["type"] == "Note"
    assert json_ld["content"] == note.content
    assert json_ld["actor"] == f"https://example.com/users/{note.actor.user.username}"
    assert json_ld["id"] == f"https://example.com/notes/{note.id}"
    assert json_ld["visibility"] == note.visibility
    assert json_ld["published"] == note.published.isoformat()


def test_create_activity_json_ld(create_activity):
    json_ld = create_activity.get_json_ld()
    assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["type"] == "Create"
    assert json_ld["id"] == f"https://example.com/activities/{create_activity.id}"
    assert json_ld["actor"] == f"https://example.com/users/{create_activity.actor.user.username}"
    assert json_ld["published"] == create_activity.timestamp.isoformat()
    assert json_ld["visibility"] == create_activity.visibility
    
    # Check object based on activity type (Note or Actor creation)
    if create_activity.note:
        assert json_ld["object"]["type"] == "Note"
    else:
        assert json_ld["object"]["type"] == "Person"


def test_like_activity_json_ld_local(like_activity):
    json_ld = like_activity.get_json_ld()
    assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["type"] == "Like"
    assert json_ld["id"] == f"https://example.com/activities/{like_activity.id}"
    assert json_ld["actor"] == f"https://example.com/users/{like_activity.actor.user.username}"
    assert json_ld["published"] == like_activity.timestamp.isoformat()
    assert json_ld["visibility"] == like_activity.visibility

    # Check local object structure
    assert json_ld["object"]["type"] == "Note"
    assert json_ld["object"]["content"] == like_activity.note.content
    assert json_ld["object"]["actor"] == f"https://example.com/users/{like_activity.note.actor.user.username}"
    assert json_ld["object"]["id"] == f"https://example.com/notes/{like_activity.note.id}"


def test_like_activity_json_ld_remote(actor):
    remote_like = LikeActivity.objects.create(
        actor=actor,
        note=None,  # No local note for remote likes
        object_url="https://mastodon.social/notes/123",
        object_data={
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Note",
            "actor": "https://mastodon.social/users/remote_user",
            "content": "A remote note",
            "published": "2023-01-01T00:00:00Z",
            "visibility": "public",
        },
        visibility="public",
    )

    json_ld = remote_like.get_json_ld()
    assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["type"] == "Like"
    assert json_ld["actor"] == f"https://example.com/users/{actor.user.username}"
    assert json_ld["published"] == remote_like.timestamp.isoformat()
    assert json_ld["visibility"] == "public"

    # Check remote object structure
    assert json_ld["object"]["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["object"]["id"] == "https://mastodon.social/notes/123"
    assert json_ld["object"]["type"] == "Note"
    assert json_ld["object"]["content"] == "A remote note"
    assert json_ld["object"]["actor"] == "https://mastodon.social/users/remote_user"


def test_follow_activity_json_ld(follow_activity):
    json_ld = follow_activity.get_json_ld()
    assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["type"] == "Follow"
    assert json_ld["id"] == f"https://example.com/activities/{follow_activity.id}"
    assert json_ld["actor"] == f"https://example.com/users/{follow_activity.actor.user.username}"
    assert json_ld["published"] == follow_activity.timestamp.isoformat()
    assert json_ld["visibility"] == follow_activity.visibility
    
    # Check target actor structure
    assert json_ld["object"]["type"] == "Person"
    assert json_ld["object"]["preferredUsername"] == follow_activity.target_actor.user.username


def test_outbox_json_ld(outbox):
    json_ld = outbox.get_json_ld()
    assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["type"] == "OrderedCollection"
    assert json_ld["id"] == f"https://example.com/users/{outbox.actor.user.username}/outbox"
    assert "totalItems" in json_ld
    assert isinstance(json_ld["items"], list)
    
    # Verify items are in reverse chronological order
    if len(json_ld["items"]) > 1:
        timestamps = [item["published"] for item in json_ld["items"]]
        assert timestamps == sorted(timestamps, reverse=True)