from django.urls import reverse

ACTIVITY_STREAM_CONTEXT = "https://www.w3.org/ns/activitystreams"
LOLA_CONTEXT = "https://swicg.github.io/activitypub-data-portability/lola"
BLOCKED_CONTEXT = "https://purl.archive.org/socialweb/blocked"

# Basic context used in most responses
def build_basic_context():
    return ACTIVITY_STREAM_CONTEXT

# Return the extended context used specifically for Actor responses
# Includes blocked collection support (FEP-c648)
def build_actor_context():
    return [
        ACTIVITY_STREAM_CONTEXT,
        BLOCKED_CONTEXT,
        LOLA_CONTEXT
    ]

def build_url(request, name, **kwargs):
    return request.build_absolute_uri(reverse(name, kwargs=kwargs))

def build_id_url(type_name, obj_id, request):
    """
    Build dynamic URLs based on the current request.
    This ensures URLs work in development, production, and any deployment environment.
    """
    base_url = f"{request.scheme}://{request.get_host()}"
    return f"{base_url}/api/{type_name}/{obj_id}/"

def build_actor_id(actor_id, request):
    return build_url(request, "actor-detail", pk=actor_id)

def build_activity_id(activity_kind, activity_id, request):
    return build_id_url(f"activities/{activity_kind}", activity_id, request)

def build_note_id(note_id, request):
    return build_id_url("notes", note_id, request)

def build_outbox_id(actor_id, request):
    return build_url(request, "actor-outbox", pk=actor_id)
