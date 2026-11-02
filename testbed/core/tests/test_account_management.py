import pytest
from django.urls import reverse

from testbed.core.factories import UserOnlyFactory


def signed_in_user(client):
    # The factory sets the password after saving, so save it again before signing in.
    user = UserOnlyFactory()
    user.save()
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_account_management_requires_a_signed_in_user(client):
    response = client.get(reverse("account-management"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("account_login"))


@pytest.mark.django_db
def test_account_management_lists_the_account_actions(client):
    user = signed_in_user(client)

    response = client.get(reverse("account-management"))
    content = response.content.decode()

    assert response.status_code == 200
    assert user.email in content
    assert "Account settings" in content
    assert "Change email" in content
    assert "Change password" in content
    assert f'href="{reverse("account_email")}"' in content
    assert f'href="{reverse("account_change_password")}"' in content
    assert f'href="{reverse("account_logout")}"' in content


@pytest.mark.django_db
def test_sign_out_page_no_longer_lists_the_account_actions(client):
    signed_in_user(client)

    content = client.get(reverse("account_logout")).content.decode()

    assert reverse("account_email") not in content
    assert reverse("account_change_password") not in content


@pytest.mark.django_db
def test_sign_out_confirmation_offers_cancel_and_sign_out(client):
    signed_in_user(client)

    response = client.get(reverse("account_logout"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Sign out?" in content
    assert f'href="{reverse("account-management")}"' in content


@pytest.mark.django_db
def test_sign_out_confirmation_signs_the_user_out(client):
    signed_in_user(client)

    response = client.post(reverse("account_logout"))

    assert response.status_code == 302
    assert response.url == reverse("home")
    assert "Sign in" in client.get(reverse("home")).content.decode()


@pytest.mark.django_db
def test_the_header_links_to_account_management_instead_of_sign_out(client):
    signed_in_user(client)

    content = client.get(reverse("home")).content.decode()

    assert f'href="{reverse("account-management")}"' in content
    assert f'href="{reverse("account_logout")}"' not in content
