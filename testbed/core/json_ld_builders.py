from .json_ld_utils import (build_basic_context,
                            build_actor_context,
                            build_actor_id,
                            build_activity_id,
                            build_note_id,
                            build_outbox_id,
                            build_url)
from .oauth.utils import build_oauth_endpoint_url
from .models import CreateActivity, LikeActivity, FollowActivity

# AS2 name -> Note column for the §6.3 metadata. Served only when it holds a value
NOTE_METADATA = {
    "summary": "summary",
    "to": "to",
    "cc": "cc",
    "inReplyTo": "in_reply_to",
    "url": "url",
    "source": "source",
    "previously": "previously",
}

# Build JSON-LD Actor with LOLA compliance.
def build_actor_json_ld(actor, auth_context=None):
    """
    Build an ActivityPub Actor object with revised-LOLA portability discovery.

    - `endpoints.oauthMigrationEndpoint` MUST always be present
      for OAuth endpoint discovery (public visibility).
    - It is advertised in parallel with `endpoints.oauthAuthorizationEndpoint`.
      Both point at `/oauth/authorize/` endpoint, which is also the URL advertised in the RFC8414 metadata.
    - The `migration` object (outbox / content / following / blocked) is privacy-sensitive feature
      discovery and is only included when the request carries a valid portability-scoped token.
    
    Args:
        actor: The Actor model instance
        auth_context: Optional authentication context dict with keys:
            - is_authenticated: boolean
            - has_portability_scope: boolean  
            - request: HTTP request object
    
    Returns:
        Dict containing ActivityPub Actor with conditional LOLA fields
    """

    # Extract request for dynamic URL generation
    request = auth_context.get('request') if auth_context else None
    
    # Build actor URL
    actor_id = build_actor_id(actor.id, request)
    
    # The migration OAuth endpoint and the general OAuth authorization endpoint are the same URL,
    # so both `endpoints.*` fields resolve to it. Computed once and reused.
    oauth_authorize_url = build_oauth_endpoint_url(request)

    # Base ActivityPub Actor (always included)
    actor_data = {
        "@context": build_actor_context(),
        "type": "Person",
        "id": actor_id,
        "preferredUsername": actor.username,
        "name": actor.username,
        "inbox": f"{actor_id}inbox",  # no route serves the inbox yet, so reverse() cannot build it
        "previously": actor.previously or [],
        "endpoints": {
            "oauthAuthorizationEndpoint": oauth_authorize_url,
            "oauthMigrationEndpoint": oauth_authorize_url,
        },
    }

    # Privacy-sensitive fields ONLY with portability scope
    if auth_context and auth_context.get('has_portability_scope'):
        actor_data["outbox"] = build_url(request, "actor-outbox", pk=actor.id)
        actor_data["following"] = build_url(request, "following-collection", pk=actor.id)
        actor_data["followers"] = build_url(request, "followers-collection", pk=actor.id)
        actor_data["liked"] = build_url(request, "liked-collection", pk=actor.id)
        actor_data["blocked"] = build_url(request, "blocked-collection", pk=actor.id)

        # LOLA migration feature discovery
        actor_data["migration"] = {
            "outbox": build_url(request, "migration-outbox", pk=actor.id),
            "content": build_url(request, "migration-content", pk=actor.id),
            "following": build_url(request, "migration-following", pk=actor.id),
            "blocked": build_url(request, "migration-blocked", pk=actor.id),
        }

    return actor_data

# The fields of obj that hold a value under their AS2 names.
# empty ones are left out, never sent as null or []
def _non_empty(obj, fields):
    values = {key: getattr(obj, attr) for key, attr in fields.items()}
    return {key: value for key, value in values.items() if value}


def build_note_json_ld(note, auth_context=None):
    """Build Note JSON-LD with dynamic URL generation"""
    request = auth_context.get('request') if auth_context else None
    
    return {
        "@context": build_basic_context(breadcrumbs=bool(note.previously)),
        "type": "Note",
        "id": build_note_id(note, request),
        "attributedTo": build_actor_id(note.actor.id, request),
        "content": note.content,
        "published": note.published.isoformat(),
        "visibility": note.visibility,
        **_non_empty(note, NOTE_METADATA),
    }


def build_create_activity_json_ld(activity, auth_context=None):
    # Build Create Activity JSON-LD with dynamic URL generation
    request = auth_context.get('request') if auth_context else None
    
    json_ld = {
        "@context": build_basic_context(breadcrumbs=bool(activity.previously)),
        "type": "Create",
        "id": build_activity_id("create", activity, request),
        "actor": build_actor_id(activity.actor.id, request),
        "published": activity.timestamp.isoformat(),
        "visibility": activity.visibility,
        **_non_empty(activity, {"previously": "previously"}),
    }

    if activity.note:
        json_ld["object"] = build_note_json_ld(activity.note, auth_context)
    else:
        json_ld["object"] = build_actor_json_ld(activity.actor, auth_context)

    return json_ld


