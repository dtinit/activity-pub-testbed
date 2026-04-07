"""
OAuth test and demo views — simulate the destination-side OAuth flow.

Contains:
- oauth_callback: handle OAuth server redirect with authorization code or error
- test_authorization_view: initiate an OAuth authorization flow for testing
- test_error_view: render an OAuth error template for UI preview
- test_token_exchange_view: exchange an authorization code for an access token

These views are development/testing utilities that demonstrate what a destination
service would do during a LOLA account migration. They are not part of the LOLA
protocol surface area for source servers, but live in this codebase as a reference
implementation of the destination-side OAuth interaction.

Separated from api.py so that Phase 1 OAuth changes (activitypub_actor in redirect,
token-to-actor binding) can be made here without touching LOLA collection views.
"""

import logging

import requests
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from ..models import Actor
from testbed.core.utils.oauth_utils import (
    generate_secure_state,
    get_user_application,
    store_state_in_session,
    validate_state_from_session,
)

logger = logging.getLogger(__name__)


def oauth_callback(request):
    """
    Handle the callback from the OAuth server.
    This displays the authorization code or error message.
    """
    # Get query parameters
    code = request.GET.get("code")
    error = request.GET.get("error")
    error_description = request.GET.get("error_description")
    state = request.GET.get("state")

    # Initialize context with received parameters
    context = {
        "code": code,
        "error": error,
        "error_description": error_description,
        "state": state,
    }

    # Validate the state parameter to prevent CSRF attacks
    if not state:
        logger.warning("OAuth callback received with no state parameter")
        context["error"] = "invalid_state"
        context["error_description"] = "No state parameter provided"
    else:
        is_valid_state = validate_state_from_session(request, state)
        if not is_valid_state:
            logger.warning("OAuth callback received with invalid state parameter")
            context["error"] = "invalid_state"
            context["error_description"] = "Invalid state parameter"

    # Log successful authorization
    if code and not error and not context.get("error"):
        logger.info("Successfully received authorization code in callback")

    return render(request, "oauth_callback.html", context)


@login_required
def test_authorization_view(request):
    """
    Test view to simulate initiating an OAuth authorization flow.
    This will redirect to the authorization endpoint with appropriate parameters.
    """
    # Get the user's OAuth application (this is normally used by the destination service)
    # Pass the request object to allow storing the client secret in the session
    application = get_user_application(request.user, request)

    # Use our own callback URL for the test flow
    scheme = request.scheme
    host = request.get_host()
    redirect_uri = f"{scheme}://{host}/callback"

    # Update the application's redirect URIs if needed
    if redirect_uri not in application.redirect_uris:
        if application.redirect_uris:
            application.redirect_uris = f"{application.redirect_uris} {redirect_uri}"
        else:
            application.redirect_uris = redirect_uri
        application.save()
        logger.info(
            f"Added {redirect_uri} to redirect URIs for application {application.client_id}"
        )

    # Generate a secure random state parameter and store it in the session
    state = generate_secure_state()
    store_state_in_session(request, state)

    # Build the authorization URL
    params = {
        "client_id": application.client_id,
        "response_type": "code",
        "scope": "activitypub_account_portability",
        "redirect_uri": redirect_uri,
        "state": state,
    }

    # Convert params to URL query string
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    auth_url = f"{reverse('oauth2_provider:authorize')}?{query_string}"

    return redirect(auth_url)


@login_required
def test_error_view(request):
    """
    Test view to simulate an OAuth error.
    This renders the error template with a sample error.
    """
    error = {
        "error": "invalid_request",
        "description": "This is a test error to preview the error template.",
        "uri": None,
    }

    return render(request, "oauth2_provider/error.html", {"error": error})


