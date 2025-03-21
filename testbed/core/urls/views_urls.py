from django.urls import path
from testbed.core.views import trigger_account, report_activity

urlpatterns = [
    # Trigger Account: Form to trigger copying an account
    path("trigger-account/", trigger_account, name="trigger-account"),
    # Report Activity: Form to report activity results
    path("report-activity/", report_activity, name="report-activity"),
]
