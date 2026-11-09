"""
URL configuration for testbed project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from allauth.account.views import confirm_email
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from testbed.core.views import account_management, oauth_authorization_server_metadata
from testbed.core.oauth import PortabilityAuthorizationView

urlpatterns = [
    # Admin Panel
    path("admin/", admin.site.urls),
    # LOLA Discovery: RFC8414-compliant OAuth Authorization Server Metadata (root level for federation)
    path(
        ".well-known/oauth-authorization-server",
        oauth_authorization_server_metadata,
        name="oauth-server-metadata",
    ),
    # API-specific endpoints (prefixed with '/api/')
    path("api/", include("testbed.core.urls.api_urls")),
    path("account/", account_management, name="account-management"),
    # Allauth omits the link route when verification by code is enabled.
    # Register it so verification emails can offer both a code and a link.
    *(
        [
            path(
                "account/confirm-email/<str:key>/",
                confirm_email,
                name="account_confirm_email",
            )
        ]
        if getattr(settings, "ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED", False)
        else []
    ),
    # allauth
    path("account/", include("allauth.urls")),
    # LOLA authorization override
    path(
        "oauth/authorize/",
        PortabilityAuthorizationView.as_view(),
        name="authorize",
    ),
    # OAuth2 provider endpoints (token, revoke, introspect, etc.)
    path("oauth/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    # Regular views (no prefix)
    path("", include("testbed.core.urls.views_urls")),
]
