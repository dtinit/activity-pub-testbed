import pytest
from django.template.loader import render_to_string
from django.urls import reverse


@pytest.mark.django_db
def test_unknown_page_renders_the_site_404(client):
    response = client.get("/no-such-page/")

    assert response.status_code == 404
    content = response.content.decode()
    assert "Page not found" in content
    assert f'href="{reverse("home")}"' in content


def test_500_page_renders_without_a_request():
    html = render_to_string("500.html")

    assert "Something went wrong" in html
    assert f'href="{reverse("home")}"' in html
    assert "Sign out" not in html
