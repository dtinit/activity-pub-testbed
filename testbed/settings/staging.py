# ruff: noqa: F405, F403
from .production import *

# Cloud Logging configuration inherited from production.py
# Set USE_GCLOUD_LOGGING=1 in Cloud Run environment variables to enable

ENVIRONMENT = "staging"
ALLOWED_HOSTS = ["activitypub-testbed-stg-run-737003321709.us-central1.run.app"]
SITE_URL = "https://activitypub-testbed-stg-run-737003321709.us-central1.run.app"
BASE_URL = "https://activitypub-testbed-stg-run-737003321709.us-central1.run.app"
CSRF_TRUSTED_ORIGINS = ['https://' + url for url in ALLOWED_HOSTS]
GS_BUCKET_NAME = "activitypub-testbed-stg-storage"

# Update the STORAGES configuration with the staging bucket
for key in STORAGES:
    STORAGES[key]["OPTIONS"]["bucket_name"] = GS_BUCKET_NAME

# Update URLs to use staging bucket
STATIC_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/static/'
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/media/'
