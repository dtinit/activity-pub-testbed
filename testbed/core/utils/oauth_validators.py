import logging
from oauth2_provider.oauth2_validators import OAuth2Validator

logger = logging.getLogger(__name__)

# Custom validator for ActivityPub-specific OAuth requirements
class ActivityPubOAuth2Validator(OAuth2Validator):
    
    # Ensure the client is requesting valid scopes for ActivityPub portability
    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        if not scopes:
            logger.warning(f"Client {client_id} requested OAuth with no scopes")
            return False
            
        # For account portability, it requires the 'activitypub_account_portability' scope
        if 'activitypub_account_portability' not in scopes:
            logger.warning(
                f"Client {client_id} requested OAuth without 'activitypub_account_portability' scope. "
                f"Scopes: {scopes}"
            )
            return False
            
        logger.info(f"Client {client_id} requested valid scopes: {scopes}")
        return super().validate_scopes(client_id, scopes, client, request, *args, **kwargs)
    
    # Additional validation for redirect URIs in ActivityPub context
    def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):
        
        # Standard validation first
        valid = super().validate_redirect_uri(client_id, redirect_uri, request, *args, **kwargs)
        
        if not valid:
            logger.warning(f"Client {client_id} requested invalid redirect URI: {redirect_uri}")
            return False
        
        # We could add additional validation here if needed later on
        # For example, checking for HTTPS in production
        
        logger.info(f"Client {client_id} requested valid redirect URI: {redirect_uri}")
        return True
