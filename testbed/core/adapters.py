from allauth.account.adapter import DefaultAccountAdapter
from .models import Actor
import logging

logger = logging.getLogger(__name__)

class TestbedAccountAdapter(DefaultAccountAdapter):
    # Create source and destination actors for any new user
    def create_actors(self, user):
        return Actor.objects.create_actors_for_user(user)
    
    def save_user(self, request, user, form, commit=True):
        # Create user and associated actors
        try:
            # Create User first
            user = super().save_user(request, user, form, commit=True)

            # Create associated actors
            source, dest = self.create_actors(user)

            logger.info(
                f"Created User {user.email} with "
                f"source actor {source.id} and destination actor {dest.id}"
            )

            return user
        
        except Exception as e:
            logger.error(f"Error in user/actor creation for {user.email}: {e}")
            raise