# Token Exchange View
@login_required
def test_token_exchange_view(request):
    """
    Demonstrate exchanging an authorization code for an access token.

    This view simulates what a destination service would do after receiving
    an authorization code. It makes a token request to the token endpoint
    using the authorization code, client credentials, and redirect URI.
    """
    # Get query parameters from the callback
    code = request.GET.get("code")
    state = request.GET.get("state")
    error = request.GET.get("error")

    # Get the user's source actor for LOLA testing
    user_actors = Actor.objects.filter(user=request.user)
    source_actor = user_actors.filter(role=Actor.ROLE_SOURCE).first()

    context = {
        "code": code,
        "state": state,
        "error": error,
        "token_response": None,
        "token_error": None,
        "source_actor": source_actor,  # Add source actor for LOLA testing
    }

    # If we have an error or no code, don't attempt token exchange
    if error or not code:
        context["token_error"] = (
            "Cannot exchange token: no valid authorization code provided"
        )
        return render(request, "oauth_token_exchange.html", context)

    # Get the application for client credentials
    application = get_user_application(request.user, request)

    # Prepare token request parameters
    token_url = f"{request.scheme}://{request.get_host()}/oauth/token/"
    redirect_uri = f"{request.scheme}://{request.get_host()}/callback"

    # Check if we have a raw client secret available
    if (
        not hasattr(application, "raw_client_secret")
        or not application.raw_client_secret
    ):
        logger.error(
            f"Raw client secret not available for token exchange. Client ID: {application.client_id}"
        )
        context["token_error"] = (
            "Client secret not available. This may happen if your session expired. Try restarting the OAuth flow."
        )
        return render(request, "oauth_token_exchange.html", context)

    # Log client credentials status (without exposing the actual secret)
    logger.info(
        f"Client credentials prepared for token exchange. Client ID: {application.client_id}"
    )
    logger.info(f"Raw client secret available: {bool(application.raw_client_secret)}")

    # Prepare the data for token exchange
    # This follows the OAuth 2.0 specification for token requests
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        # We'll use HTTP Basic Auth instead of including these in the body
        # 'client_id': application.client_id,
        # 'client_secret': application.raw_client_secret,
    }

    try:
        # Make the token request
        logger.info("Attempting to exchange authorization code for token")

        # Log the complete request details for debugging (except the secret)
        logger.info(f"Token request URL: {token_url}")
        logger.info(f"Token request parameters: {token_data}")

        # Get client credentials
        client_id = application.client_id
        client_secret = application.raw_client_secret

        # Set standard content type header for form data
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        # OAuth 2.0 spec allows for two methods of client authentication:
        # 1. HTTP Basic Authentication (preferred and more secure)
        # 2. Including client credentials in the request body

        # First try: Use HTTP Basic Authentication for client credentials (preferred method)
        logger.info("Attempting token exchange using HTTP Basic Authentication")
        token_response = requests.post(
            token_url,
            data=token_data.copy(),  # Use a copy to avoid modifying the original
            headers=headers,
            auth=(client_id, client_secret),  # HTTP Basic Authentication
        )

        # If first method fails with 401 Unauthorized, try the alternative method
        if token_response.status_code == 401:
            logger.info(
                "HTTP Basic Authentication failed. Trying with credentials in request body."
            )
            # Create a new copy of token_data with client credentials included
            body_auth_data = token_data.copy()
            body_auth_data["client_id"] = client_id
            body_auth_data["client_secret"] = client_secret

            # Make the request with credentials in the request body
            token_response = requests.post(
                token_url, data=body_auth_data, headers=headers
            )

            # Log which method succeeded
            if token_response.status_code == 200:
                logger.info(
                    "Token exchange succeeded using request body authentication"
                )

        # Check if the request was successful
        if token_response.status_code == 200:
            # Parse the JSON response
            token_json = token_response.json()
            logger.info("Successfully exchanged authorization code for token")
            context["token_response"] = token_json

            # NEW: Store token in session for seamless demo authentication
            from testbed.core.utils.oauth_utils import store_token_in_session

            store_token_in_session(request, token_json)
            context["session_auth_enabled"] = True
            logger.info("Token stored in session - demo authentication now active")
        else:
            # Handle error response with detailed logging
            logger.warning(
                f"Token exchange failed with status {token_response.status_code}"
            )
            logger.warning(f"Response headers: {dict(token_response.headers)}")

            try:
                error_details = token_response.json()
                logger.warning(f"Response JSON: {error_details}")
                context["token_error"] = (
                    f"Error: {error_details.get('error', 'Unknown error')}"
                )
                if "error_description" in error_details:
                    context["token_error"] += f" - {error_details['error_description']}"
            except (ValueError, KeyError):
                # ValueError catches JSONDecodeError (response body is not valid JSON).
                # KeyError is included defensively; in practice it cannot fire here
                # because error_details['error_description'] is guarded by the 'in' check above.
                # Note: AttributeError/TypeError (non-dict JSON) fall through to the outer
                # except Exception handler at the call site with a less precise error message.
                logger.warning(f"Response text: {token_response.text}")
                context["token_error"] = (
                    f"Error: HTTP {token_response.status_code} - {token_response.text}"
                )

    except Exception as e:
        # Handle exceptions during the request
        logger.error(f"Exception during token exchange: {str(e)}")
        context["token_error"] = f"Exception: {str(e)}"

    return render(request, "oauth_token_exchange.html", context)
