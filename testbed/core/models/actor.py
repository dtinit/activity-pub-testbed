from django.db import models
from django.apps import apps
from datetime import timezone
from ..utils.validators import validate_username
import logging


logger = logging.getLogger(__name__)

    
class Actor(models.Model):
    username = models.CharField(
        max_length=100, unique=True, validators=[validate_username]
    )
    full_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    previously = models.JSONField(default=list, null=True, blank=True)

    def __str__(self):
        return self.username
    
    # Record a previous location of this account
    def record_move(self, previous_server, previous_username, move_date=None):
        print(f"Previously type: {type(self.previously)}")  # Debug line
        print(f"Previously value: {self.previously}")       # Debug line

        if self.previously is None:
            self.previously = []

        move_record = {
            'type': 'Move', 
            'object': f"https://{previous_server}/users/{previous_username}",
            'published': (move_date or timezone.now()).isoformat()
        }

        self.previously.append(move_record)
        self.save()
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            try:

                # Get model classes to avoid circular imports
                PortabilityOutbox = apps.get_model("core", "PortabilityOutbox")
                CreateActivity = apps.get_model("core", "CreateActivity")

                # Create a PortabilityOutbox for new actor
                outbox = PortabilityOutbox.objects.create(actor=self)

                # Create an initial Activity announcing the Actor's creation
                activity = CreateActivity.objects.create(
                    actor=self, visibility="public"
                )

                # Add to Outbox
                outbox.add_activity(activity)

            except Exception as e:
                logger.error(
                    f"Error creating outbox/activity for actor {self.username}: {e}"
                )

    def get_json_ld(self):
        # Return a LOLA-compliant JSON-LD representation of the account
        return {
            "@context": [
                "https://www.w3.org/ns/activitystreams",
                "https://swicg.github.io/activitypub-data-portability/lola.jsonld",
            ],
            "type": "Person",
            "id": f"https://example.com/users/{self.username}",
            "preferredUsername": self.username,
            "name": self.username,
            "previously": self.previously or [], # Ensure it's always a list
        }