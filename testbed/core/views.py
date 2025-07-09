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
from testbed.core.utils.oauth_utils import get_user_application
from testbed.core.forms.oauth_connection_form import OAuthApplicationForm
from django.contrib import messages
from django.urls import reverse
import logging

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
    application = get_user_application(request.user)

    if request.method == "POST":
        oauth_form = OAuthApplicationForm(request.POST, instance=application)
        if oauth_form.is_valid():
            oauth_form.save()
            messages.success(request, "OAuth connection updated successfully.")
            return redirect("/")  # Redirect to index page instead of using named URL
        else:
            messages.error(request, "There was an error updating your OAuth connection.")
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
    
    context = {
        'code': code,
        'error': error,
        'error_description': error_description,
        'state': state
    }
    
    return render(request, 'oauth_callback.html', context)

@login_required
def test_authorization_view(request):
    """
    Test view to simulate initiating an OAuth authorization flow.
    This will redirect to the authorization endpoint with appropriate parameters.
    """
    # Get the user's OAuth application (this is normally used by the destination service)
    application = get_user_application(request.user)
    
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
    
    # Build the authorization URL
    params = {
        'client_id': application.client_id,
        'response_type': 'code',
        'scope': 'activitypub_account_portability',
        'redirect_uri': redirect_uri,
        'state': 'test_state_123'  # In a real app, this would be a secure random string
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
