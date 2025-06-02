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

def build_id_url(type_name, obj_id):
    return f"https://example.com/{type_name}/{obj_id}"

def build_actor_id(actor_id):
    return build_id_url("actors", actor_id)

def build_activity_id(activity_id):
    return build_id_url("activities", activity_id)

def build_note_id(note_id):
    return build_id_url("notes", note_id)

def build_outbox_id(actor_id):
    return f"https://example.com/actors/{actor_id}/outbox"