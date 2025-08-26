from .json_ld_utils import (build_basic_context,
                            build_actor_context,
                            build_actor_id,
                            build_activity_id,
                            build_note_id,
                            build_outbox_id)
from .utils.oauth_utils import build_oauth_endpoint_url
from .models import CreateActivity, LikeActivity, FollowActivity

def build_actor_json_ld(actor, auth_context=None):
    """
    Build JSON-LD Actor with optional LOLA enhancements.
    
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
    
    # Base ActivityPub Actor (always included) - now with dynamic URLs
    actor_id = build_actor_id(actor.id, request)
    actor_data = {
        "@context": build_actor_context(),
        "type": "Person",
        "id": actor_id,
        "preferredUsername": actor.username,
        "name": actor.username,
        # Standard ActivityPub collections
        "inbox": f"{actor_id}/inbox",
        "outbox": f"{actor_id}/outbox",
        "previously": actor.previously or [], # Ensure it's always a list
    }
    
    # Add LOLA fields ONLY when authenticated with portability scope
    if auth_context and auth_context.get('has_portability_scope'):
        # Required LOLA discovery field
        actor_data["accountPortabilityOauth"] = build_oauth_endpoint_url(request)
        
        # LOLA social collections (privacy-sensitive relationship data)
        actor_data["followers"] = f"{actor_id}/followers"
        actor_data["following"] = f"{actor_id}/following"
        
        # Additional LOLA discovery fields
        actor_data["content"] = f"{actor_id}/content"
        actor_data["blocked"] = f"{actor_id}/blocked"
        actor_data["migration"] = f"{actor_id}/outbox"
    
    return actor_data

def build_note_json_ld(note, auth_context=None):
    """Build Note JSON-LD with dynamic URL generation"""
    request = auth_context.get('request') if auth_context else None
    
    return {
        "@context": build_basic_context(),
        "type": "Note",
        "id": build_note_id(note.id, request),
        "actor": build_actor_id(note.actor.id, request),
        "content": note.content,
        "published": note.published.isoformat(),
        "visibility": note.visibility,
    }


def build_create_activity_json_ld(activity, auth_context=None):
    # Build Create Activity JSON-LD with dynamic URL generation
    request = auth_context.get('request') if auth_context else None
    
    json_ld = {
        "@context": build_basic_context(),
        "type": "Create",
        "id": build_activity_id(activity.id, request),
        "actor": build_actor_id(activity.actor.id, request),
        "published": activity.timestamp.isoformat(),
        "visibility": activity.visibility,
    }

    if activity.note:
        json_ld["object"] = build_note_json_ld(activity.note, auth_context)
    else:
        json_ld["object"] = build_actor_json_ld(activity.actor, auth_context)

    return json_ld


def build_like_activity_json_ld(activity, auth_context=None):
    # Build Like Activity JSON-LD with dynamic URL generation
    request = auth_context.get('request') if auth_context else None
    
    base = {
        "@context": build_basic_context(),
        "type": "Like",
        "id": build_activity_id(activity.id, request),
        "actor": build_actor_id(activity.actor.id, request),
        "published": activity.timestamp.isoformat(),
        "visibility": activity.visibility,
    }

    if activity.note:
        # For local notes, use the Note model's get_json_ld method
        base["object"] = build_note_json_ld(activity.note, auth_context)
    else:
        # For remote objects, use the stored data
        base["object"] = {
            "@context": build_basic_context(),
            **activity.object_data,
            "id": activity.object_url,
        }

    return base


def build_follow_activity_json_ld(activity, auth_context=None):
    # Build Follow Activity JSON-LD with dynamic URL generation
    request = auth_context.get('request') if auth_context else None
    
    base = {
        "@context": build_basic_context(),
        "type": "Follow",
        "id": build_activity_id(activity.id, request),
        "actor": build_actor_id(activity.actor.id, request),
        "published": activity.timestamp.isoformat(),
        "visibility": activity.visibility,
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
    
    all_activities.sort(key=lambda x: x.timestamp, reverse=True)

    # Extract request for dynamic URL generation
    request = auth_context.get('request') if auth_context else None
    
    def build_activity_json_ld(activity):
        if isinstance(activity, CreateActivity):
            return build_create_activity_json_ld(activity, auth_context)
        elif isinstance(activity, LikeActivity):
            return build_like_activity_json_ld(activity, auth_context)
        elif isinstance(activity, FollowActivity):
            return build_follow_activity_json_ld(activity, auth_context)

    return {
        "@context": build_basic_context(),
        "type": "OrderedCollection",
        "id": build_outbox_id(outbox.actor.id, request),
        "totalItems": len(all_activities),
        "items": [build_activity_json_ld(activity) for activity in all_activities],
    }
