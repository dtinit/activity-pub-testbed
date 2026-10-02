from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from testbed.core.models import Actor
from testbed.core.utils.provisioning import provision_actor_content
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
        
    source, dest = Actor.objects.create_actors_for_user(instance)
    logger.info(
        f"Created actors for {instance.username}: "
        f"source={source.id}, destination={dest.id}"
    )

    provision_actor_content(source)
