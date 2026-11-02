import pytest
from django.urls import resolve, reverse

from testbed.core.factories import UserOnlyFactory


def signed_in_user(client):
    # The factory sets the password after saving, so save it again before signing in.
    user = UserOnlyFactory()
    user.save()
    client.force_login(user)
    return user


def header_for(content):
    return content.split("<header>", 1)[1].split("</header>", 1)[0]


def test_account_management_url_resolves():
    assert resolve(reverse("account-management")).view_name == "account-management"


@pytest.mark.django_db
def test_account_management_requires_a_signed_in_user(client):
    response = client.get(reverse("account-management"))

    assert response.status_code == 302
    assert (
        response.url
        == f"{reverse('account_login')}?next={reverse('account-management')}"
    )


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
@pytest.mark.parametrize(
    ("page", "other_page"),
    [
        ("account_email", "account_change_password"),
        ("account_change_password", "account_email"),
    ],
)
def test_manage_pages_no_longer_show_the_account_menu(client, page, other_page):
    signed_in_user(client)

    content = client.get(reverse(page)).content.decode()

    assert f'href="{reverse(other_page)}"' not in content
    assert f'href="{reverse("account-management")}"' in content


@pytest.mark.django_db
def test_email_page_renders_the_management_controls(client):
    user = signed_in_user(client)

    content = client.get(reverse("account_email")).content.decode()

    assert user.email in content
    assert "Unverified" in content
    assert 'name="action_primary"' in content
    assert 'name="action_send"' in content
    assert 'name="action_remove"' in content
    assert 'name="action_add"' in content
    assert "New email address" in content


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

    header = header_for(client.get(reverse("home")).content.decode())

    assert f'href="{reverse("account-management")}"' in header
    assert f'href="{reverse("account_logout")}"' not in header


@pytest.mark.django_db
def test_login_page_header_links_to_signup(client):
    header = header_for(client.get(reverse("account_login")).content.decode())

    assert f'href="{reverse("account_signup")}"' in header
    assert f'href="{reverse("account_login")}"' not in header


@pytest.mark.django_db
def test_signup_page_header_links_to_login(client):
    header = header_for(client.get(reverse("account_signup")).content.decode())

    assert f'href="{reverse("account_login")}"' in header
    assert f'href="{reverse("account_signup")}"' not in header
