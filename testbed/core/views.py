from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.generics import RetrieveAPIView
from rest_framework.authtoken.models import Token
from oauth2_provider.contrib.rest_framework import TokenHasScope
from oauth2_provider.models import Application, AccessToken
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from datetime import timedelta
from .models import Actor, PortabilityOutbox
from .serializers import ActorSerializer, PortabilityOutboxSerializer, UserRegistrationSerializer, LoginSerializer

import uuid


# Public endpoint (no token required)
class TesterRegistrationView(APIView):
    permissions_classes = [AllowAny] # Allow anyone to register

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'message': 'Tester account created successfully.',
                'user_id': user.id,
                'username': user.username,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# Public endpoint (no token required)
class LoginView(APIView):
    permission_classes = [AllowAny]  # Allow anyone to log in
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Get or create application (this happens once per login)
        app, _ = Application.objects.get_or_create(
            name="Testbed Default",
            defaults={
                'client_type': Application.CLIENT_CONFIDENTIAL,
                'authorization_grant_type': Application.GRANT_PASSWORD,
                'skip_authorization': True
            }
        )

        # Generate access token
        access_token = AccessToken.objects.create(
            user=user,
            application=app,
            expires=timezone.now() + timedelta(seconds=3600),
            scope='read write private',
            token=str(uuid.uuid4())
        )

        return Response({
            'message': 'Login successful',
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'token': {
                'access_token': access_token.token,
                'token_type': 'Bearer',
                'expires_in': 3600,
                'scope': access_token.scope
            }
        }, status=status.HTTP_200_OK)

# Protected endpoint (requires token)
class ActorDetailView(RetrieveAPIView):
    permission_classes = [TokenHasScope]
    required_scopes = ['read']  # Public Actor data -> Require 'read' scope for this view 
    queryset = Actor.objects.all()
    serializer_class = ActorSerializer


class PortabilityOutboxDetailView(RetrieveAPIView):
    # queryset = PortabilityOutbox.objects.all()
    permission_classes = [TokenHasScope]
    required_scopes = ['private']  # Private data access -> Require 'private' scope for this view
    serializer_class = PortabilityOutboxSerializer

    def get_object(self):
        # Retrieve the outbox for the given actor
        actor_id = self.kwargs["pk"]
        return get_object_or_404(PortabilityOutbox, actor_id=actor_id)


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
