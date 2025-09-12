import pytest
from testbed.core.json_ld_utils import (
    JsonLDContext,
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
    assert JsonLDContext.ACTIVITY_STREAM == "https://www.w3.org/ns/activitystreams"
    assert JsonLDContext.LOLA == "https://swicg.github.io/activitypub-data-portability/lola.jsonld"

# Test basic context builder returns single URL
def test_build_basic_context():
    context = build_basic_context()
    assert context == JsonLDContext.ACTIVITY_STREAM
    assert isinstance(context, str)

# Test actor context builder returns list with both URLs
def test_build_actor_context():
    context = build_actor_context()
    assert isinstance(context, list)
    assert len(context) == 2
    assert JsonLDContext.ACTIVITY_STREAM in context
    assert JsonLDContext.LOLA in context

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
