from .json_ld_utils import (build_basic_context,
                            build_actor_context,
                            build_actor_id,
                            build_activity_id,
                            build_note_id,
                            build_outbox_id)
from .models import CreateActivity, LikeActivity, FollowActivity

def build_actor_json_ld(actor):
    return {
        "@context": build_actor_context(),
        "type": "Person",
        "id": build_actor_id(actor.id),
        "preferredUsername": actor.username,
        "name": actor.username,
        "previously": actor.previously or [], # Ensure it's always a list
    }

def build_note_json_ld(note):
    return {
        "@context": build_basic_context(),
        "type": "Note",
        "id": build_note_id(note.id),
        "actor": build_actor_id(note.actor.id),
        "content": note.content,
        "published": note.published.isoformat(),
        "visibility": note.visibility,
    }


def build_create_activity_json_ld(activity):
    json_ld = {
        "@context": build_basic_context(),
        "type": "Create",
        "id": build_activity_id(activity.id),
        "actor": build_actor_id(activity.actor.id),
        "published": activity.timestamp.isoformat(),
        "visibility": activity.visibility,
    }

    if activity.note:
        json_ld["object"] = build_note_json_ld(activity.note)
    else:
        json_ld["object"] = build_actor_json_ld(activity.actor)

    return json_ld


def build_like_activity_json_ld(activity):
    base = {
        "@context": build_basic_context(),
        "type": "Like",
        "id": build_activity_id(activity.id),
        "actor": build_actor_id(activity.actor.id),
        "published": activity.timestamp.isoformat(),
        "visibility": activity.visibility,
    }

    if activity.note:
        # For local notes, use the Note model's get_json_ld method
        base["object"] = build_note_json_ld(activity.note)
    else:
        # For remote objects, use the stored data
        base["object"] = {
            "@context": build_basic_context(),
            **activity.object_data,
            "id": activity.object_url,
        }

    return base


def build_follow_activity_json_ld(activity):
    base = {
        "@context": build_basic_context(),
        "type": "Follow",
        "id": build_activity_id(activity.id),
        "actor": build_actor_id(activity.actor.id),
        "published": activity.timestamp.isoformat(),
        "visibility": activity.visibility,
    }

    if activity.target_actor:
        base["object"] = build_actor_json_ld(activity.target_actor)
    else:
        base["object"] = {
            "@context": build_basic_context(),
            **activity.target_actor_data,
            "id": activity.target_actor_url
        }

    return base


def build_outbox_json_ld(outbox):
    create_activities = list(outbox.activities_create.all())
    like_activities = list(outbox.activities_like.all())
    follow_activities = list(outbox.activities_follow.all())

    all_activities = create_activities + like_activities + follow_activities
    all_activities.sort(key=lambda x: x.timestamp, reverse=True)

    def build_activity_json_ld(activity):
        if isinstance(activity, CreateActivity):
            return build_create_activity_json_ld(activity)
        elif isinstance(activity, LikeActivity):
            return build_like_activity_json_ld(activity)
        elif isinstance(activity, FollowActivity):
            return build_follow_activity_json_ld(activity)

    return {
        "@context": build_basic_context(),
        "type": "OrderedCollection",
        "id": build_outbox_id(outbox.actor.id),
        "totalItems": len(all_activities),
        "items": [build_activity_json_ld(activity) for activity in all_activities],
    }