# from rest_framework.generics import RetrieveAPIView 
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import redirect
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from .models import Actor, PortabilityOutbox
from .serializers import ActorSerializer, PortabilityOutboxSerializer


@api_view(['GET'])
def actor_detail(request, pk):
    actor = get_object_or_404(Actor.objects.all(), pk=pk)
    serializer = ActorSerializer(actor)
    return Response(serializer.data)


@api_view(['GET'])
def portability_outbox_detail(request, pk):
    outbox = get_object_or_404(PortabilityOutbox, actor_id=pk)
    serializer = PortabilityOutboxSerializer(outbox)
    return Response(serializer.data)

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
