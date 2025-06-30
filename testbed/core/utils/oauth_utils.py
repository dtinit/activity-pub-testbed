import logging
from oauth2_provider.models import get_application_model
from testbed.core.utils.utils import random_client_id, random_client_secret

logger = logging.getLogger(__name__)
Application = get_application_model()

# Get or create the single OAuth Application for a user.
# This enforces the one-application-per-user approach where each user
# represents an ActivityPub service in the LOLA portability flow.
def get_user_application(user):

    # Check if user already has an application
    applications = Application.objects.filter(user=user)
    
    if applications.exists():
        # Use the first one if it exists
        application = applications.first()
        if applications.count() > 1:
            # Log warning if multiple exist (shouldn't happen with our business logic)
            logger.warning(f"User {user.username} has multiple OAuth applications. Using the first one.")
        logger.info(f"Retrieved existing OAuth application for user {user.username}")
        return application
    
    # Create a new application with random credentials and ActivityPub-specific name
    logger.info(f"Creating new ActivityPub OAuth application for user {user.username}")
    return Application.objects.create(
        user=user,
        name=f"{user.username}'s ActivityPub Service",
        client_id=random_client_id(),
        client_secret=random_client_secret(),
        redirect_uris='',
        client_type='confidential',
        authorization_grant_type='authorization-code'
    )
