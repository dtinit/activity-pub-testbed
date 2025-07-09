from django.urls import path
from testbed.core.views import (
    index,
    trigger_account,
    report_activity,
    test_authorization_view,
    test_error_view,
    oauth_callback,
    )

urlpatterns = [
    path("", index, name="home"),
    # Trigger Account: Form to trigger copying an account
    path("trigger-account/", trigger_account, name="trigger-account"),
    # Report Activity: Form to report activity results
    path("report-activity/", report_activity, name="report-activity"),
    # OAuth Testing Views
    path("test/oauth/authorize/", test_authorization_view, name="test-oauth-authorize"),
    path("test/oauth/error/", test_error_view, name="test-oauth-error"),
    path("callback", oauth_callback, name="oauth-callback"),
]
