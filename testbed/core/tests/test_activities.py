import pytest


def test_activity_creation(activity):
    assert activity.actor is not None
    assert activity.note is not None
    assert activity.type in ['Create', 'Like', 'Update', 'Follow', 'Announce', 'Delete', 'Undo', 'Flag']
    assert activity.visibility in ['public', 'private', 'followers-only']

def test_activity_str_representation(activity):
    assert activity.type in str(activity)
    assert activity.actor.username in str(activity)
