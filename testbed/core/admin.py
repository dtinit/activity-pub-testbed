from django.contrib import admin
from .models import (
    Actor,
    Note,
    CreateActivity,
    LikeActivity,
    FollowActivity,
    PortabilityOutbox,
    TransferJob,
    TransferredItem,
)


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'role')

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("actor", "content", "published", "visibility")
    list_filter = ("visibility", "published")
    search_fields = ("content", "actor__username")


@admin.register(CreateActivity)
class CreateActivityAdmin(admin.ModelAdmin):
    list_display = ("actor", "timestamp", "visibility")
    list_filter = ("visibility", "timestamp")


@admin.register(LikeActivity)
class LikeActivityAdmin(admin.ModelAdmin):
    list_display = ("actor", "get_liked_object", "timestamp", "visibility")
    list_filter = ("visibility", "timestamp")
    search_fields = ("actor__username", "object_url", "object_data__content")

    def get_liked_object(self, obj):
        if obj.note:
            return f"Local: {obj.note}"
        return (
            f"Remote: {obj.object_data.get('content', '')[:50]}... ({obj.object_url})"
        )

    get_liked_object.short_description = "Liked Object"


@admin.register(FollowActivity)
class FollowActivityAdmin(admin.ModelAdmin):
    list_display = ("actor", "target_actor", "timestamp", "visibility")
    list_filter = ("visibility", "timestamp")


@admin.register(PortabilityOutbox)
class PortabilityOutboxAdmin(admin.ModelAdmin):
    list_display = ("actor", "created_at")
    readonly_fields = (
        "created_at",
        "get_create_activities",
        "get_like_activities",
        "get_follow_activities",
    )
    fields = (
        "actor",
        "created_at",
        "get_create_activities",
        "get_like_activities",
        "get_follow_activities",
    )

    def get_create_activities(self, obj):
        if not obj:
            return "No create activities"

        create_activities = obj.activities_create.filter(actor=obj.actor)
        output = []
        for activity in create_activities:
            if activity.note:
                output.append(f"Created note: {activity.note.content[:50]}...")
            else:
                output.append("Created actor profile")

        return "\n".join(output) if output else "No create activities"

    get_create_activities.short_description = "Create Activities"

    def get_like_activities(self, obj):
        if not obj:
            return "No like activities"

        like_activities = obj.activities_like.filter(actor=obj.actor)
        output = []
        for activity in like_activities:
            if activity.note:
                output.append(f"Liked local: {activity.note.content[:50]}...")
            else:
                content = activity.object_data.get("content", "")[:50]
                output.append(f"Liked remote: {content}... ({activity.object_url})")

        return "\n".join(output) if output else "No like activities"

    get_like_activities.short_description = "Like Activities"

    def get_follow_activities(self, obj):
        if not obj:
            return "No follow activities"

        follow_activities = obj.activities_follow.filter(actor=obj.actor)
        output = []
        for activity in follow_activities:
            output.append(f"Followed: {activity.target_actor.username}")

        return "\n".join(output) if output else "No follow activities"

    get_follow_activities.short_description = "Follow Activities"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class TransferredItemInline(admin.TabularInline):
    model = TransferredItem
    extra = 0
    can_delete = False
    fields = (
        "collection",
        "object_type",
        "source_id",
        "destination_id",
        "outcome",
        "created_at",
    )
    readonly_fields = fields
    ordering = ("collection", "id")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TransferJob)
class TransferJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "destination_actor",
        "state",
        "retry_when",
        "created_at",
        "updated_at",
    )
    list_filter = ("state", "retry_when", "created_at")
    search_fields = (
        "destination_actor__user__username",
        "source_base_url",
        "source_actor_url",
        "authorized_actor_url",
    )
    readonly_fields = ("policy", "progress", "artifacts", "created_at", "updated_at")
    inlines = [TransferredItemInline]

    list_select_related = ("destination_actor", "destination_actor__user")

    @admin.display(ordering="destination_actor__user__username", description="User")
    def user(self, obj):
        return obj.user


@admin.register(TransferredItem)
class TransferredItemAdmin(admin.ModelAdmin):

    list_display = ("id", "job", "collection", "object_type", "outcome", "created_at")
    list_filter = ("collection", "outcome", "created_at")
    search_fields = ("source_id", "destination_id", "job__id")

    list_select_related = ("job", "job__destination_actor__user")
    readonly_fields = (
        "job",
        "collection",
        "source_id",
        "destination_id",
        "object_type",
        "outcome",
        "detail",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
