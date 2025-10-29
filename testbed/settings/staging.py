# ruff: noqa: F405, F403
from .production import *

ENVIRONMENT = "staging"
ALLOWED_HOSTS = [".run.app"] # Temporary in order to get Cloud Run default
SITE_URL = ""
CSRF_TRUSTED_ORIGINS = ['https://' + url for url in ALLOWED_HOSTS]
GS_BUCKET_NAME = "activitypub-testbed-stg-storage"

# Cloud Run uses X-Forwarded-Proto header for HTTPS detection
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Update the STORAGES configuration with the staging bucket
for key in STORAGES:
    STORAGES[key]["OPTIONS"]["bucket_name"] = GS_BUCKET_NAME

# Update URLs to use staging bucket
STATIC_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/static/'
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/media/'
