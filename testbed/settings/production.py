# ruff: noqa: F405, F403
import sys
from google.oauth2 import service_account
from .base import *

ENVIRONMENT = "production"
DEBUG = False
ALLOWED_SEED_COMMAND = False
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = [".run.app"] # Temporary in order to get Cloud Run default
SITE_URL = ""

# PostgreSQL for production
DATABASES = {"default": env.db_url("DJ_DATABASE_CONN_STRING")}

CSRF_TRUSTED_ORIGINS = ['https://' + url for url in ALLOWED_HOSTS]
GS_CREDENTIALS = service_account.Credentials.from_service_account_file(
    'service-account-credentials.json'
)
GS_BUCKET_NAME = "activitypub-testbed-prod-storage"

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "bucket_name": GS_BUCKET_NAME,
            "location": "media",
        }
    },
    "staticfiles": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "bucket_name": GS_BUCKET_NAME,
            "location": "static",
        }
    },
}

STATIC_URL = f'<https://storage.googleapis.com/{GS_BUCKET_NAME}/static/>'
MEDIA_URL = f'<https://storage.googleapis.com/{GS_BUCKET_NAME}/media/>'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'django_google_structured_logger.formatter.GoogleFormatter',
        },
    },
    
    'handlers': {
        'google_cloud': {
            'class': 'google.cloud.logging_v2.handlers.StructuredLogHandler',
            'stream': sys.stdout,
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['google_cloud'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['google_cloud'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['google_cloud'],
            'level': 'INFO',
            'propagate': False,
        },
        'testbed': {
            'handlers': ['google_cloud'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = "noreply@dtinit.org"
EMAIL_HOST_PASSWORD = env.str('EMAIL_HOST_PASSWORD')