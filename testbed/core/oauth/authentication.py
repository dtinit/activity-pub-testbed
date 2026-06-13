"""
Authentication classes for ActivityPub and LOLA implementation.

This module contains custom authentication classes that support both regular
ActivityPub federation and LOLA account portability requirements.
"""

import logging

from django.conf import settings
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
        1. Authorization header - the only normative LOLA path (always enabled)
        2. Session-stored token - gated by LOLA_ALLOW_SESSION_TOKEN_AUTH

        Path 2 is a non-normative testbed convenience that exists because this testbed doubles
        as a destination-side demo tool: after the demo token-exchange flow stores a token in
        the session, the browser can browse the LOLA collections without re-sending a header.
        
        It is NOT part of the LOLA source-server contract and is gated inside its own helper.
        See docs/lola-authentication.md.

        Both enabled paths produce the same (user, token) shape and set
        request.auth to the AccessToken instance. The actor binding check in
        validate_lola_access() operates on request.auth and therefore covers
        every path uniformly.

        If authentication succeeds, checks if the token has the portability scope.
        If authentication fails, allows the request to continue as unauthenticated.

        Args:
            request: The HTTP request object

        Returns:
            A tuple of (user, token) if authentication succeeds, None otherwise
        """
        # Initialize authentication flags on the request object
        request.is_oauth_authenticated = False
        request.has_portability_scope = False
        
        try:
            # 1. Normative path: standard Authorization: Bearer header auth
            result = super().authenticate(request)

            # 2. Demo fallback: session-stored token
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
    
    def _try_session_auth(self, request):
        """
        Try to authenticate using a token stored in the Django session.

        NON-NORMATIVE demo path. After the demo token-exchange flow stores the access token in the
        session (store_token_in_session), later requests from that browser session authenticate automatically.
        The token is re-validated against the DB each request (handles revocation) and expired
        tokens are cleared from the session.

        Supports the 'public_only' query parameter to suppress session auth for
        the demo's public-vs-gated comparison.

        Args:
            request: The HTTP request object

        Returns:
            A tuple of (user, token) if authentication succeeds, None otherwise
            (including when this path is disabled for the environment).
        """
        from testbed.core.oauth.utils import (
            clear_token_from_session,
            get_token_from_session,
        )

        # Skip entirely unless this environment opts in.
        if not getattr(settings, "LOLA_ALLOW_SESSION_TOKEN_AUTH", False):
            logger.debug(
                "Session auth skipped: LOLA_ALLOW_SESSION_TOKEN_AUTH disabled "
                "for this environment"
            )
            return None

        # public_only forces the unauthenticated view for demo comparison.
        if request.GET.get("public_only"):
            logger.debug("public_only set - skipping session authentication")
            return None

        # get_token_from_session handles session-side expiry checking.
        token_string = get_token_from_session(request)
        if not token_string:
            return None

        result = self._resolve_valid_access_token(token_string)
        if result is None:
            # Token missing/expired/revoked in the DB: clear it from the session
            # so we don't keep retrying a dead token on every request.
            clear_token_from_session(request)
            logger.debug("Session token invalid - cleared from session")
            return None

        logger.debug(
            "Session authentication successful for user: %s", result[0].username
        )
        return result

    def _resolve_valid_access_token(self, token_string):
        """
        Look up an AccessToken by its raw string and return (user, token) if it
        exists and is currently valid (not expired), else None.

        Validation step for the session path (_try_session_auth): turns the token
        string read from the session into the (user, AccessToken) pair the auth
        contract expects, rejecting unknown or expired tokens. 
        
        Returns None for a missing token, so callers fail closed to unauthenticated; unexpected
        lookup errors propagate to authenticate(), whose broad handler degrades the request to unauthenticated.
        """
        from oauth2_provider.models import AccessToken

        try:
            access_token = AccessToken.objects.select_related(
                "user", "application"
            ).get(token=token_string)
        except AccessToken.DoesNotExist:
            return None

        if access_token.is_valid():
            return access_token.user, access_token
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
