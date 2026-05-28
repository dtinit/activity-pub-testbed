"""
Custom django-oauth-toolkit (DOT) authorization view for LOLA portability.

`PortabilityAuthorizationView` subclasses DOT's `AuthorizationView` to satisfy
LOLA §5.3, which requires the source server's approval redirect to carry three
parameters:

    code, state, activitypub_actor

DOT already produces `code` and `state` as part of the standard OAuth 2.0
authorization-code flow. This subclass appends `activitypub_actor` (the
absolute URL of the source Actor that just granted portability access)
"""

import logging
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

from oauth2_provider.views import AuthorizationView

from ..json_ld_utils import build_absolute_actor_url

logger = logging.getLogger(__name__)


LOLA_PORTABILITY_SCOPE = "activitypub_account_portability"
ACTIVITYPUB_ACTOR_PARAM = "activitypub_actor" # Query parameter name defined by LOLA §5.3 for the granted source Actor URL.


class PortabilityAuthorizationView(AuthorizationView):
    """
    Appends `activitypub_actor` to the approval redirect for portability-scoped
    authorizations, and binds the request to the resolved source actor so the
    redirect actor and the token-bound actor share a single source of truth.
    """

    def form_valid(self, form):
        """
        Handle the POST approval path.

        Resolve the source actor and stamp `request.activitypub_bound_actor_id`
        BEFORE delegating to DOT so the binding attribute is present when DOT
        creates the grant/token. DOT returns an OAuth2ResponseRedirect; we then
        append `activitypub_actor` to its Location header.
        """
        scopes = form.cleaned_data.get("scope") or ""
        actor = self._prepare_actor_binding(scopes)

        response = super().form_valid(form)

        if actor is not None:
            self._append_actor_to_redirect(response, actor)
        return response

    def get(self, request, *args, **kwargs):
        scopes = request.GET.get("scope", "")
        actor = self._prepare_actor_binding(scopes)

        response = super().get(request, *args, **kwargs)

        if actor is not None and self._is_redirect(response):
            self._append_actor_to_redirect(response, actor)
        return response

    def _prepare_actor_binding(self, scope_string):
        """
        Resolve the source actor for a portability authorization and record it
        on the request so the token validator binds to the same actor.
        """
        if LOLA_PORTABILITY_SCOPE not in scope_string.split():
            return None

        actor = self._resolve_source_actor()
        if actor is None:
            logger.warning(
                "LOLA authorization: no resolvable source actor for user_id=%s; "
                "activitypub_actor will be omitted from redirect",
                getattr(getattr(self.request, "user", None), "pk", None),
            )
            return None

        # Single source of truth: this is the same attribute
        # ActivityPubOAuth2Validator._save_bearer_token reads when it creates
        # the TokenActorBinding, so the redirect actor and the bound actor match.
        self.request.activitypub_bound_actor_id = actor.pk
        logger.info(
            "LOLA authorization: bound actor resolved actor_id=%s user_id=%s",
            actor.pk,
            getattr(getattr(self.request, "user", None), "pk", None),
        )
        return actor

    def _resolve_source_actor(self):
        # Resolve the approving user's source Actor.
        from ..models import Actor

        user = getattr(self.request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None

        try:
            return Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
        except Actor.DoesNotExist:
            return None

    def _append_actor_to_redirect(self, response, actor):
        """
        Append `activitypub_actor=<absolute Actor URL>` to a successful
        approval redirect's Location header, preserving everything DOT already
        put there.
        """
        location = response.get("Location")
        if not location:
            return

        query = parse_qs(urlparse(location).query)
        if "code" not in query:
            return

        actor_url = build_absolute_actor_url(actor.pk, self.request)
        response["Location"] = self._add_query_param(
            location, ACTIVITYPUB_ACTOR_PARAM, actor_url
        )
        logger.info(
            "LOLA authorization: appended %s to redirect actor_id=%s",
            ACTIVITYPUB_ACTOR_PARAM,
            actor.pk,
        )

    @staticmethod
    def _add_query_param(url, key, value):
        parsed = urlparse(url)
        query = parse_qsl(parsed.query, keep_blank_values=True)
        query.append((key, value))
        new_query = urlencode(query)
        return urlunparse(parsed._replace(query=new_query))

    @staticmethod
    def _is_redirect(response):
        # True when the response is an HTTP redirect carrying a Location header
        return 300 <= getattr(response, "status_code", 0) < 400 and response.has_header(
            "Location"
        )
