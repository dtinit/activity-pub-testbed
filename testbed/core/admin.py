from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models.auth import TesterUser
from .models import (
    Actor,
    Note,
    CreateActivity,
    LikeActivity,
    FollowActivity,
    PortabilityOutbox,
)

@admin.register(TesterUser)
class TesterUserAdmin(UserAdmin):
    list_display = ("email", "is_tester", "email_verified", "is_staff", "is_active")
    list_filter = ("is_tester", "email_verified", "is_staff", "is_active")
    readonly_fields = ("email_verified", "date_joined", "last_login")

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_tester', 'email_verified', 'is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    # Override add_fieldsets to use email instead of username
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )

    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)



@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ("username", "full_name", "created_at", "updated_at")
    search_fields = ("username", "full_name")
    readonly_fields = ("created_at", "updated_at")


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
