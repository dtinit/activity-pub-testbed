import logging
import secrets  # Python's secure random number generator module
import base64   # For encoding binary data as text
from oauth2_provider.models import get_application_model
from testbed.core.utils.utils import random_client_id, random_client_secret

logger = logging.getLogger(__name__)
Application = get_application_model()

# Constant to use as the session key for storing the OAuth state parameter
# Using a specific key helps avoid conflicts with other session variables
OAUTH_STATE_SESSION_KEY = 'oauth_state'

# Session key for storing raw client secret
CLIENT_SECRET_SESSION_KEY = 'oauth_client_secret'

# Session keys for OAuth token storage (demo enhancement)
# These enable seamless authentication after successful token exchange
ACCESS_TOKEN_SESSION_KEY = 'lola_access_token'
TOKEN_EXPIRY_SESSION_KEY = 'lola_token_expiry'
TOKEN_SCOPE_SESSION_KEY = 'lola_token_scope'

# Get or create the single OAuth Application for a user.
# This enforces the one-application-per-user approach where each user
# represents an ActivityPub service in the LOLA portability flow.
def get_user_application(user, request=None):
    """
    Get or create an OAuth application for a user with encrypted client secret storage.
    
    This function now uses encrypted database storage for client secrets, solving the
    "Token Exchange Failed" issue caused by fragile session-based storage. Client secrets
    are always available for token exchange regardless of session state.
    
    Args:
        user: The user to get/create an application for
        request: Optional request object (maintained for compatibility)
        
    Returns:
        Application instance with raw_client_secret attribute always available
    """
    from testbed.core.models import OAuthClientCredentials
    
    # Check if user already has an application
    applications = Application.objects.filter(user=user)
    
    if applications.exists():
        # Use the first one if it exists
        application = applications.first()
        if applications.count() > 1:
            # Log warning if multiple exist (shouldn't happen with our business logic)
            logger.warning(f"User {user.username} has multiple OAuth applications. Using the first one.")
        logger.info(f"Retrieved existing OAuth application for user {user.username}")
        
        # Try to get client secret from encrypted storage
        try:
            credentials = OAuthClientCredentials.objects.get(user=user)
            application.raw_client_secret = credentials.get_client_secret()
            logger.info(f"Retrieved encrypted client secret for user {user.username}")
            
        except OAuthClientCredentials.DoesNotExist:
            logger.warning(f"No encrypted client credentials found for user {user.username}")
            
            # MIGRATION: Try session storage as fallback for existing users
            if request and CLIENT_SECRET_SESSION_KEY in request.session:
                client_secret = request.session[CLIENT_SECRET_SESSION_KEY]
                logger.info(f"Migrating client secret from session to encrypted storage for user {user.username}")
                
                # Create encrypted credentials record
                credentials = OAuthClientCredentials.objects.create(user=user)
                credentials.set_client_secret(client_secret)
                credentials.save()
                
                application.raw_client_secret = client_secret
                logger.info(f"Successfully migrated client secret to encrypted storage")
                
                # Clean up session storage
                request.session.pop(CLIENT_SECRET_SESSION_KEY, None)
            else:
                logger.error(f"No client secret available for user {user.username} - neither encrypted storage nor session")
                application.raw_client_secret = None
        
        except Exception as e:
            logger.error(f"Error retrieving encrypted client secret for user {user.username}: {str(e)}")
            application.raw_client_secret = None
            
        # Add client ID to the log for troubleshooting
        logger.info(f"Application details - Client ID: {application.client_id}, Has raw secret: {hasattr(application, 'raw_client_secret') and application.raw_client_secret is not None}")
        
        return application
    
    # Generate credentials for new application
    client_id = random_client_id()
    client_secret = random_client_secret()
    
    # Create a new application with random credentials and ActivityPub-specific name
    logger.info(f"Creating new ActivityPub OAuth application for user {user.username}")
    application = Application.objects.create(
        user=user,
        name=f"{user.username}'s ActivityPub Service",
        client_id=client_id,
        client_secret=client_secret,
        redirect_uris='',
        client_type='confidential',
        authorization_grant_type='authorization-code'
    )
    
    # Store client secret in encrypted storage
    try:
        credentials = OAuthClientCredentials.objects.create(user=user)
        credentials.set_client_secret(client_secret)
        credentials.save()
        logger.info(f"Stored client secret in encrypted storage for user {user.username}")
    except Exception as e:
        logger.error(f"Failed to store encrypted client secret for user {user.username}: {str(e)}")
        # Fall back to session storage for this session
        if request:
            request.session[CLIENT_SECRET_SESSION_KEY] = client_secret
            logger.info("Fallback: stored client secret in session")
    
    # Attach the raw client_secret as an attribute for token exchange
    application.raw_client_secret = client_secret
    
    return application

