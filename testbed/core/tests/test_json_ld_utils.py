import pytest
from testbed.core.json_ld_utils import (
    ACTIVITY_STREAM_CONTEXT,
    BLOCKED_CONTEXT,
    PREVIOUSLY_TERM,
    build_basic_context,
    build_actor_context,
    build_id_url,
    build_actor_id,
    build_activity_id,
    build_note_id,
    build_outbox_id,
)

# Test that context URLs are correct
def test_json_ld_context_constants():
    assert ACTIVITY_STREAM_CONTEXT == "https://www.w3.org/ns/activitystreams"
    assert BLOCKED_CONTEXT == "https://purl.archive.org/socialweb/blocked"

# Test basic context builder returns single URL
def test_build_basic_context():
    context = build_basic_context()
    assert context == ACTIVITY_STREAM_CONTEXT
    assert isinstance(context, str)

def test_build_actor_context():
    assert build_actor_context() == [ACTIVITY_STREAM_CONTEXT, BLOCKED_CONTEXT, PREVIOUSLY_TERM]

# Test base URL builder function
def test_build_id_url(mock_request):
    url = build_id_url("test", 123, mock_request)
    assert url == "http://testserver/api/test/123/"

def test_build_actor_id(mock_request):
    actor_id = build_actor_id(123, mock_request)
    assert actor_id == "http://testserver/api/actors/123/"

def test_activity_ids_are_unique_across_kinds(mock_request):
    ids = [
        build_activity_id(activity_kind, 123, mock_request)
        for activity_kind in ("create", "like", "follow")
    ]
    assert ids == [
        "http://testserver/api/activities/create/123/",
        "http://testserver/api/activities/like/123/",
        "http://testserver/api/activities/follow/123/",
    ]

def test_build_note_id(mock_request):
    note_id = build_note_id(123, mock_request)
    assert note_id == "http://testserver/api/notes/123/"

def test_build_outbox_id(mock_request):
    outbox_id = build_outbox_id(123, mock_request)
    assert outbox_id == "http://testserver/api/actors/123/outbox/"
