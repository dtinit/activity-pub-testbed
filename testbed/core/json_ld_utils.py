from django.urls import reverse

ACTIVITY_STREAM_CONTEXT = "https://www.w3.org/ns/activitystreams"
BLOCKED_CONTEXT = "https://purl.archive.org/socialweb/blocked"
# LOLA §7.1.8 gives `previously` no IRI yet and publishes no context that's why the term is defined here
PREVIOUSLY_TERM = {
    "previously": {
        "@id": "https://swicg.github.io/activitypub-data-portability/lola#previously",
        "@type": "@id",
        "@container": "@list",
    }
}

# Basic context used in most responses, extended with the `previously` term only when the object carries breadcrumbs
def build_basic_context(breadcrumbs=False):
    if breadcrumbs:
        return [ACTIVITY_STREAM_CONTEXT, PREVIOUSLY_TERM]
    return ACTIVITY_STREAM_CONTEXT

# Return the extended context used specifically for Actor responses
# Includes blocked collection support (FEP-c648) and the `previously` term
def build_actor_context():
    return [
        ACTIVITY_STREAM_CONTEXT,
        BLOCKED_CONTEXT,
        PREVIOUSLY_TERM,
    ]

def build_url(request, name, **kwargs):
    return request.build_absolute_uri(reverse(name, kwargs=kwargs))

def build_actor_id(actor_id, request):
    return build_url(request, "actor-detail", pk=actor_id)

def build_activity_id(activity_kind, activity, request):
    return build_url(request, f"{activity_kind}-activity-detail", pk=activity.actor_id, object_pk=activity.pk)

def build_note_id(note, request):
    return build_url(request, "note-detail", pk=note.actor_id, object_pk=note.pk)

def build_outbox_id(actor_id, request):
    return build_url(request, "actor-outbox", pk=actor_id)
