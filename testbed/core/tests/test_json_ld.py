import pytest


def test_actor_json_ld(actor):
    json_ld = actor.get_json_ld()
    assert json_ld['type'] == 'Person'
    assert json_ld['preferredUsername'] == actor.username
    assert '@context' in json_ld

def test_note_json_ld(note):
    json_ld = note.get_json_ld()
    assert json_ld['type'] == 'Note'
    assert json_ld['content'] == note.content
    assert '@context' in json_ld

def test_activity_json_ld(activity):
    json_ld = activity.get_json_ld()
    assert json_ld['type'] == activity.type
    assert 'object' in json_ld
    assert '@context' in json_ld

def test_outbox_json_ld(outbox):
    json_ld = outbox.get_json_ld()
    assert json_ld['type'] == 'OrderedCollection'
    assert '@context' in json_ld
    assert json_ld['totalItems'] == outbox.activities.count()