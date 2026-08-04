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

"""
Who counts as "the client" for rate limiting.

Direct public Cloud Run traffic always passes through Google's managed frontend,
so REMOTE_ADDR is that frontend rather than the caller and must not be assumed to be
the original caller. The caller's real address is in X-Forwarded-For instead. That header is a
list, and each machine appends what it saw -- so the entries on the RIGHT are
trustworthy and the ones on the LEFT are whatever the caller typed.

Cloud Run does not document a stable, trusted X-Forwarded-For layout for this
run.app/domain-mapping path. (The "<client>, <load-balancer>" format is specified for
external Application Load Balancers, which this testbed does not use yet.)

This number says how many entries on the right belong to Google. The caller is the
one just before them.

     1  ->  "<caller>, <google>"     picks <caller>
     0  ->  ignore the header, use REMOTE_ADDR (= Google, so everyone shares
            a single rate-limit bucket)

Why 1 when Google does not document the exact layout for this run.app /
domain-mapping path: for honest callers 1 is never worse than 0. If the layout is
what we expect, 1 identifies each caller correctly. If it is not, 1 falls back to
REMOTE_ADDR and behaves exactly like 0.

The risk of 1 is that a caller could pad the header to get a fresh bucket every
request and dodge the limit -- and nothing logs when that happens.

To check it after deploy: make one request with NO X-Forwarded-For, then look for
"client resolution: xff_entries=N" in the logs. Set this to N - 1.
See docs/lola-rate-limiting.md.
"""
RATE_LIMIT_TRUSTED_PROXY_DEPTH = env.int("DJANGO_RATE_LIMIT_TRUSTED_PROXY_DEPTH", default=1)

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
