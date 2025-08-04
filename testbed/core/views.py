# from rest_framework.generics import RetrieveAPIView 
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import redirect
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from .models import Actor, PortabilityOutbox
from .json_ld_builders import build_actor_json_ld, build_outbox_json_ld
from django.contrib.auth.decorators import login_required
from testbed.core.utils.oauth_utils import (
    get_user_application,
    generate_secure_state,
    store_state_in_session,
    validate_state_from_session
)
from testbed.core.forms.oauth_connection_form import OAuthApplicationForm
from django.contrib import messages
from django.urls import reverse
import logging
import requests

logger = logging.getLogger(__name__)

@api_view(['GET'])
def actor_detail(request, pk):
    actor = get_object_or_404(Actor, pk=pk)
    return Response(build_actor_json_ld(actor))

@api_view(['GET'])
def portability_outbox_detail(request, pk):
    outbox = get_object_or_404(PortabilityOutbox, actor_id=pk)
    return Response(build_outbox_json_ld(outbox))

# Restrict the view to staff users using the @user_passes_test decorator
@user_passes_test(lambda u: u.is_staff)  # Restrict to staff
def deactivate_account(request, actor_id):
    # Deactivate a user's account
    actor = Actor.objects.get(pk=actor_id)
    actor.user.is_active = False
    actor.user.save()
    return redirect("admin:index")  # Redirect to admin interface


def trigger_account(request):
    if request.method == "POST":
        # Perform trigger action logic
        return HttpResponse("Account trigger action performed.")
    return render(request, "trigger_account_form.html")


def report_activity(request):
    if request.method == "POST":
        # Perform report activity logic
        return HttpResponse("Activity has been reported.")
    return render(request, "report_activity_form.html")


def index(request):
    if not request.user.is_authenticated:
        return render(request, "index.html")

    user_actors = Actor.objects.filter(user=request.user)
    
    # Get the user's OAuth application using our utility function
    # Pass the request object to allow storing the client secret in the session
    application = get_user_application(request.user, request)

    if request.method == "POST":
        oauth_form = OAuthApplicationForm(request.POST, instance=application)
        if oauth_form.is_valid():
            oauth_form.save()
            messages.success(request, "OAuth connection updated successfully.")
            return redirect("/")  # Redirect to index page instead of using named URL
        else:
            error_message = "There was an error updating your OAuth connection:"
            
            # Handle all redirect_uris errors
            if 'redirect_uris' in oauth_form.errors:
                # Add the error class to the field
                oauth_form.fields['redirect_uris'].widget.attrs['class'] += ' error-field'
                
                # Get the specific error message
                redirect_error = oauth_form.errors['redirect_uris'][0]
                error_message += f"<br>• {redirect_error}"
            messages.error(request, error_message)
    else:
        # Initialize form with the application instance
        oauth_form = OAuthApplicationForm(instance=application)

    return render(request, "index.html", {
        'source_actor': user_actors.filter(role=Actor.ROLE_SOURCE).first(),
        'destination_actor': user_actors.filter(role=Actor.ROLE_DESTINATION).first(),
        'oauth_form': oauth_form,
    })


# OAuth Testing Views

def oauth_callback(request):
    """
    Handle the callback from the OAuth server
    This displays the authorization code or error message
    """
    # Get query parameters
    code = request.GET.get('code')
    error = request.GET.get('error')
    error_description = request.GET.get('error_description')
    state = request.GET.get('state')
    
    # Initialize context with received parameters
    context = {
        'code': code,
        'error': error,
        'error_description': error_description,
        'state': state
    }
    
    # Validate the state parameter to prevent CSRF attacks
    if not state:
        logger.warning("OAuth callback received with no state parameter")
        context['error'] = 'invalid_state'
        context['error_description'] = 'No state parameter provided'
    else:
        is_valid_state = validate_state_from_session(request, state)
        if not is_valid_state:
            logger.warning("OAuth callback received with invalid state parameter")
            context['error'] = 'invalid_state'
            context['error_description'] = 'Invalid state parameter'
    
    # Log successful authorization
    if code and not error and not context.get('error'):
        logger.info("Successfully received authorization code in callback")
    
    return render(request, 'oauth_callback.html', context)

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
        logger.info(f"Added {redirect_uri} to redirect URIs for application {application.client_id}")
    
    # Generate a secure random state parameter and store it in the session
    state = generate_secure_state()
    store_state_in_session(request, state)
    
    # Build the authorization URL
    params = {
        'client_id': application.client_id,
        'response_type': 'code',
        'scope': 'activitypub_account_portability',
        'redirect_uri': redirect_uri,
        'state': state
    }
    
    # Convert params to URL query string
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    auth_url = f"{reverse('oauth2_provider:authorize')}?{query_string}"
    
    return redirect(auth_url)

