# ruff: noqa: F405, F403
from google.oauth2 import service_account
from .base import *

ENVIRONMENT = "production"
DEBUG = False
ALLOWED_SEED_COMMAND = False
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = ["ap-testbed.dtinit.org", "www.ap-testbed.dtinit.org", "activitypub-testbed-prod-run-512458093489.us-central1.run.app"]
SITE_URL = "https://ap-testbed.dtinit.org"
BASE_URL = "https://ap-testbed.dtinit.org"

# Cloud Run uses X-Forwarded-Proto header for HTTPS detection
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

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
    "sass_processor": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "bucket_name": GS_BUCKET_NAME,
            "location": "static",
        }
    }
}

STATIC_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/static/'
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/media/'

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = "noreply@dtinit.org"
EMAIL_HOST_PASSWORD = env.str('EMAIL_HOST_PASSWORD')

# Google Cloud Logging with automatic trace correlation.
# Enabled via USE_GCLOUD_LOGGING=1 environment variable.
from testbed.core.utils.logging_utils import setup_cloud_logging
setup_cloud_logging()
