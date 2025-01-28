import pytest


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

def test_like_activity_json_ld(like_activity):
    json_ld = like_activity.get_json_ld()
    assert json_ld['type'] == 'Like'
    assert 'object' in json_ld
    assert '@context' in json_ld

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
