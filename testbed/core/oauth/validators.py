import logging

from oauthlib.oauth2.rfc6749.errors import InvalidRequestFatalError
from oauth2_provider.models import get_access_token_model
from oauth2_provider.oauth2_validators import OAuth2Validator

logger = logging.getLogger(__name__)


# Custom validator for ActivityPub-specific OAuth requirements
class ActivityPubOAuth2Validator(OAuth2Validator):
    # The OAuth scope that marks a token as a LOLA portability token.
    LOLA_PORTABILITY_SCOPE = 'activitypub_account_portability'

    # Ensure the client is requesting valid scopes for ActivityPub portability
    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        if not scopes:
            logger.warning("Client %s requested OAuth with no scopes", client_id)
            return False

        # For account portability, it requires the 'activitypub_account_portability' scope
        if self.LOLA_PORTABILITY_SCOPE not in scopes:
            logger.warning(
                "Client %s requested OAuth without %r scope. Scopes: %s",
                client_id,
                self.LOLA_PORTABILITY_SCOPE,
                scopes,
            )
            return False

        logger.info("Client %s requested valid scopes: %s", client_id, scopes)
        return super().validate_scopes(client_id, scopes, client, request, *args, **kwargs)

    # Additional validation for redirect URIs in ActivityPub context
    def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):

        # Standard validation first
        valid = super().validate_redirect_uri(client_id, redirect_uri, request, *args, **kwargs)

        if not valid:
            logger.warning("Client %s requested invalid redirect URI: %s", client_id, redirect_uri)
            return False

        # We could add additional validation here if needed later on
        # For example, checking for HTTPS in production

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

        For non-portability scopes we skip binding entirely so normal
        ActivityPub federation tokens keep working unchanged.

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

        scope_string = token.get("scope") or ""
        if self.LOLA_PORTABILITY_SCOPE not in scope_string.split():
            # Non-LOLA scopes don't get a binding: regular ActivityPub tokens
            # are not actor-keyed. Explicit early-return keeps behavior clear.
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

        Preference order:
          1. `request.activitypub_bound_actor_id` — the actor id the user
             explicitly selected at the authorization step. Populated by
             following PR's authorization view; absent today. Re-validated here
             against (user, role=ROLE_SOURCE) so a client-supplied id cannot
             bind to another user's actor.
          2. Fallback: the authenticated user's unique source Actor.
             `Actor.clean()` enforces one source actor per user, so this
             lookup is deterministic when an actor exists.

        Returns None when no valid source actor can be resolved; the caller
        treats that as a hard failure (refuse to issue the token).
        """
        # Import lazily — this module is imported by DOT at app startup before
        # the core app's models are fully available in some test configs.
        from testbed.core.models import Actor

        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None

        bound_id = getattr(request, "activitypub_bound_actor_id", None)
        try:
            if bound_id is not None:
                return Actor.objects.get(
                    pk=bound_id,
                    user=user,
                    role=Actor.ROLE_SOURCE,
                )
            return Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
        except Actor.DoesNotExist:
            return None
