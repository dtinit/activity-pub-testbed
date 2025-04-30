from django.urls import path
from testbed.core.views import (
    index,
    login_view,
    logout_view,
    trigger_account,
    report_activity,
    )

urlpatterns = [
    path("", index, name="home"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    # Trigger Account: Form to trigger copying an account
    path("trigger-account/", trigger_account, name="trigger-account"),
    # Report Activity: Form to report activity results
    path("report-activity/", report_activity, name="report-activity"),
    

]
