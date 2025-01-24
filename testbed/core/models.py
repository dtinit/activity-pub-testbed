import logging
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


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
                activity = CreateActivity.objects.create(
                    actor=self,
                    visibility='public'
                )

                # Add to Outbox
                outbox.add_activity(activity)

            except Exception as e:
                logger.error(f'Error creating outbox/activity for actor {self.username}: {e}') 

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
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, related_name="%(class)s_activities") # This makes each subclass have its own related_name 
    timestamp = models.DateTimeField(auto_now_add=True)
    visibility = models.CharField(max_length=20, default="public", choices=[
        ("public", "Public"),
        ("private", "Private"),
        ("followers-only", "Followers only")
    ])

    class Meta:
        abstract = True # This makes it a base clas that won't create its own table

class CreateActivity(Activity):
    note = models.OneToOneField(
        "Note",
        on_delete=models.CASCADE,
        related_name="create_activities",
        null=True,
        blank=True
    )

    def get_json_ld(self):
        json_ld = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Create",
            "id": f"https://example.com/activities/{self.id}",
            "actor": f"https://example.com/users/{self.actor.username}",
            "published": self.timestamp.isoformat(),
            "visibility": self.visibility,
        }

        if self.note:
            json_ld['object'] = self.note.get_json_ld()
        else:
            json_ld['object'] = self.actor.get_json_ld()

        return json_ld
    

class LikeActivity(Activity):
    note = models.OneToOneField(
        "Note",
        on_delete=models.CASCADE,
        related_name="like_activities"
    )

    def get_json_ld(self):
        return {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Like",
            "id": f"https://example.com/activities/{self.id}",
            "actor": f"https://example.com/users/{self.actor.username}",
            "object": self.note.get_json_ld(),
            "published": self.timestamp.isoformat(),
            "visibility": self.visibility,
        }
    

class FollowActivity(Activity):
    target_actor = models.ForeignKey(
        Actor,
        on_delete=models.CASCADE,
        related_name="follow_activities_received"
    )

    def get_json_ld(self):
        return {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Follow",
            "id": f"https://example.com/activities/{self.id}",
            "actor": f"https://example.com/users/{self.actor.username}",
            "object": self.target_actor.get_json_ld(),
            "published": self.timestamp.isoformat(),
            "visibility": self.visibility,
        }



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
    activities_create = models.ManyToManyField(CreateActivity, related_name="outboxes")
    activities_like = models.ManyToManyField(LikeActivity, related_name="outboxes")
    activities_follow = models.ManyToManyField(FollowActivity, related_name="outboxes")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Outbox for {self.actor.username}"
    
    # Helper method to add any type of activity
    def add_activity(self, activity):
        if isinstance(activity, CreateActivity):
            self.activities_create.add(activity)
        elif isinstance(activity, LikeActivity):
            self.activities_like.add(activity)
        elif isinstance(activity, FollowActivity):
            self.activities_follow.add(activity)

    def get_json_ld(self):
        # Combine all activity types
        create_activities = list(self.activities_create.all())
        like_activities = list(self.activities_like.all())
        follow_activities = list(self.activities_follow.all())

        all_activities = create_activities + like_activities + follow_activities
        
        # Sort by timestamp
        all_activities.sort(key=lambda x: x.timestamp, reverse=True)

        return {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "OrderedCollection",
            "id": f"https://example.com/users/{self.actor.username}/outbox",
            "totalItems": len(all_activities),
            "items": [activity.get_json_ld() for activity in all_activities],
        }
