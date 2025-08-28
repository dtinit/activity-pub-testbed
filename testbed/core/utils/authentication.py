"""
Authentication classes for ActivityPub and LOLA implementation.

This module contains custom authentication classes that support both regular
ActivityPub federation and LOLA account portability requirements.
"""

import logging
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework import exceptions

logger = logging.getLogger(__name__)

class OptionalOAuth2Authentication(OAuth2Authentication):
    """
    Authentication class that makes OAuth2 authentication optional.
    
    This class allows API endpoints to function in two distinct modes:
    1. Unauthenticated Mode: For standard ActivityPub federation
    2. Authenticated Mode: For LOLA account portability with proper OAuth scope
    
    The class adds flags to the request object indicating authentication status
    and whether the token has the LOLA portability scope, allowing views to
    provide enhanced data for authenticated requests while maintaining 
    compatibility with standard ActivityPub clients.
    """
    
    # The specific OAuth scope required for LOLA account portability
    LOLA_PORTABILITY_SCOPE = 'activitypub_account_portability'
    
    def authenticate(self, request):
        """
        Attempt to authenticate the request using OAuth2 with multiple methods.
        
        Authentication priority:
        1. Authorization header (production federation)
        2. URL parameter (testing convenience) 
        3. Session storage (demo enhancement)
        
        If authentication succeeds, check if the token has the portability scope.
        If authentication fails, allow the request to continue as unauthenticated.
        
        This approach enables the same endpoint to serve both:
        - Public data for unauthenticated requests (standard ActivityPub)
        - Enhanced data for authenticated requests with portability scope (LOLA)
        
        Args:
            request: The HTTP request object
            
        Returns:
            A tuple of (user, token) if authentication succeeds, None otherwise
        """
        # Initialize authentication flags on the request object
        request.is_oauth_authenticated = False
        request.has_portability_scope = False
        
        try:
            # 1. First try standard Authorization header authentication (PRODUCTION)
            result = super().authenticate(request)
            
            # 2. If header auth failed, try URL parameter auth (TESTING)
            if result is None:
                result = self._authenticate_with_url_token(request)
            
            # 3. NEW: If URL auth failed, try session auth (DEMO ENHANCEMENT)
            if result is None:
                result = self._try_session_auth(request)
            
            if result is not None:
                user, token = result
                
                # Authentication succeeded
                request.is_oauth_authenticated = True
                logger.debug(f"OAuth authentication successful for user: {user.username}")
                
                # Check if token has the LOLA portability scope
                if self._has_portability_scope(token):
                    request.has_portability_scope = True
                    logger.debug(f"Token has portability scope for user: {user.username}")
                else:
                    logger.debug(f"Token missing portability scope for user: {user.username}")
                
                return user, token
                
        except exceptions.AuthenticationFailed as e:
            # Authentication failed, but we'll continue as unauthenticated
            # This is the key difference from standard OAuth2Authentication
            logger.debug(f"OAuth authentication failed, continuing as unauthenticated: {str(e)}")
            pass
        except Exception as e:
            # Handle any other authentication-related exceptions gracefully
            logger.debug(f"OAuth authentication error, continuing as unauthenticated: {str(e)}")
            pass
            
        # Return None to indicate that authentication was not performed
        # This allows the request to continue as unauthenticated rather than failing
        return None
    
    def _authenticate_with_url_token(self, request):
        """
        Try to authenticate using token from URL parameter (for LOLA testing convenience).
        
        Checks for 'auth_token' in URL parameters and validates it as an OAuth token.
        This enables simple <a> links in templates for testing LOLA functionality.
        
        Args:
            request: The HTTP request object
            
        Returns:
            A tuple of (user, token) if authentication succeeds, None otherwise
        """
        from oauth2_provider.models import AccessToken
        
        # Get token from URL parameter
        token_string = request.GET.get('auth_token')
        if not token_string:
            return None
            
        try:
            # Look up the token in the database
            access_token = AccessToken.objects.select_related('user', 'application').get(
                token=token_string
            )
            
            # Check if token is valid (not expired)
            if access_token.is_valid():
                logger.debug(f"URL parameter authentication successful for user: {access_token.user.username}")
                return access_token.user, access_token
            else:
                logger.debug("URL parameter token is expired or invalid")
                return None
                
        except AccessToken.DoesNotExist:
            logger.debug("URL parameter token not found in database")
            return None
        except Exception as e:
            logger.debug(f"Error during URL parameter authentication: {str(e)}")
            return None

    def _try_session_auth(self, request):
        """
        Try to authenticate using token stored in session (demo enhancement).
        
        This provides seamless authentication after successful OAuth token exchange,
        eliminating the need for manual token handling in demo workflows. The method
        validates session tokens against the database to ensure they haven't been
        revoked and handles automatic cleanup of expired tokens.
        
        Supports 'public_only' parameter to disable session auth for comparison demos.
        
        Args:
            request: The HTTP request object
            
        Returns:
            A tuple of (user, token) if authentication succeeds, None otherwise
        """
        from oauth2_provider.models import AccessToken
        from testbed.core.utils.oauth_utils import get_token_from_session, clear_token_from_session
        
        # Check if public_only parameter is set (for demo comparison)
        if request.GET.get('public_only'):
            logger.debug("public_only parameter detected - skipping session authentication")
            return None
        
        # Get token from session (this handles expiration checking)
        token_string = get_token_from_session(request)
        if not token_string:
            return None
            
        try:
            # Look up the token in the database to ensure it's still valid
            # (handles cases where token was revoked but still in session)
            access_token = AccessToken.objects.select_related('user', 'application').get(
                token=token_string
            )
            
            # Verify token is still valid (handles revocation, etc.)
            if access_token.is_valid():
                logger.debug(f"Session authentication successful for user: {access_token.user.username}")
                return access_token.user, access_token
            else:
                # Token invalid - clear from session to prevent future attempts
                clear_token_from_session(request)
                logger.debug("Session token invalid, cleared from session")
                return None
                
        except AccessToken.DoesNotExist:
            # Token not found in database - clear from session
            logger.debug("Session token not found in database, clearing from session")
            clear_token_from_session(request)
            return None
        except Exception as e:
            logger.debug(f"Error during session authentication: {str(e)}")
            return None
    
    def _has_portability_scope(self, token):
        """
        Check if the token has the LOLA portability scope.
        
        Args:
            token: The OAuth token object
            
        Returns:
            Boolean indicating whether the token has the portability scope
        """
        if not hasattr(token, 'scope'):
            return False
            
        # Handle both string and None scope values safely
        scope = getattr(token, 'scope', '')
        if not scope:
            return False
            
        # Split the scope string and check if it contains the portability scope
        scopes = scope.split()
        return self.LOLA_PORTABILITY_SCOPE in scopes
