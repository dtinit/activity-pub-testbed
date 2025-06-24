from allauth.account.adapter import DefaultAccountAdapter
from .models import Actor
import logging

logger = logging.getLogger(__name__)

class TestbedAccountAdapter(DefaultAccountAdapter):    
    def save_user(self, request, user, form, commit=True):
        try:
            # Just create the user - signal will handle actor creation
            user = super().save_user(request, user, form, commit=True)
            logger.info(f"Created User {user.email} (actors will be created by signal)")
            return user
        
        except Exception as e:
            logger.error(f"Error in user creation for {user.email}: {e}")
            raise
