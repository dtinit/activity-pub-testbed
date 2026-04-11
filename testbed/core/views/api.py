"""
LOLA API views

Contains:
- actor_detail: ActivityPub Actor with conditional LOLA migration.* properties
- portability_outbox_detail: Outbox with LOLA content filtering
- following_collection: public Following OrderedCollection
- followers_collection: LOLA-gated Followers OrderedCollection
- content_collection: LOLA-gated raw Notes (no Activity wrappers)
- liked_collection: LOLA-gated liked objects with migration metadata
- blocked_collection: LOLA-gated block list (FEP-c648)
- oauth_authorization_server_metadata: RFC8414 discovery endpoint

All LOLA-gated endpoints call validate_lola_access() from decorators.py.
All endpoints use build_auth_context() to produce a consistent dict for JSON-LD builders.
"""

import logging

from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from ..json_ld_builders import (
    build_actor_json_ld,
    build_collection_json_ld,
    build_note_json_ld,
    build_outbox_json_ld,
    build_relationship_items,
)
from ..json_ld_utils import build_actor_id, build_note_id
from ..models import (
    Actor,
    Blocked,
    Followers,
    Following,
    LikeActivity,
    Note,
    PortabilityOutbox,
)
from ..utils.authentication import OptionalOAuth2Authentication
from ..utils.errors import build_actor_not_found_error
from .decorators import activitypub_content, build_auth_context, validate_lola_access

