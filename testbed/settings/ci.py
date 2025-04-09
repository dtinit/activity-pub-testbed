# ruff: noqa: F405, F403
from .base import *


ENVIRONMENT = "ci"
DEBUG = True
ALLOWED_SEED_COMMAND = True
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS") + ["testserver"]

# Seeding settings
SEED_ADMIN_USERNAME = ("admin",)
SEED_ADMIN_EMAIL = ("admin@testing.com",)
SEED_ADMIN_PASSWORD = ("admin123",)

DATABASES = {"default": env.db_url("DJ_DATABASE_CONN_STRING")}

LOGGING["loggers"] = {
    "django": {
        "handlers": ["rich_console"],
        "level": "WARNING",
        "propagate": False,
    }
}