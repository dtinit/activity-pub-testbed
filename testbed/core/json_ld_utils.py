class JsonLDContext:
    ACTIVITY_STREAM = "https://www.w3.org/ns/activitystreams"
    LOLA = "https://swicg.github.io/activitypub-data-portability/lola.jsonld"

# Return the basic context used in most responses
def build_basic_context():
    return JsonLDContext.ACTIVITY_STREAM

# Return the extended context used specifcally for Actor responses
def build_actor_context():
    return [
        JsonLDContext.ACTIVITY_STREAM,
        JsonLDContext.LOLA
    ]

def build_id_url(type_name, obj_id, request=None):
    """
    Build dynamic URLs based on the current request.
    This ensures URLs work in development, production, and any deployment environment.
    """
    if request:
        base_url = f"{request.scheme}://{request.get_host()}"
        return f"{base_url}/api/{type_name}/{obj_id}"
    else:
        # Fallback for cases where request is not available (testing, etc.)
        return f"https://example.com/{type_name}/{obj_id}"

def build_actor_id(actor_id, request=None):
    if request:
        base_url = f"{request.scheme}://{request.get_host()}"
        return f"{base_url}/api/actors/{actor_id}"
    else:
        return f"https://example.com/actors/{actor_id}"

def build_activity_id(activity_id, request=None):
    if request:
        base_url = f"{request.scheme}://{request.get_host()}"
        return f"{base_url}/api/activities/{activity_id}"
    else:
        return f"https://example.com/activities/{activity_id}"

def build_note_id(note_id, request=None):
    if request:
        base_url = f"{request.scheme}://{request.get_host()}"
        return f"{base_url}/api/notes/{note_id}"
    else:
        return f"https://example.com/notes/{note_id}"

# Build outbox URL with dynamic base URL
def build_outbox_id(actor_id, request=None):
    if request:
        base_url = f"{request.scheme}://{request.get_host()}"
        return f"{base_url}/api/actors/{actor_id}/outbox"
    else:
        # Fallback for cases where request is not available
        return f"https://example.com/actors/{actor_id}/outbox"