# ============================================================================
# CSRF Protection for OAuth Flow
# ============================================================================
# The following functions implement the state parameter handling for OAuth 2.0
# as specified in RFC 6749 Section 10.12 (CSRF Protection)
# https://datatracker.ietf.org/doc/html/rfc6749#section-10.12
#
# The state parameter is critical for preventing Cross-Site Request Forgery attacks
# in the OAuth authorization flow. Without it, an attacker could trick a user into
# authorizing a malicious application without the user's knowledge.

def generate_secure_state(length=32):
    """
    Generate a cryptographically secure random string for use as a state parameter
    in the OAuth 2.0 flow to prevent CSRF attacks.
    
    - Using a cryptographically secure random generator prevents attackers from guessing the state
    - The state parameter acts as a nonce that binds the authorization request to the client
    - We use base64url encoding to make it URL-safe (important for query parameters)
    
    Args:
        length: The length of the random bytes to generate (32 provides ~256 bits of entropy)
        
    Returns:
        A URL-safe base64-encoded random string
    """
    # Generate random bytes using Python's cryptographically secure RNG
    # secrets.token_bytes is designed for security-critical randomness
    random_bytes = secrets.token_bytes(length)
    
    # Encode as URL-safe base64 and remove padding
    # URL-safe base64 ensures the state parameter works properly in URLs
    # Removing padding ('=') characters makes it cleaner in query strings
    return base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')
    
def store_state_in_session(request, state):
    """
    Store the OAuth state parameter in the user's session for later validation.
    
    - The state must persist between the authorization request and callback
    - Using the session is more secure than cookies or local storage
    - This creates a server-side record of the expected state parameter
    
    Args:
        request: The HTTP request object with session
        state: The state parameter to store
    """
    request.session[OAUTH_STATE_SESSION_KEY] = state
    logger.info("Stored OAuth state parameter in session")
    
def validate_state_from_session(request, state):
    """
    Validate that the provided state parameter matches the one stored in the session.
    
    Why we need this:
    - Validates that the authorization response matches our original request
    - Prevents CSRF attacks by ensuring the callback wasn't initiated by an attacker
    - Uses a constant-time comparison to prevent timing attacks
    - Removes the state from session after validation to prevent replay attacks
    
    Args:
        request: The HTTP request object with session
        state: The state parameter from the callback to validate
        
    Returns:
        True if the state is valid, False otherwise
    """
    stored_state = request.session.get(OAUTH_STATE_SESSION_KEY)
    
    # If there's no stored state, validation fails
    # This could happen if the session expired or if this is a forged request
    if not stored_state:
        logger.warning("No OAuth state parameter found in session")
        return False
    
    # Clear the state from session to prevent replay attacks
    # This ensures the same state value can't be reused for multiple validations
    request.session.pop(OAUTH_STATE_SESSION_KEY, None)
    
    # Compare the stored state with the provided state using constant-time comparison
    # secrets.compare_digest prevents timing attacks that could occur with simple == comparison
    is_valid = secrets.compare_digest(stored_state, state)
    
    if is_valid:
        logger.info("OAuth state parameter validated successfully")
    else:
        logger.warning("OAuth state parameter validation failed")
        
    return is_valid

# ============================================================================
# Session Token Management for Demo Enhancement
# ============================================================================
# These functions enable seamless authentication after OAuth token exchange
# by storing tokens in session storage. This solves the "Token Exchange Failed"
# issue and provides a smooth demo experience.

