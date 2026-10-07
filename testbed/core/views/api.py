"""
LOLA API views

Contains:
- actor_detail [dual-mode]: ActivityPub Actor with conditional LOLA migration.* properties
- portability_outbox_detail [dual-mode]: Outbox with LOLA content filtering; at migration/outbox/, the Creates of a Note only
- following_collection [dual-mode]: Following OrderedCollection
- followers_collection [strict]: LOLA-gated Followers OrderedCollection
- content_collection [strict]: LOLA-gated raw Notes (no Activity wrappers)
- liked_collection [strict]: LOLA-gated liked objects with migration metadata
- blocked_collection [strict]: LOLA-gated block list (FEP-c648)
- object_detail [per object]: one Note or activity under its actor, for every object route. Strict or dual-mode
  by the object's own visibility
- oauth_authorization_server_metadata [public]: RFC8414 discovery endpoint (no actor)

Access model (actor-scoped views):
Below the DRF chain (@api_view / @authentication_classes / @activitypub_content),
every actor-scoped view stacks two decorators from decorators.py:

- @actor_required resolves <pk> -> Actor (404 actor_not_found if missing) and injects it as the `actor` argument.
- @lola_scope_required OR @lola_scope_optional is the LOLA gate.
  It runs AFTER @actor_required, so the 404 existence check always precedes the 403 auth check.

The two gate differ only in whether the portability scope is mandatory:
- @lola_scope_required (STRICT) - followers, content, liked, blocked.
  No token -> 403 insufficient_scope; a token bound to a different actor -> 403 actor_mismatch.
- @lola_scope_optional (DUAL-MODE) - actor-detail, outbox, following.
  Public access stays open (no token -> plain public response), but a token bound to a different
  actor -> 403 actor_mismatch, so it is never served this actor's augmented/private data.
  The dedicated .../migration/{outbox,following} routes reuse these same views and inherit the gate.

Each view below therefore assumes `actor` exists and the caller is authorized for it, and documents only
what is endpoint-specific. All views build their payload via json_ld_builders, passing the dict from build_auth_context(request).

Ordering (ActivityPub §5: an OrderedCollection MUST be presented consistently in reverse chronological order):
newest first by each collection's own time field, ties to the higher primary key, so repeated fetches return the same order.
- outbox: activity timestamp, then pk, merged across Create, Like and Follow in build_outbox_json_ld
- content: Note.published, then id
- liked: LikeActivity.timestamp, then id
- following, followers, blocked: created_at, then id
The migration/... routes reuse these views, so they share the same keys.
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
    build_like_object_json_ld,
    build_note_json_ld,
    build_outbox_json_ld,
    build_relationship_items,
)
from ..json_ld_utils import build_url
from ..models import (
    Blocked,
    Followers,
    Following,
    LikeActivity,
    Note,
)
from ..oauth.authentication import OptionalOAuth2Authentication
from ..utils.errors import ActorMismatch, InsufficientScope, ObjectNotFound
from .decorators import (
    actor_required,
    activitypub_content,
    build_auth_context,
    lola_scope_optional,
    lola_scope_required,
    require_lola_access,
)

logger = logging.getLogger(__name__)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
@actor_required
@lola_scope_optional
def actor_detail(request, pk, actor):
    # Build standardized authentication context
    auth_context = build_auth_context(request)

    # Build response with authentication context
    data = build_actor_json_ld(actor, auth_context)
    return Response(data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
@actor_required
@lola_scope_optional
def portability_outbox_detail(request, pk, actor, migration=False):
    """
    The outbox and the migration outbox (LOLA §6.2) when its route passes migration=True.
    One view for both routes; they share one gate and one visibility rule.
    """
    outbox = actor.portability_outbox

    # Build standardized authentication context
    auth_context = build_auth_context(request)

    # Build response with authentication-based content filtering
    data = build_outbox_json_ld(outbox, auth_context, migration=migration)
    return Response(data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
@actor_required
@lola_scope_optional
def following_collection(request, pk, actor):
    """
    Returns who an actor is currently following in ActivityPub OrderedCollection format.
    Per LOLA spec: "The Following collection as per https://www.w3.org/TR/activitypub/#following
    SHOULD be provided on the Actor object when accessed with the account migration authorization token."
    Also serves the advertised .../migration/following/ route.
    """
    # Get all active following relationships for this actor
    following_qs = Following.objects.filter(
        actor=actor, status=Following.STATUS_ACTIVE
    ).order_by("-created_at", "-id")

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
    collection_id = build_url(request, request.resolver_match.url_name, pk=pk)
    collection_data = build_collection_json_ld(collection_id, items)

    return Response(collection_data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
@actor_required
@lola_scope_required
def followers_collection(request, pk, actor):
    # Get all active follower relationships for this actor
    followers_qs = Followers.objects.filter(
        actor=actor, status=Followers.STATUS_ACTIVE
    ).order_by("-created_at", "-id")

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
    collection_id = build_url(request, request.resolver_match.url_name, pk=pk)
    collection_data = build_collection_json_ld(collection_id, items)

    return Response(collection_data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
@actor_required
@lola_scope_required
def content_collection(request, pk, actor):
    """
    The actor's raw authored objects (Notes) without Activity wrappers, for migration fidelity.
    Spec: "MUST provide raw authored objects (no wrapper Activities) for fidelity.
    """
    # Apply content filtering based on authentication and scope
    notes_qs = Note.objects.filter(actor=actor).order_by("-published", "-id")

    # Filter content based on authentication - public only for non-LOLA requests
    if not getattr(request, "has_portability_scope", False):
        notes_qs = notes_qs.filter(visibility="public")
    # LOLA authenticated requests with portability scope get ALL content (public + private)

    # Build standardized authentication context for JSON-LD building
    auth_context = build_auth_context(request)

    # Build raw Note objects (no Activity wrappers)
    items = [build_note_json_ld(note, auth_context) for note in notes_qs]

    # Build ActivityPub OrderedCollection
    collection_id = build_url(request, request.resolver_match.url_name, pk=pk)
    collection_data = build_collection_json_ld(collection_id, items)

    return Response(collection_data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
@actor_required
@lola_scope_required
def liked_collection(request, pk, actor):
    """
    The objects of the actor's Likes (ActivityPub §5.5), each built by build_like_object_json_ld:
    the same object the Like activity carries, so a non-public local Note is served as its id only.
    """
    # Every Like the actor made, whatever its visibility. The strict gate above admits only this actor's bound token
    likes_qs = LikeActivity.objects.filter(actor=actor).order_by("-timestamp", "-id")

    # Build standardized authentication context for JSON-LD building
    auth_context = build_auth_context(request)

    items = [build_like_object_json_ld(like, auth_context) for like in likes_qs]

    # Build ActivityPub OrderedCollection
    collection_id = build_url(request, request.resolver_match.url_name, pk=pk)
    collection_data = build_collection_json_ld(collection_id, items)

    return Response(collection_data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
@actor_required
@lola_scope_required
def blocked_collection(request, pk, actor):
    """
    LOLA Blocked collection endpoint (FEP-c648).

    The actor's block list as an ActivityPub OrderedCollection.
    Per LOLA spec: "If the source server does blocking, the personal block list SHOULD be fetchable at the
    URL advertised on the Actor object, as per https://codeberg.org/fediverse/fep/src/branch/main/fep/c648/fep-c648.md"

    Security Note: This endpoint implements the strongest privacy protection in the entire LOLA specification,
    as block lists reveal who users consider threats, harassers, or sources of harm.
    Unauthorized access could compromise user safety.
    """
    # Get all active blocking relationships for this actor
    blocked_qs = Blocked.objects.filter(
        actor=actor, status=Blocked.STATUS_ACTIVE
    ).order_by("-created_at", "-id")

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
    collection_id = build_url(request, request.resolver_match.url_name, pk=pk)
    collection_data = build_collection_json_ld(collection_id, items)

    logger.info(f"Blocked collection accessed: actor_id={pk}, items_count={len(items)}")

    return Response(collection_data)


@api_view(["GET"])
@authentication_classes([OptionalOAuth2Authentication])
@activitypub_content
@actor_required
def object_detail(request, pk, actor, object_pk, model, build):
    """
    One Note or activity, at the URL its `id` names. Its route passes the `model` and its `build` function.

    A public object is dual-mode: open to anyone, refused to a token bound to another actor (403).
    A non-public object is strict: only a token bound to its owner sees it. Every other caller gets the
    same 404 as a missing object, or one under another actor, so a private object's existence never shows.
    """
    obj = model.objects.filter(pk=object_pk, actor=actor).first()
    if obj is None:
        raise ObjectNotFound

    if obj.visibility == "public":
        # Dual-mode, like the outbox: a token bound to another actor is refused (403)
        require_lola_access(request, required_scope=False, url_pk=pk)
    else:
        # Strict, like the content collection: any refusal becomes the missing-object 404
        try:
            require_lola_access(request, required_scope=True, url_pk=pk)
        except (InsufficientScope, ActorMismatch):
            raise ObjectNotFound from None

    return Response(build(obj, build_auth_context(request)))


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
        "activitypub_account_portability": authorization_endpoint,
    }

    response = JsonResponse(metadata)
    response["Content-Type"] = "application/json"
    response["Access-Control-Allow-Origin"] = "*"  # CORS for federation
    return response
