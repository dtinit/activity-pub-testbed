from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "testbed.core"
    
    def ready(self):
        import testbed.core.signals