def store_token_in_session(request, token_data):
    """
    Store OAuth token in session after successful exchange.
    
    This enables seamless authentication for demo workflows by maintaining
    authentication state after token exchange. Users can now click collection
    test links without manual token handling.
    
    Args:
        request: The HTTP request object with session
        token_data: Dictionary containing token response data
                   Expected keys: access_token, expires_in, scope
    """
    from datetime import datetime, timedelta
    
    # Store the access token
    access_token = token_data.get('access_token')
    if not access_token:
        logger.warning("No access_token in token_data, cannot store in session")
        return
    
    request.session[ACCESS_TOKEN_SESSION_KEY] = access_token
    
    # Calculate and store expiry time
    expires_in = token_data.get('expires_in', 3600)  # Default 1 hour if not specified
    expiry_time = datetime.now() + timedelta(seconds=expires_in)
    request.session[TOKEN_EXPIRY_SESSION_KEY] = expiry_time.timestamp()
    
    # Store scope for validation
    scope = token_data.get('scope', '')
    request.session[TOKEN_SCOPE_SESSION_KEY] = scope
    
    logger.info(f"OAuth token stored in session for demo authentication (expires in {expires_in} seconds)")

def get_token_from_session(request):
    """
    Get valid OAuth token from session, None if expired or missing.
    
    This function handles token expiration automatically by checking timestamps
    and cleaning up expired tokens. This prevents authentication with invalid tokens.
    
    Args:
        request: The HTTP request object with session
        
    Returns:
        String containing access token if valid, None if expired/missing
    """
    from datetime import datetime
    
    token = request.session.get(ACCESS_TOKEN_SESSION_KEY)
    if not token:
        logger.debug("No OAuth token found in session")
        return None
        
    # Check if token has expired
    expiry_timestamp = request.session.get(TOKEN_EXPIRY_SESSION_KEY)
    if expiry_timestamp:
        if datetime.now().timestamp() > expiry_timestamp:
            clear_token_from_session(request)
            logger.debug("Session OAuth token expired, cleared from session")
            return None
    
    logger.debug("Valid OAuth token retrieved from session")
    return token

def get_token_scope_from_session(request):
    """
    Get OAuth token scope from session.
    
    This enables scope validation for session-based authentication,
    ensuring LOLA portability scope requirements are met.
    
    Args:
        request: The HTTP request object with session
        
    Returns:
        String containing token scope, empty string if not found
    """
    scope = request.session.get(TOKEN_SCOPE_SESSION_KEY, '')
    logger.debug(f"Retrieved token scope from session: '{scope}'")
    return scope

def clear_token_from_session(request):
    """
    Clear OAuth token data from session.
    
    This function provides secure cleanup of token data, used when tokens
    expire, become invalid, or when users explicitly log out of demo sessions.
    
    Args:
        request: The HTTP request object with session
    """
    # Remove all token-related session data
    keys_removed = []
    
    if ACCESS_TOKEN_SESSION_KEY in request.session:
        request.session.pop(ACCESS_TOKEN_SESSION_KEY, None)
        keys_removed.append('access_token')
        
    if TOKEN_EXPIRY_SESSION_KEY in request.session:
        request.session.pop(TOKEN_EXPIRY_SESSION_KEY, None)
        keys_removed.append('expiry')
        
    if TOKEN_SCOPE_SESSION_KEY in request.session:
        request.session.pop(TOKEN_SCOPE_SESSION_KEY, None)
        keys_removed.append('scope')
    
    if keys_removed:
        logger.info(f"OAuth token data cleared from session: {', '.join(keys_removed)}")
    else:
        logger.debug("No OAuth token data found in session to clear")

# OAuth Endpoint URL Construction
def build_oauth_endpoint_url(request):
    """
    Build OAuth authorization endpoint URL for LOLA discovery.
    
    This function constructs the OAuth authorization endpoint URL that will be
    included in ActivityPub Actor responses for LOLA account portability.
    The URL allows other ActivityPub services to discover where users can
    authorize access for account migration.
    
    Args:
        request: The HTTP request object containing scheme and host information
        
    Returns:
        String containing the fully qualified OAuth authorization endpoint URL
    """
    scheme = request.scheme
    host = request.get_host()
    return f"{scheme}://{host}/oauth/authorize/"