def build_like_object_json_ld(like, auth_context=None):
    """
    The object of a Like. What the Like activity carries and what the liked collection lists.

    A remote object is served as stored. A local Note is embedded only when it is public; any other
    visibility is served as its id alone, because the Note may belong to another account (LOLA §5).
    """
    request = auth_context.get('request') if auth_context else None

    if like.note is None:
        data = like.object_data or {}
        return {
            "@context": build_basic_context(breadcrumbs=bool(data.get("previously"))),
            **data,
            "id": like.object_url,
        }
    if like.note.visibility == "public":
        return build_note_json_ld(like.note, auth_context)
    return build_note_id(like.note, request)


def build_like_activity_json_ld(activity, auth_context=None):
    # Build Like Activity JSON-LD with dynamic URL generation
    request = auth_context.get('request') if auth_context else None
    
    base = {
        "@context": build_basic_context(breadcrumbs=bool(activity.previously)),
        "type": "Like",
        "id": build_activity_id("like", activity, request),
        "actor": build_actor_id(activity.actor.id, request),
        "published": activity.timestamp.isoformat(),
        "visibility": activity.visibility,
        **_non_empty(activity, {"previously": "previously"}),
    }
    base["object"] = build_like_object_json_ld(activity, auth_context)

    return base


def build_follow_activity_json_ld(activity, auth_context=None):
    # Build Follow Activity JSON-LD with dynamic URL generation
    request = auth_context.get('request') if auth_context else None
    
    base = {
        "@context": build_basic_context(breadcrumbs=bool(activity.previously)),
        "type": "Follow",
        "id": build_activity_id("follow", activity, request),
        "actor": build_actor_id(activity.actor.id, request),
        "published": activity.timestamp.isoformat(),
        "visibility": activity.visibility,
        **_non_empty(activity, {"previously": "previously"}),
    }

    if activity.target_actor:
        base["object"] = build_actor_json_ld(activity.target_actor, auth_context)
    else:
        base["object"] = {
            "@context": build_basic_context(),
            **activity.target_actor_data,
            "id": activity.target_actor_url
        }

    return base


def build_outbox_json_ld(outbox, auth_context=None):
    """
    Build outbox JSON-LD with authentication-based content filtering.
    
    Args:
        outbox: The PortabilityOutbox model instance
        auth_context: Optional authentication context dict with keys:
            - is_authenticated: boolean
            - has_portability_scope: boolean  
            - request: HTTP request object
    
    Returns:
        Dict containing ActivityPub OrderedCollection with filtered activities
    """
    create_activities = list(outbox.activities_create.all())
    like_activities = list(outbox.activities_like.all())
    follow_activities = list(outbox.activities_follow.all())

    all_activities = create_activities + like_activities + follow_activities
    
    # Filter content based on authentication and scope
    if not auth_context or not auth_context.get('has_portability_scope'):
        # Public only for unauthenticated requests or requests without portability scope
        all_activities = [activity for activity in all_activities if activity.visibility == 'public']
    # LOLA authenticated requests with portability scope get ALL activities (public + private)
    
    all_activities.sort(key=lambda activity: (activity.timestamp, activity.pk), reverse=True)

    # Extract request for dynamic URL generation
    request = auth_context.get('request') if auth_context else None
    
    def build_activity_json_ld(activity):
        if isinstance(activity, CreateActivity):
            return build_create_activity_json_ld(activity, auth_context)
        elif isinstance(activity, LikeActivity):
            return build_like_activity_json_ld(activity, auth_context)
        elif isinstance(activity, FollowActivity):
            return build_follow_activity_json_ld(activity, auth_context)

    items = [build_activity_json_ld(activity) for activity in all_activities]
    return build_collection_json_ld(build_outbox_id(outbox.actor.id, request), items)


def build_collection_json_ld(collection_id, items):
    """
    The one envelope every LOLA collection is served in, the outbox included.

    Args:
        collection_id: The full URL/ID for the collection
        items: The collection's items, already in its documented order

    Returns:
        Dict containing ActivityPub OrderedCollection
    """
    return {
        "@context": build_basic_context(),
        "type": "OrderedCollection",
        "id": collection_id,
        "totalItems": len(items),
        "orderedItems": items,
    }


def build_relationship_items(relationships, local_actor_field, remote_url_field, remote_data_field, auth_context):
    """
    Build collection items from Following or Followers relationship querysets.
    
    Handles both local and remote actors consistently across relationship types.
    
    Args:
        relationships: QuerySet of Following or Followers objects
        local_actor_field: Field name for local actor (e.g., 'target_actor', 'follower_actor')
        remote_url_field: Field name for remote URL (e.g., 'target_actor_url', 'follower_actor_url')  
        remote_data_field: Field name for remote data (e.g., 'target_actor_data', 'follower_actor_data')
        auth_context: Authentication context for JSON-LD building
    
    Returns:
        List of actor JSON-LD objects ready for collection
    """
    items = []
    for relationship in relationships:
        # Try to get local actor using dynamic field access
        local_actor = getattr(relationship, local_actor_field, None)
        
        if local_actor:
            # Local actor: use full JSON-LD builder with authentication context
            items.append(build_actor_json_ld(local_actor, auth_context))
        else:
            # Remote actor: use cached data with URL injection
            remote_url = getattr(relationship, remote_url_field, None)
            remote_data = getattr(relationship, remote_data_field, None)
            
            actor_data = remote_data.copy() if remote_data else {}
            actor_data['id'] = remote_url
            items.append(actor_data)
    
    return items
