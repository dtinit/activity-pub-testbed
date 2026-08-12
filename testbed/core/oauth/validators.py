import logging
from urllib.parse import urlparse

from oauthlib.oauth2.rfc6749.errors import InvalidRequestFatalError
from oauth2_provider.models import get_access_token_model
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.settings import oauth2_settings

from .scopes import LOLA_PORTABILITY_SCOPE, scope_grants_portability

logger = logging.getLogger(__name__)


# Custom validator for ActivityPub-specific OAuth requirements
class ActivityPubOAuth2Validator(OAuth2Validator):

    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        """
        Gate every OAuth grant on the LOLA portability scope.

        LOLA §5: "The advertised OAuth endpoint MUST support the `activitypub_account_portability` scope."
        This method is where that support is enforced, and it is the decision that makes a token a
        portability token -- which in turn is what makes `_save_bearer_token` bind it to a single Actor
        (the Section 5 one-account MUST) and what makes the request-time gate in views/decorators.py engage.
        
        Fail-closed: both local checks run BEFORE delegating to django-oauth-toolkit,
        so a request that misses the portability scope is rejected. `super()` then
        applies DOT's requested scopes must be a subset of available scopes check.

        Args:
            client_id: OAuth client identifier.
            scopes: requested scopes. oauthlib passes a list here today, but
                `scope_grants_portability` accepts a space-delimited string too so the check cannot
                silently degrade to a substring match if that ever changes. See oauth/scopes.py.
            client: the DOT Application the request is for.
            request: the oauthlib Request object.

        Returns:
            bool: True only when the portability scope is present AND DOT's own
            scope validation passes.
        """
        if not scopes:
            logger.warning("Client %s requested OAuth with no scopes", client_id)
            return False

        if not scope_grants_portability(scopes):
            logger.warning(
                "Client %s requested OAuth without %r scope. Scopes: %s",
                client_id,
                LOLA_PORTABILITY_SCOPE,
                scopes,
            )
            return False

        logger.info("Client %s requested valid scopes: %s", client_id, scopes)
        return super().validate_scopes(client_id, scopes, client, request, *args, **kwargs)

    def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):
        """
        Approve a redirect URI only if it is BOTH registered AND uses an allowed scheme.

        Two gates, both fail-closed:

        1. Registration: `super()` matches the URI against the Application's
           `redirect_uris` allow-list (django-oauth-toolkit's own check).
        2. Scheme -- the URI's scheme must appear in
           OAUTH2_PROVIDER["ALLOWED_REDIRECT_URI_SCHEMES"].

        Gate 2 exists because DOT's enforces it in `Application.clean()`, which only
        runs under `full_clean()`, and Django's `Model.save()` never calls it.

        Args:
            client_id: OAuth client identifier
            redirect_uri: the callback URI the client asked us to redirect to
            request: the oauthlib Request object

        Returns:
            bool: True only when both gates pass. Returning False makes oauthlib
            raise `MismatchingRedirectURIError`, a FatalClientError, and DOT
            answers 400 by re-rendering `oauth2_provider/authorize.html` with the
            error in context.
        """
        # Gate 1: is it registered?
        valid = super().validate_redirect_uri(client_id, redirect_uri, request, *args, **kwargs)

        if not valid:
            logger.warning("Client %s requested invalid redirect URI: %s", client_id, redirect_uri)
            return False

        # Gate 2: is the scheme allowed in this environment?
        # lowercases the scheme, the allowed list is lowercased to match, as DOT's own validator does.
        allowed_schemes = [scheme.lower() for scheme in oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES]
        scheme = urlparse(redirect_uri).scheme

        if scheme not in allowed_schemes:
            logger.warning(
                "Client %s requested redirect URI with disallowed scheme %r "
                "(allowed: %s): %s",
                client_id,
                scheme,
                allowed_schemes,
                redirect_uri,
            )
            return False

        logger.info("Client %s requested valid redirect URI: %s", client_id, redirect_uri)

        return True

    def _save_bearer_token(self, token, request, *args, **kwargs):
        """
        Persist a TokenActorBinding alongside LOLA-scoped access tokens.

        DOT (django-oauth-toolkit) recommends overriding `_save_bearer_token` (not `save_bearer_token`)
        for custom token-storage logic so the write rides the same
        `transaction.atomic()` block DOT already opens. This is important for
        security: if binding resolution or creation fails, the whole transaction
        rolls back and no portability token is issued — i.e., we fail closed
        at issuance rather than leaving an unbound LOLA token in the database.

        Binding is skipped for any token without the portability scope.

        Args:
            token: OAuthLib token dict. `token["access_token"]` is the
                   final access-token string DOT has written to the DB row by
                   the time super() returns.
            request: OAuthLib Request object. `request.user` is the
                     authenticated Django User for authorization-code grants.
        """
        # Let DOT persist the AccessToken first. Any FatalClientError raised by
        # super() will propagate out of the atomic block and prevent any write.
        super()._save_bearer_token(token, request, *args, **kwargs)

        if not scope_grants_portability(token.get("scope")):
            # validate_scopes() rejects every grant that lacks the portability scope,
            # so no non-portability token can be issued.
            return

        # Resolve the Actor to bind BEFORE looking up the access token row, so a
        # resolution failure rolls back the AccessToken DOT just inserted.
        actor = self._resolve_bound_actor(request)
        if actor is None:
            # Fail closed: refuse to issue an unbound portability token.
            # Raising an oauthlib fatal error aborts the token response and
            # rolls back the enclosing transaction.atomic() block.
            logger.warning(
                "LOLA token issuance rejected: no resolvable source actor for user_id=%s",
                getattr(getattr(request, "user", None), "pk", None),
            )
            raise InvalidRequestFatalError(description="actor_binding_unavailable")

        # Import the binding model lazily so this module stays importable
        # before Django app registry is ready (DOT loads validators early).
        from testbed.core.models import TokenActorBinding

        access_token_model = get_access_token_model()
        access_token = access_token_model.objects.get(token=token["access_token"])

        # get_or_create defends the refresh-token-reuse path (where DOT may
        # update an existing AccessToken in place and an old binding already
        # exists). Under DOT's default ROTATE_REFRESH_TOKEN=True, every refresh
        # creates a brand-new AccessToken and this is effectively a create.
        binding, created = TokenActorBinding.objects.get_or_create(
            token=access_token,
            defaults={"actor": actor},
        )

        if not created and binding.actor_id != actor.pk:
            # Pre-existing binding disagrees with the actor we just resolved —
            # treat as a hard security failure. Roll back via raise; never
            # silently rebind the token to a different actor.
            logger.error(
                "LOLA token binding conflict: existing bound_actor_id=%s does not match resolved actor_id=%s for user_id=%s",
                binding.actor_id,
                actor.pk,
                getattr(getattr(request, "user", None), "pk", None),
            )
            raise InvalidRequestFatalError(description="actor_binding_conflict")

        # Safe log: we record actor id and user id, never the access-token string.
        logger.info(
            "LOLA token bound to actor: actor_id=%s user_id=%s created=%s",
            actor.pk,
            getattr(getattr(request, "user", None), "pk", None),
            created,
        )

    def _resolve_bound_actor(self, request):
        """
        Resolve which source Actor a newly-issued LOLA token should be bound to.

        Returns the authenticated user's unique source Actor, or None if no
        source actor exists (the caller treats None as a hard failure and
        refuses to issue the token). `Actor.clean()` enforces one source actor
        per user, so this lookup is deterministic.
        """
        # Import lazily — this module is imported by DOT at app startup before
        # the core app's models are fully available in some test configs.
        from testbed.core.models import Actor

        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None

        try:
            return Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
        except Actor.DoesNotExist:
            return None
