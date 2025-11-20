import pytest
from testbed.core.json_ld_utils import (
    ACTIVITY_STREAM_CONTEXT,
    LOLA_CONTEXT,
    BLOCKED_CONTEXT,
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
    assert LOLA_CONTEXT == "https://swicg.github.io/activitypub-data-portability/lola"
    assert BLOCKED_CONTEXT == "https://purl.archive.org/socialweb/blocked"

# Test basic context builder returns single URL
def test_build_basic_context():
    context = build_basic_context()
    assert context == ACTIVITY_STREAM_CONTEXT
    assert isinstance(context, str)

# Test actor context builder returns list with all three URLs
def test_build_actor_context():
    context = build_actor_context()
    assert isinstance(context, list)
    assert len(context) == 3
    assert ACTIVITY_STREAM_CONTEXT in context
    assert BLOCKED_CONTEXT in context
    assert LOLA_CONTEXT in context

# Test base URL builder function
def test_build_id_url(mock_request):
    url = build_id_url("test", 123, mock_request)
    assert url == "http://testserver/api/test/123"

def test_build_actor_id(mock_request):
    actor_id = build_actor_id(123, mock_request)
    assert actor_id == "http://testserver/api/actors/123"

def test_build_activity_id(mock_request):
    activity_id = build_activity_id(123, mock_request)
    assert activity_id == "http://testserver/api/activities/123"

def test_build_note_id(mock_request):
    note_id = build_note_id(123, mock_request)
    assert note_id == "http://testserver/api/notes/123"

def test_build_outbox_id(mock_request):
    outbox_id = build_outbox_id(123, mock_request)
    assert outbox_id == "http://testserver/api/actors/123/outbox"
