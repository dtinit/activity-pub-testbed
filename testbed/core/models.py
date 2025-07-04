import logging
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from datetime import timezone

logger = logging.getLogger(__name__)

class ActorManager(models.Manager):
    # Create both source and destination actors for a user
    def create_actors_for_user(self, user, source_username=None, destination_username=None):
        source = self.create(
            user=user,
            username=source_username or f"{user.username}_source",
            role=Actor.ROLE_SOURCE,
        )
        destination = self.create(
            user=user,
            username=destination_username or f"{user.username}_dest",
            role=Actor.ROLE_DESTINATION,
        )

        return source, destination


class Actor(models.Model):
    ROLE_SOURCE = "source"
    ROLE_DESTINATION = "destination"
    ROLE_CHOICES = [
        (ROLE_SOURCE, "Source Service"),
        (ROLE_DESTINATION, "Destination Service"),
    ]

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name="actors")
    username = models.CharField(max_length=100, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    previously = models.JSONField(default=list, null=True, blank=True)

    objects = ActorManager()

    def __str__(self):
        return f"{self.user.username}'s {self.role} actor"
    
    @property
    def is_source(self):
        return self.role == self.ROLE_SOURCE
    
    @property
    def is_destination(self):
        return self.role == self.ROLE_DESTINATION
    
    # Record a previous location of this account
    def record_move(self, previous_server, previous_username, move_date=None):
        if self.previously is None:
            self.previously = []

        move_record = {
            'type': 'Move', 
            'object': f"https://{previous_server}/users/{previous_username}",
            'published': (move_date or timezone.now()).isoformat()
        }

        self.previously.append(move_record)
        self.save()

    # Initialize outbox and create activity for any actor type
    def initialize_actor(self):
        try:
            # Create a PortabilityOutbox for new actor
            outbox, created = PortabilityOutbox.objects.get_or_create(actor=self)

            # Only create the initial activity if this is a new outbox
            if created:
                # Create an initial Activity announcing the Actor's creation
                activity = CreateActivity.objects.create(
                    actor=self,
                    visibility="public",
                )
                # Add the activity to the outbox
                outbox.add_activity(activity)

        except Exception as e:
            logger.error(f"Error initializing actor {self.user.username}: {e}")
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            self.initialize_actor()

    def clean(self):
        super().clean()
        if self.user.actors.filter(role=self.role).exists():
            raise ValidationError(f"User {self.user.username} already has an actor with role {self.role}")

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
            return f"Create by {self.actor.user.username}: {self.note}"
        return f"Create by {self.actor.user.username}: Actor creation"

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
            return f"Like by {self.actor.user.username}: {self.note}"
        content = self.object_data.get("content", "")[:50]
        return f"Like by {self.actor.user.username}: {content}..."

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
            return f'Follow by {self.actor.user.username}: {self.target_actor.user.username}'
        username = self.target_actor_data.get('preferredUsername', '')
        return f'Follow by {self.actor.user.username}: {username} (remote)'

class Note(models.Model):
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, related_name="notes")
    content = models.TextField()
    published = models.DateTimeField(auto_now_add=True)
    visibility = models.CharField(
        max_length=20,
        default="public",
        choices=[
            ("public", "Public"),
            ("private", "Private"),
            ("followers-only", "Followers Only"),
        ],
    )

    def __str__(self):
        return f"Note by {self.actor.user.username}: {self.content[:30]}"

class PortabilityOutbox(models.Model):
    actor = models.OneToOneField(
        Actor, on_delete=models.CASCADE, related_name="portability_outbox"
    )
    activities_create = models.ManyToManyField(CreateActivity, related_name="outboxes")
    activities_like = models.ManyToManyField(LikeActivity, related_name="outboxes")
    activities_follow = models.ManyToManyField(FollowActivity, related_name="outboxes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['actor'],
                name='unique_actor_outbox'
            )
        ]

    def __str__(self):
        return f"Outbox for {self.actor.user.username}"

    # Helper method to add any type of activity
    def add_activity(self, activity):
        if isinstance(activity, CreateActivity):
            self.activities_create.add(activity)
        elif isinstance(activity, LikeActivity):
            self.activities_like.add(activity)
        elif isinstance(activity, FollowActivity):
            self.activities_follow.add(activity)
