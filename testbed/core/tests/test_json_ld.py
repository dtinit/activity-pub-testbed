from testbed.core.models import LikeActivity


def test_actor_json_ld(actor):
    json_ld = actor.get_json_ld()
    assert json_ld['type'] == 'Person'
    assert json_ld['preferredUsername'] == actor.username
    assert json_ld['previously'] == actor.previously
    assert '@context' in json_ld

def test_note_json_ld(note):
    json_ld = note.get_json_ld()
    assert json_ld['type'] == 'Note'
    assert json_ld['content'] == note.content
    assert json_ld['actor'] == f'https://example.com/users/{note.actor.username}'
    assert '@context' in json_ld

def test_create_activity_json_ld(create_activity):
    json_ld = create_activity.get_json_ld()
    assert json_ld['type'] == 'Create'
    assert 'object' in json_ld
    assert '@context' in json_ld

# Test json-ld structure for local note likes
def test_like_activity_json_ld_local(like_activity):
    json_ld = like_activity.get_json_ld()
    assert json_ld['type'] == 'Like'
    assert '@context' in json_ld

    # Check local object structure
    assert 'object' in json_ld
    assert json_ld['object']['type'] == 'Note'
    assert '@context' in json_ld['object']
    assert 'content' in json_ld['object']
    assert 'actor' in json_ld['object']
    assert 'id' in json_ld['object']

# Test json-ld structure for remote note likes
def test_like_activity_json_ld_remote(actor):
    remote_like = LikeActivity.objects.create(
        actor=actor,
        object_url="https://mastodon.social/notes/123",
        object_data={
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Note",
            "actor": "https://mastodon.social/users/remote_user",
            "content": "A remote note",
            "published": "2023-01-01T00:00:00Z",
            "visibility": "public",
        },
        visibility="public"
    )

    json_ld = remote_like.get_json_ld()

    # Check basic Like structure
    assert json_ld['type'] == 'Like'
    assert '@context' in json_ld

    # Check remote object structure
    assert 'object' in json_ld
    assert json_ld['object']['@context'] == "https://www.w3.org/ns/activitystreams"
    assert json_ld['object']['id'] == "https://mastodon.social/notes/123"
    assert json_ld['object']['type'] == "Note"
    assert json_ld['object']['content'] == "A remote note"
    assert json_ld['object']['actor'] == "https://mastodon.social/users/remote_user"

def test_follow_activity_json_ld(follow_activity):
    json_ld = follow_activity.get_json_ld()
    assert json_ld['type'] == 'Follow'
    assert 'object' in json_ld
    assert '@context' in json_ld

def test_outbox_activity_types(outbox):
    json_ld = outbox.get_json_ld()
    assert json_ld['type'] == 'OrderedCollection'
    assert '@context' in json_ld
    assert 'totalItems' in json_ld
    assert 'items' in json_ld
