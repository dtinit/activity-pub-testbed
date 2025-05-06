from django.db import models
from .actor import Actor

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