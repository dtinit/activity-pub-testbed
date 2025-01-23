from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

def validate_username(value):
    if " " in value or not value.isalnum():
        raise ValidationError("Username must be alphanumeric and contain no spaces.")

    if len(value) < 3:
        raise ValidationError("Username must be at least 3 characters.")

class Actor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='actor')
    username = models.CharField(max_length=100, unique=True, validators=[validate_username])
    full_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    previously = models.JSONField(default=dict, null=True, blank=True)

    def __str__(self):
        return self.username
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            try:
                # Create a PortabilityOutbox for new actor
                outbox = PortabilityOutbox.objects.create(actor=self)

                # Create an initial Activity announcing the Actor's creation
                activity = Activity.objects.create(
                    actor=self,
                    type='Create',
                    visibility='public'
                )

                # Add to Outbox before modifying get_json_ld() to maintain relationship
                outbox.activities.add(activity)

                if hasattr(activity, 'get_json_ld'):
                    # Store the original get_json_ld() output
                    original_get_json_ld = activity.get_json_ld()

                    # Override the activity's get_json_ld() method to include the actor as the object
                    def get_modified_json_ld():
                        base_json = original_get_json_ld()
                        base_json['object'] = self.get_json_ld()
                        return base_json
            
                    activity.get_json_ld = get_modified_json_ld
            except Exception as e:
                print(f'Error creating outbox/activity for actor: {e}')

            
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
            "previously": self.previously,
        }


class Activity(models.Model):
    # TODO: Check ActivityStreams and ActivityPub specifications
    TYPE_CHOICES = [
        ("Create", "Create"),
        ("Like", "Like"),
        ("Update", "Update"),
        ("Follow", "Follow"),
        ("Announce", "Announce"),
        ("Delete", "Delete"),
        ("Undo", "Undo"),
        ("Flag", "Flag"),
    ]

    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, related_name="actor_activities")
    type = models.CharField(max_length=100, choices=TYPE_CHOICES)
    note = models.OneToOneField("Note", on_delete=models.CASCADE, related_name="note_activities", null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    visibility = models.CharField(max_length=20, default="public", choices=[
        ("public", "Public"),
        ("private", "Private"),
        ("followers-only", "Followers only")
    ])

    def __str__(self):
        return f"{self.actor.username} - {self.type} at {self.timestamp}"

    def get_json_ld(self):
        json_ld = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": self.type,
            "id": f"https://example.com/activities/{self.id}",
            "actor": f"https://example.com/users/{self.actor.username}",
            "published": self.timestamp.isoformat(),
            "visibility": self.visibility,
        }

        # Note's get_json_ld() method
        if self.note:
            json_ld["object"] = self.note.get_json_ld()
        return json_ld


class Note(models.Model):
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, related_name="notes")
    content = models.TextField()
    published = models.DateTimeField(auto_now_add=True)
    visibility = models.CharField(max_length=20, default="public", choices=[
        ("public", "Public"),
        ("private", "Private"),
        ("followers-only", "Followers Only")
    ])

    def __str__(self):
        return f"Note by {self.actor.username}: {self.content[:30]}"

    def get_json_ld(self):
        return {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Note",
            "id": f"https://example.com/notes/{self.id}",
            "actor": f"https://example.com/users/{self.actor.username}",
            "content": self.content,
            "published": self.published.isoformat(),
            "visibility": self.visibility,
        }


class PortabilityOutbox(models.Model):
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, related_name="portability_outbox")
    activities = models.ManyToManyField(Activity, related_name="portability_outbox")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Outbox for {self.actor.username}"

    def get_json_ld(self):
        return {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "OrderedCollection",
            "id": f"https://example.com/users/{self.actor.username}/outbox",
            "totalItems": self.activities.count(),
            "items": [activity.get_json_ld() for activity in self.activities.all()],
        }
