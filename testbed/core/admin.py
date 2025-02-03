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
    readonly_fields = ('created_at',)
