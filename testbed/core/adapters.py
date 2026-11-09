from allauth.account import app_settings
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailConfirmation, EmailConfirmationHMAC
from django.utils import timezone
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

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """
        Include both a verification code and a verification link.

        Allauth normally chooses one method globally. Sending both lets the
        user verify by whichever method they prefer.
        """
        if not app_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED:
            return super().send_confirmation_mail(request, emailconfirmation, signup)

        if app_settings.EMAIL_CONFIRMATION_HMAC:
            link_confirmation = EmailConfirmationHMAC.create(
                emailconfirmation.email_address
            )
        else:
            link_confirmation = EmailConfirmation.create(
                emailconfirmation.email_address
            )
            link_confirmation.sent = timezone.now()
            link_confirmation.save(update_fields=["sent"])
        context = {
            "user": emailconfirmation.email_address.user,
            "code": emailconfirmation.key,
            "activate_url": self.get_email_confirmation_url(request, link_confirmation),
        }
        if signup:
            email_template = "account/email/email_confirmation_signup"
        else:
            email_template = "account/email/email_confirmation"
        self.send_mail(email_template, emailconfirmation.email_address.email, context)
