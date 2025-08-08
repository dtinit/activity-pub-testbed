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

# Get or create the single OAuth Application for a user.
# This enforces the one-application-per-user approach where each user
# represents an ActivityPub service in the LOLA portability flow.
def get_user_application(user, request=None):
    """
    Get or create an OAuth application for a user.
    
    If request is provided, stores the raw client secret in the session
    for later use in token exchange requests. For security reasons, the raw client secret
    is never stored in the database, only the hashed version. We keep the raw version
    in the session temporarily to enable token exchange in the OAuth flow.
    
    Args:
        user: The user to get/create an application for
        request: Optional request object with session for storing client secret
        
    Returns:
        Application instance with raw_client_secret attribute if available
    """
    # Check if user already has an application
    applications = Application.objects.filter(user=user)
    
    if applications.exists():
        # Use the first one if it exists
        application = applications.first()
        if applications.count() > 1:
            # Log warning if multiple exist (shouldn't happen with our business logic)
            logger.warning(f"User {user.username} has multiple OAuth applications. Using the first one.")
        logger.info(f"Retrieved existing OAuth application for user {user.username}")
        
        # Initialize the raw client secret attribute to None
        application.raw_client_secret = None
        
        # If we have the raw client secret in session, use it (needed for token exchange)
        if request and CLIENT_SECRET_SESSION_KEY in request.session:
            # Attach the raw client_secret as an attribute for token exchange
            application.raw_client_secret = request.session[CLIENT_SECRET_SESSION_KEY]
            logger.info("Using raw client secret from session for token exchange")
        elif request:
            logger.warning(f"Raw client secret not found in session for user {user.username}. This will prevent token exchange.")
            # We could potentially implement a client secret recovery mechanism here if needed
            
        # Add client ID to the log for troubleshooting
        logger.info(f"Application details - Client ID: {application.client_id}, Has raw secret: {hasattr(application, 'raw_client_secret') and application.raw_client_secret is not None}")
        
        return application
    
    # Generate credentials
    client_id = random_client_id()
    client_secret = random_client_secret()
    
    # Store the raw client secret in session if request is provided
    if request:
        request.session[CLIENT_SECRET_SESSION_KEY] = client_secret
        logger.info("Stored raw client secret in session for token exchange")
    
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
