"""
This module provides functions for Google Cloud Logging handlers,
properly isolates Cloud-specific dependencies to production/staging
"""

import os
import logging


def get_cloud_logging_handler():
    """
    1. Checks if Cloud Logging is enabled (USE_GCLOUD_LOGGING env var)
    2. Imports google-cloud-logging packages ONLY if enabled
    3. Returns configured handler with trace correlation filter
    
    Returns:
        logging.Handler: CloudLoggingHandler configured with custom logName and
                        trace filter, or NullHandler if Cloud Logging is disabled
    
    Environment Variables:
        USE_GCLOUD_LOGGING: Set to "1" to enable Cloud Logging
        GOOGLE_CLOUD_PROJECT: GCP project ID (auto-detected on Cloud Run)
    """
    
    if os.environ.get('USE_GCLOUD_LOGGING', '0') != '1':
        return logging.NullHandler()
    
    # Import Google Cloud packages only when Cloud Logging is enabled
    # This ensures dev/CI/test environments never import these packages
    try:
        from google.cloud.logging import Client as CloudLoggingClient
        from google.cloud.logging.handlers import CloudLoggingHandler
        from testbed.core.utils.logging_filters import CloudRunTraceFilter
        
        client = CloudLoggingClient()
        
        cloud_logging_handler = CloudLoggingHandler(
            client,
            name="testbed"
        )
        
        cloud_logging_handler.addFilter(CloudRunTraceFilter())
        
        return cloud_logging_handler
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Failed to initialize Cloud Logging: {e}. "
            "Falling back to NullHandler. Logs will not appear in Cloud Logging."
        )
        return logging.NullHandler()
