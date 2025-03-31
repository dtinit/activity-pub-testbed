from django.urls import path
from testbed.core.views import (
    ActorDetailView,
    PortabilityOutboxDetailView,
    deactivate_account,
)

urlpatterns = [
    # Actor Endpoint: Retrieve actor details and export LOLA-compliant data
    path("actors/<int:pk>/", ActorDetailView.as_view(), name="actor-detail"),
    # Portability Outbox: Retrieve the outbox linked to the actor
    path(
        "actors/<int:pk>/outbox/",
        PortabilityOutboxDetailView.as_view(),
        name="actor-outbox",
    ),
    # Deactivate Account: API endpoint for account deactivation
    path(
        "actors/<int:actor_id>/deactivate/",
        deactivate_account,
        name="deactivate-account",
    ),
]
