from django.contrib import admin
from .models import (
        Actor,
        Note,
        CreateActivity,
        LikeActivity,
        FollowActivity,
        PortabilityOutbox
    )


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ('username', 'full_name', 'created_at', 'updated_at')
    search_fields = ('username', 'full_name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('actor', 'content', 'published', 'visibility')
    list_filter = ('visibility', 'published')
    search_fields = ('content', 'actor__username')

@admin.register(CreateActivity)
class CreateActivityAdmin(admin.ModelAdmin):
    list_display = ('actor', 'timestamp', 'visibility')
    list_filter = ('visibility', 'timestamp')

@admin.register(LikeActivity)
class LikeActivityAdmin(admin.ModelAdmin):
    list_display = ('actor', 'note', 'timestamp', 'visibility')
    list_filter = ('visibility', 'timestamp')

@admin.register(FollowActivity)
class FollowActivityAdmin(admin.ModelAdmin):
    list_display = ('actor', 'target_actor', 'timestamp', 'visibility')
    list_filter = ('visibility', 'timestamp')

@admin.register(PortabilityOutbox)
class PortabilityOutboxAdmin(admin.ModelAdmin):
    list_display = ('actor', 'created_at')
    readonly_fields = ('created_at', 'get_create_activities', 'get_like_activities', 'get_follow_activities')
    fields = ('actor', 'created_at', 'get_create_activities', 'get_like_activities', 'get_follow_activities')

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
            output.append(f"Liked: {activity.note.content[:50]}...")
        
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

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields] + [
            'get_create_activities',
            'get_like_activities',
            'get_follow_activities'
        ]
