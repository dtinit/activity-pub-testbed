# ruff: noqa: F405, F403
import os
from .base import *

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

ENVIRONMENT = "development"
DEBUG = True
ALLOWED_SEED_COMMAND = True
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="your-dev-secret-key")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Seeding settings
SEED_ADMIN_USERNAME = ("admin",)
SEED_ADMIN_EMAIL = ("admin@testing.com",)
SEED_ADMIN_PASSWORD = ("admin123",)

# Database settings
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    "default": env.db_url(
        "DJ_DATABASE_CONN_STRING", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}

if DEBUG:
    LOGGING["handlers"]["structured_file"] = {
        "class": "logging.FileHandler", # FileHandler overwrites on each run
        "filename": os.path.join(LOGS_DIR, "structured.log"),
        "formatter": "key_value",
        "mode": "w", # 'w' overwrites the file each time
    }

    LOGGING["loggers"].update({
        # Comment out this section and comment the section below to see django_structlog output in console
        # "django_structlog": {
        #     "handlers": ["console"],
        #     "level": "INFO",
        # },

        # Current active configuration - writes to file, overwriting on each server start
        "django_structlog": {
            "handlers": ["structured_file"],
            "level": "INFO",
        },

    })

# REST Framework Development Configuration
# https://www.django-rest-framework.org/api-guide/settings/

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny', 

    ),
}