import pytest


def test_note_creation(note):
    assert note.actor is not None
    assert note.content is not None
    assert note.published is not None
    assert note.visibility in ['public', 'private', 'followers-only']

def test_note_str_representation(note):
    assert str(note).startswith('Note by')
    assert note.content[:30] in str(note)
