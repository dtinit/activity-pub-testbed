from django.db import models
from .actor import Actor
from .activity import CreateActivity, LikeActivity, FollowActivity

class PortabilityOutbox(models.Model):
    actor = models.ForeignKey(
        Actor, on_delete=models.CASCADE, related_name="portability_outbox"
    )
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