logger = logging.getLogger(__name__)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
def actor_detail(request, pk):
    """
    Returns basic ActivityPub data for unauthenticated requests,
    and enhanced LOLA data for authenticated requests with portability scope.
    """
    try:
        actor = Actor.objects.get(pk=pk)
    except Actor.DoesNotExist:
        return build_actor_not_found_error(pk, request)

    # Build standardized authentication context
    auth_context = build_auth_context(request)

    # Build response with authentication context
    data = build_actor_json_ld(actor, auth_context)
    return Response(data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
def portability_outbox_detail(request, pk):
    """
    Returns public activities for unauthenticated requests,
    and all activities for authenticated requests with portability scope.
    """
    try:
        outbox = PortabilityOutbox.objects.get(actor_id=pk)
    except PortabilityOutbox.DoesNotExist:
        return build_actor_not_found_error(pk, request)

    # Build standardized authentication context
    auth_context = build_auth_context(request)

    # Build response with authentication-based content filtering
    data = build_outbox_json_ld(outbox, auth_context)
    return Response(data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
def following_collection(request, pk):
    """
    Returns who an actor is currently following in ActivityPub OrderedCollection format.
    Per LOLA spec: "The Following collection as per https://www.w3.org/TR/activitypub/#following
    SHOULD be provided on the Actor object when accessed with the account migration authorization token."

    Note: While the collection URL only appears in LOLA-authenticated Actor objects,
    the collection itself follows standard ActivityPub public access patterns.
    """
    try:
        actor = Actor.objects.get(pk=pk)
    except Actor.DoesNotExist:
        return build_actor_not_found_error(pk, request)

    # Get all active following relationships for this actor
    following_qs = Following.objects.filter(
        actor=actor, status=Following.STATUS_ACTIVE
    ).order_by("-created_at")

    # Build standardized authentication context for nested Actor objects
    auth_context = build_auth_context(request)

    # Build the collection items
    items = build_relationship_items(
        relationships=following_qs,
        local_actor_field="target_actor",
        remote_url_field="target_actor_url",
        remote_data_field="target_actor_data",
        auth_context=auth_context,
    )

    # Build ActivityPub OrderedCollection
    collection_id = f"{request.scheme}://{request.get_host()}/api/actors/{pk}/following"
    collection_data = build_collection_json_ld(collection_id, items)

    return Response(collection_data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
def followers_collection(request, pk):
    """
    Returns who is currently following an actor in ActivityPub OrderedCollection format.
    This is privacy-sensitive data that requires LOLA scope authentication.
    Per LOLA implementation: Followers collection requires account migration authorization token.
    """
    try:
        actor = Actor.objects.get(pk=pk)
    except Actor.DoesNotExist:
        return build_actor_not_found_error(pk, request)

    # Apply centralized LOLA validation
    validation_result = validate_lola_access(request, required_scope=True)
    if not validation_result["valid"]:
        return validation_result["error_response"]

    # Get all active follower relationships for this actor
    followers_qs = Followers.objects.filter(
        actor=actor, status=Followers.STATUS_ACTIVE
    ).order_by("-created_at")

    # Build standardized authentication context for nested Actor objects
    auth_context = build_auth_context(request)

    # Build the collection items
    items = build_relationship_items(
        relationships=followers_qs,
        local_actor_field="follower_actor",
        remote_url_field="follower_actor_url",
        remote_data_field="follower_actor_data",
        auth_context=auth_context,
    )

    # Build ActivityPub OrderedCollection
    collection_id = f"{request.scheme}://{request.get_host()}/api/actors/{pk}/followers"
    collection_data = build_collection_json_ld(collection_id, items)

    return Response(collection_data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
def content_collection(request, pk):
    """
    Returns raw authored objects (Notes) without Activity wrappers per LOLA specification.
    Applies visibility gating: unauthenticated requests receive public-only content; LOLA-authenticated
    requests receive all content including non-public objects.

    Spec: "MUST provide raw authored objects (no wrapper Activities) for fidelity."

    Auth: Requires activitypub_account_portability scope.
    """
    try:
        actor = Actor.objects.get(pk=pk)
    except Actor.DoesNotExist:
        return build_actor_not_found_error(pk, request)

    # Apply centralized LOLA validation
    validation_result = validate_lola_access(request, required_scope=True)
    if not validation_result["valid"]:
        return validation_result["error_response"]

    # Apply content filtering based on authentication and scope
    notes_qs = Note.objects.filter(actor=actor).order_by("-published")

    # Filter content based on authentication - public only for non-LOLA requests
    if not getattr(request, "has_portability_scope", False):
        notes_qs = notes_qs.filter(visibility="public")
    # LOLA authenticated requests with portability scope get ALL content (public + private)

    # Build standardized authentication context for JSON-LD building
    auth_context = build_auth_context(request)

    # Build raw Note objects (no Activity wrappers)
    items = [build_note_json_ld(note, auth_context) for note in notes_qs]

    # Build ActivityPub OrderedCollection
    collection_id = f"{request.scheme}://{request.get_host()}/api/actors/{pk}/content"
    collection_data = build_collection_json_ld(collection_id, items)

    return Response(collection_data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
def liked_collection(request, pk):
    """
    Returns objects that an actor has liked with migration-ready metadata per LOLA specification.
    Applies field projection to minimize payload size while retaining sufficient migration context.

    This endpoint requires LOLA scope authentication and applies field projection
    to minimize payload size while providing sufficient metadata for migration.
    """
    try:
        actor = Actor.objects.get(pk=pk)
    except Actor.DoesNotExist:
        return build_actor_not_found_error(pk, request)

    # Apply centralized LOLA validation
    validation_result = validate_lola_access(request, required_scope=True)
    if not validation_result["valid"]:
        return validation_result["error_response"]

    # Get all LikeActivity objects for this actor in reverse chronological order
    likes_qs = LikeActivity.objects.filter(actor=actor).order_by("-timestamp")

    # Apply visibility filtering - only include likes of public objects for privacy
    # TODO: This could be enhanced with trust controls
    likes_qs = likes_qs.filter(visibility="public")

    # Build standardized authentication context for JSON-LD building
    auth_context = build_auth_context(request)

    # Build liked objects with required metadata fields
    items = []
    for like in likes_qs:
        # Build the liked object with field projection for performance
        if like.note:
            # Local Note object - extract required metadata
            liked_object = {
                "id": build_note_id(like.note.id, auth_context.get("request")),
                "type": "Note",
                "attributedTo": build_actor_id(
                    like.note.actor.id, auth_context.get("request")
                ),
                "published": like.note.published.isoformat(),
                "summary": getattr(like.note, "summary", ""),
                "content": like.note.content[:280]
                if len(like.note.content) > 280
                else like.note.content,  # Small content only
                "inReplyTo": None,  # TODO: Add reply chain support when implemented
                "audience": {"public": like.note.visibility == "public"},
                "attachment": [],  # TODO: Add when attachment support is implemented
                "canonicalUrl": build_note_id(
                    like.note.id, auth_context.get("request")
                ),
                # Optional objectHash for integrity verification
                "objectHash": None,  # TODO: Implement content hashing if needed
            }
        else:
            # Remote object - use cached object_data with field projection
            remote_data = like.object_data or {}
            liked_object = {
                "id": like.object_url,
                "type": remote_data.get("type", "Object"),
                "attributedTo": remote_data.get("attributedTo", ""),
                "published": remote_data.get("published", like.timestamp.isoformat()),
                "summary": remote_data.get("summary", ""),
                "content": remote_data.get("content", "")[:280]
                if remote_data.get("content")
                else "",  # Small content only
                "inReplyTo": remote_data.get("inReplyTo"),
                "audience": {
                    "public": True
                },  # Assume remote objects in likes are public
                "attachment": remote_data.get("attachment", [])[:3]
                if remote_data.get("attachment")
                else [],  # Limit attachments
                "canonicalUrl": like.object_url,
                "objectHash": remote_data.get("objectHash"),
            }

        items.append(liked_object)

    # Build ActivityPub OrderedCollection
    collection_id = f"{request.scheme}://{request.get_host()}/api/actors/{pk}/liked"
    collection_data = build_collection_json_ld(collection_id, items)

    return Response(collection_data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
def blocked_collection(request, pk):
    """
    LOLA Blocked collection endpoint.

    Returns actors that have been blocked by an actor in ActivityPub OrderedCollection format.
    Per LOLA spec: "If the source server does blocking, the personal block list SHOULD be fetchable at the
    URL advertised on the Actor object, as per https://codeberg.org/fediverse/fep/src/branch/main/fep/c648/fep-c648.md"

    This is highly privacy-sensitive data that requires LOLA scope authentication.
    Block lists are critical user safety data that must never be exposed without proper authorization.

    Security Note: This endpoint implements the strongest privacy protection in the entire LOLA specification,
    as block lists reveal who users consider threats, harassers, or sources of harm.
    Unauthorized access could compromise user safety.
    """
    try:
        actor = Actor.objects.get(pk=pk)
    except Actor.DoesNotExist:
        return build_actor_not_found_error(pk, request)

    # Apply centralized LOLA validation - MANDATORY for blocked collection
    validation_result = validate_lola_access(request, required_scope=True)
    if not validation_result["valid"]:
        return validation_result["error_response"]

    # Get all active blocking relationships for this actor
    blocked_qs = Blocked.objects.filter(
        actor=actor, status=Blocked.STATUS_ACTIVE
    ).order_by("-created_at")

    # Build standardized authentication context for nested Actor objects
    auth_context = build_auth_context(request)

    # Build the collection items using the same pattern as followers/following
    items = build_relationship_items(
        relationships=blocked_qs,
        local_actor_field="blocked_actor",
        remote_url_field="blocked_actor_url",
        remote_data_field="blocked_actor_data",
        auth_context=auth_context,
    )

    # Build ActivityPub OrderedCollection in FEP-c648 format
    collection_id = f"{request.scheme}://{request.get_host()}/api/actors/{pk}/blocked"
    collection_data = build_collection_json_ld(collection_id, items)

    logger.info(f"Blocked collection accessed: actor_id={pk}, items_count={len(items)}")

    return Response(collection_data)


def oauth_authorization_server_metadata(request):
    """
    RFC8414-compliant OAuth Authorization Server Metadata endpoint for LOLA discovery.

    This endpoint enables automatic LOLA discovery by destination servers.

    Per LOLA specification: "ActivityPub servers supporting this specification SHOULD
    include the URL of their portability authorization endpoint in their authorization
    server metadata document [RFC8414] using the activitypub_account_portability parameter."
    """
    if hasattr(settings, "BASE_URL") and settings.BASE_URL:
        base_url = settings.BASE_URL
    else:
        scheme = request.scheme
        host = request.get_host()
        base_url = f"{scheme}://{host}"

    authorization_endpoint = f"{base_url}{reverse('oauth2_provider:authorize')}"

    metadata = {
        "issuer": base_url,
        "authorization_endpoint": authorization_endpoint,
        "token_endpoint": f"{base_url}{reverse('oauth2_provider:token')}",
        "scopes_supported": ["activitypub_account_portability"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        # LOLA-specific parameter for account portability endpoint discovery
        "activitypub_account_portability": {
            "supported": True,
            "authorization_endpoint": authorization_endpoint,
            "scopes": ["activitypub_account_portability"],
        },
    }

    response = JsonResponse(metadata)
    response["Content-Type"] = "application/json"
    response["Access-Control-Allow-Origin"] = "*"  # CORS for federation
    return response
