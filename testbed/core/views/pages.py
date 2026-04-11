"""
Standard Django page views — template rendering and redirect endpoints.

Contains:
- deactivate_account: staff-only action to deactivate a user account
- trigger_account: stub form for triggering account copy
- report_activity: stub form for reporting activity results
- index: dashboard page with actor info and OAuth application settings

These views have no DRF, no JSON-LD, and no LOLA protocol surface area.
They are separated here so that LOLA API changes in later phases do not
produce merge conflicts in the same file as these page views.
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse
from django.shortcuts import redirect, render

from ..models import Actor
from ..oauth.forms import OAuthApplicationForm
from ..oauth.utils import get_user_application

logger = logging.getLogger(__name__)


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
            if "redirect_uris" in oauth_form.errors:
                # Add the error class to the field
                oauth_form.fields["redirect_uris"].widget.attrs["class"] += (
                    " error-field"
                )

                # Get the specific error message
                redirect_error = oauth_form.errors["redirect_uris"][0]
                error_message += f"<br>• {redirect_error}"
            messages.error(request, error_message)
    else:
        # Initialize form with the application instance
        oauth_form = OAuthApplicationForm(instance=application)

    return render(
        request,
        "index.html",
        {
            "source_actor": user_actors.filter(role=Actor.ROLE_SOURCE).first(),
            "destination_actor": user_actors.filter(
                role=Actor.ROLE_DESTINATION
            ).first(),
            "oauth_form": oauth_form,
        },
    )
