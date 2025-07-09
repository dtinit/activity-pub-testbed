from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from testbed.core.utils.oauth_utils import get_user_application
from django.conf import settings
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

"""
Test view to simulate initiating an OAuth authorization flow.
This will redirect to the authorization endpoint with appropriate parameters.
"""
@login_required
def test_authorization_view(request):    
    # Get the user's OAuth application (this is normally used by the destination service)
    application = get_user_application(request.user)
    
    # Build the authorization URL
    params = {
        'client_id': application.client_id,
        'response_type': 'code',
        'scope': 'activitypub_account_portability',
        'redirect_uri': application.redirect_uris.split()[0],  # Use the first redirect URI
        'state': 'test_state_123'  # In a real app, this would be a secure random string
    }
    
    # Convert params to URL query string
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    auth_url = f"{reverse('oauth2_provider:authorize')}?{query_string}"
    
    return redirect(auth_url)


"""
Test view to simulate an OAuth error.
This renders the error template with a sample error.
"""
@login_required
def test_error_view(request):

    error = {
        'error': 'invalid_request',
        'description': 'This is a test error to preview the error template.',
        'uri': None
    }
    
    return render(request, 'oauth2_provider/error.html', {'error': error})
