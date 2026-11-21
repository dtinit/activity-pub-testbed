"""
Destination page views: where a source sends the user back during a transfer.

Contains:
    - transfer_callback: Completes one transfer job's OAuth authorization (LOLA §5.3)
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET

from ..models import TransferJob
from ..transfer import auth, jobs
from ..transfer.transport import TransportError


@login_required
@require_GET
def transfer_callback(request):
    state = request.GET.get("state")
    # Without this, a missing state would match every job whose state is NULL
    if not state:
        raise Http404
    # Only the job's owner can complete it (RFC 6749 §10.12)
    job = get_object_or_404(
        TransferJob,
        oauth_state=state,
        destination_actor__user=request.user,
        state=TransferJob.State.ACTIVE,
    )

    try:
        auth.complete_authorization(job, request.GET)
    except (auth.AuthorizationError, TransportError) as exc:
        jobs.fail(job, str(exc))
        messages.error(request, f"Authorization did not complete: {exc}")
    else:
        messages.success(request, f"Authorized as {job.authorized_actor_url}")
    return redirect("home")
