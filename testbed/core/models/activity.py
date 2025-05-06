from django.db import models
from django.core.exceptions import ValidationError
from .actor import Actor

class Activity(models.Model):
    actor = models.ForeignKey(
        Actor, on_delete=models.CASCADE, related_name="%(class)s_activities"
    )  # This makes each subclass have its own related_name
    timestamp = models.DateTimeField(auto_now_add=True)
    visibility = models.CharField(
        max_length=20,
        default="public",
        choices=[
            ("public", "Public"),
            ("private", "Private"),
            ("followers-only", "Followers only"),
        ],
    )

    class Meta:
        abstract = True  # This makes it a base clas that won't create its own table


class CreateActivity(Activity):
    note = models.OneToOneField(
        "Note",
        on_delete=models.CASCADE,
        related_name="create_activities",
        null=True,
        blank=True,
    )

    def __str__(self):
        if self.note:
            return f"Create by {self.actor.username}: {self.note}"
        return f"Create by {self.actor.username}: Actor creation"

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
            json_ld["object"] = self.note.get_json_ld()
        else:
            json_ld["object"] = self.actor.get_json_ld()

        return json_ld


class LikeActivity(Activity):
    note = models.ForeignKey(
        "Note",
        on_delete=models.CASCADE,
        related_name="like_activities",
        null=True,
        blank=True,
    )
    object_url = models.URLField(
        max_length=200,
        help_text="URL of the liked object in the fediverse",
        null=True,
        blank=True,
    )
    object_data = models.JSONField(
        help_text="Metadata of the liked object", null=True, blank=True
    )

    def clean(self):
        super().clean()
        # For remote objects, we need both url and data
        if not self.object_url and not (self.object_url and self.object_data):
            raise ValidationError("Remote objects must have both URL and metadata")

    def __str__(self):
        if self.note:
            return f"Like by {self.actor.username}: {self.note}"
        content = self.object_data.get("content", "")[:50]
        return f"Like by {self.actor.username}: {content}..."

    def get_json_ld(self):
        base = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Like",
            "id": f"https://example.com/activities/{self.id}",
            "actor": f"https://example.com/users/{self.actor.username}",
            "published": self.timestamp.isoformat(),
            "visibility": self.visibility,
        }

        if self.note:
            # For local notes, use the Note model's get_json_ld method
            base["object"] = self.note.get_json_ld()
        else:
            # For remote objects, use the stored data
            base["object"] = {
                "@context": "https://www.w3.org/ns/activitystreams",
                **self.object_data,
                "id": self.object_url,
            }

        return base


class FollowActivity(Activity):
    target_actor = models.ForeignKey(
        Actor,
        on_delete=models.CASCADE,
        related_name="follow_activities_received",
        null=True,
        blank=True
    )
    target_actor_url = models.URLField(
        max_length=200,
        help_text="URL of the followed actor in the fediverse",
        null=True,
        blank=True
    )
    target_actor_data = models.JSONField(
        help_text="Metadata of the followed actor",
        null=True,
        blank=True,
    )

    def clean(self):
        super().clean()
        if not self.target_actor and not (self.target_actor_url and self.target_actor_data):
            raise ValidationError("Either local target_actor or remote actor data (URL and metadata) must be provided")

    def __str__(self):
        if self.target_actor:
            return f'Follow by {self.actor.username}: {self.target_actor.username}'
        username = self.target_actor_data.get('preferredUsername', '')
        return f'Follow by {self.actor.username}: {username} (remote)'
    
    def get_json_ld(self):
        base = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Follow",
            "id": f"https://example.com/activities/{self.id}",
            "actor": f"https://example.com/users/{self.actor.username}",
            "published": self.timestamp.isoformat(),
            "visibility": self.visibility,
        }

        if self.target_actor:
            base["object"] = self.target_actor.get_json_ld()
        else:
            base["object"] = {
                "@context": "https://www.w3.org/ns/activitystreams",
                **self.target_actor_data,
                "id": self.target_actor_url
            }

        return base