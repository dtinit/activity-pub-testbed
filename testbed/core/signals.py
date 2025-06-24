from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from testbed.core.models import Actor
from testbed.core.utils.actor_utils import populate_source_actor_outbox
import logging

logger = logging.getLogger(__name__)

"""
    Signal handler to ensure all users have source and destination actors
    This is the single point of actor creation for all users
"""
@receiver(post_save, sender=User)
def create_actors_for_new_users(sender, instance, created, **kwargs):
    # Only run for newly created users
    if not created:
        return
        
    # Skip if user already has actors
    if instance.actors.exists():
        logger.debug(f"User {instance.username} already has actors, skipping creation")
        return
        
    # Create the source and destination actors
    try:
        source, dest = Actor.objects.create_actors_for_user(instance)
        logger.info(
            f"Created actors for {instance.username}: "
            f"source={source.id}, destination={dest.id}"
        )
        
        # Populate the source actor's outbox with sample content
        # Check if there are other actors for local interactions
        include_local = Actor.objects.filter(role=Actor.ROLE_SOURCE).count() > 1
        
        results = populate_source_actor_outbox(
            source_actor=source,
            include_local_interactions=include_local
        )
        
        logger.info(f"Populated outbox for {instance.username}'s source actor with sample content")
        
    except Exception as e:
        logger.error(f"Error creating/populating actors for {instance.username}: {e}")
