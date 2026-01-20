"""
Uses Google's setup_logging() which automatically:
- Detects Django framework
- Extracts X-Cloud-Trace-Context headers from requests
- Adds trace/spanId to all log entries
- Groups logs by request in Cloud Logging

References:
- https://cloud.google.com/python/docs/reference/logging/latest/auto-trace-span-extraction
- https://cloud.google.com/trace/docs/trace-log-integration
- https://docs.cloud.google.com/python/docs/reference/logging/latest/client
- https://github.com/googleapis/python-logging/blob/main/google/cloud/logging_v2/handlers/handlers.py
"""

import os
import logging

logger = logging.getLogger(__name__)


def setup_cloud_logging():
    """
    Initialize Google Cloud Logging with automatic trace correlation.

    Returns:
        bool: True if Cloud Logging was successfully initialized, False if not

    Environment Variables:
        USE_GCLOUD_LOGGING: Set to "1" to enable Cloud Logging
        GOOGLE_CLOUD_PROJECT: GCP project ID (auto-detected on Cloud Run)
    """
    if os.environ.get('USE_GCLOUD_LOGGING', '0') != '1':
        logger.info(
            "Cloud Logging disabled (USE_GCLOUD_LOGGING != 1)"
        )
        return False

    try:
        import google.cloud.logging

        client = google.cloud.logging.Client()

        client.setup_logging(log_level=logging.INFO)

        logger.info(
            "Cloud Logging initialized with automatic trace correlation"
        )
        return True

    except Exception as e:
        logger.warning(
            f"Failed to initialize Cloud Logging: {e}. "
            "Falling back to console logging."
        )
        return False