@login_required
def test_error_view(request):
    """
    Test view to simulate an OAuth error.
    This renders the error template with a sample error.
    """
    error = {
        'error': 'invalid_request',
        'description': 'This is a test error to preview the error template.',
        'uri': None
    }
    
    return render(request, 'oauth2_provider/error.html', {'error': error})


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
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    context = {
        'code': code,
        'state': state,
        'error': error,
        'token_response': None,
        'token_error': None,
    }
    
    # If we have an error or no code, don't attempt token exchange
    if error or not code:
        context['token_error'] = "Cannot exchange token: no valid authorization code provided"
        return render(request, 'oauth_token_exchange.html', context)
    
    # Get the application for client credentials
    application = get_user_application(request.user, request)
    
    # Prepare token request parameters
    token_url = f"{request.scheme}://{request.get_host()}/oauth/token/"
    redirect_uri = f"{request.scheme}://{request.get_host()}/callback"
    
    # Check if we have a raw client secret available
    if not hasattr(application, 'raw_client_secret') or not application.raw_client_secret:
        logger.error(f"Raw client secret not available for token exchange. Client ID: {application.client_id}")
        context['token_error'] = "Client secret not available. This may happen if your session expired. Try restarting the OAuth flow."
        return render(request, 'oauth_token_exchange.html', context)
        
    # Log client credentials status (without exposing the actual secret)
    logger.info(f"Client credentials prepared for token exchange. Client ID: {application.client_id}")
    logger.info(f"Raw client secret available: {bool(application.raw_client_secret)}")
    
    # Prepare the data for token exchange
    # This follows the OAuth 2.0 specification for token requests
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        # We'll use HTTP Basic Auth instead of including these in the body
        # 'client_id': application.client_id,
        # 'client_secret': application.raw_client_secret,
    }
    
    try:
        # Make the token request
        logger.info(f"Attempting to exchange authorization code for token")
        
        # Log the complete request details for debugging (except the secret)
        logger.info(f"Token request URL: {token_url}")
        logger.info(f"Token request parameters: {token_data}")
        
        # Get client credentials
        client_id = application.client_id
        client_secret = application.raw_client_secret
        
        # Set standard content type header for form data
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
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
            auth=(client_id, client_secret)  # HTTP Basic Authentication
        )
        
        # If first method fails with 401 Unauthorized, try the alternative method
        if token_response.status_code == 401:
            logger.info("HTTP Basic Authentication failed. Trying with credentials in request body.")
            # Create a new copy of token_data with client credentials included
            body_auth_data = token_data.copy()
            body_auth_data['client_id'] = client_id
            body_auth_data['client_secret'] = client_secret
            
            # Make the request with credentials in the request body
            token_response = requests.post(
                token_url, 
                data=body_auth_data,
                headers=headers
            )
            
            # Log which method succeeded
            if token_response.status_code == 200:
                logger.info("Token exchange succeeded using request body authentication")
        
        # Check if the request was successful
        if token_response.status_code == 200:
            # Parse the JSON response
            token_json = token_response.json()
            logger.info("Successfully exchanged authorization code for token")
            context['token_response'] = token_json
        else:
            # Handle error response with detailed logging
            logger.warning(f"Token exchange failed with status {token_response.status_code}")
            logger.warning(f"Response headers: {dict(token_response.headers)}")
            
            try:
                error_details = token_response.json()
                logger.warning(f"Response JSON: {error_details}")
                context['token_error'] = f"Error: {error_details.get('error', 'Unknown error')}"
                if 'error_description' in error_details:
                    context['token_error'] += f" - {error_details['error_description']}"
            except:
                logger.warning(f"Response text: {token_response.text}")
                context['token_error'] = f"Error: HTTP {token_response.status_code} - {token_response.text}"
    
    except Exception as e:
        # Handle exceptions during the request
        logger.error(f"Exception during token exchange: {str(e)}")
        context['token_error'] = f"Exception: {str(e)}"
    
    return render(request, 'oauth_token_exchange.html', context)
