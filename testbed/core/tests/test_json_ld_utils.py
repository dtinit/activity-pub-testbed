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
def test_build_id_url():
    url = build_id_url("test", 123)
    assert url == "https://example.com/test/123"

def test_build_actor_id():
    actor_id = build_actor_id(123)
    assert actor_id == "https://example.com/actors/123"

def test_build_activity_id():
    activity_id = build_activity_id(123)
    assert activity_id == "https://example.com/activities/123"

def test_build_note_id():
    note_id = build_note_id(123)
    assert note_id == "https://example.com/notes/123"

def test_build_outbox_id():
    outbox_id = build_outbox_id(123)
    assert outbox_id == "https://example.com/actors/123/outbox"