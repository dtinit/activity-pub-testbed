# from rest_framework.generics import RetrieveAPIView 
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import redirect
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from .models import Actor, PortabilityOutbox
from .json_ld_builders import build_actor_json_ld, build_outbox_json_ld

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
    return render(request, "index.html")
