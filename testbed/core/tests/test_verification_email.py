from types import SimpleNamespace

import pytest
from allauth.account.models import EmailAddress
from allauth.core import context as allauth_context
from django.core import mail
from django.test import RequestFactory

from testbed.core.adapters import TestbedAccountAdapter as AccountAdapter
from testbed.core.factories import UserOnlyFactory


@pytest.mark.django_db
def test_verification_email_offers_both_a_code_and_a_link(settings):
    settings.ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    user = UserOnlyFactory()
    address = EmailAddress.objects.create(user=user, email=user.email, verified=False)
    request = RequestFactory().get("/account/confirm-email/")
    request.user = user
    confirmation = SimpleNamespace(email_address=address, key="123456")

    with allauth_context.request_context(request):
        AccountAdapter().send_confirmation_mail(request, confirmation, signup=True)

    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert "123456" in body
    assert "/account/confirm-email/" in body
