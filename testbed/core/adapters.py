from allauth.account.adapter import DefaultAccountAdapter
from .models import Actor
import logging

logger = logging.getLogger(__name__)

class TestbedAccountAdapter(DefaultAccountAdapter):    
    def save_user(self, request, user, form, commit=True):
        try:
            # Create User first
            user = super().save_user(request, user, form, commit=True)

            # Create associated actors
            source, dest = Actor.objects.create_actors_for_user(user)

            logger.info(
                f"Created User {user.email} with "
                f"source actor {source.id} and destination actor {dest.id}"
            )
            return user
        
        except Exception as e:
            logger.error(f"Error in user/actor creation for {user.email}: {e}")
            raise