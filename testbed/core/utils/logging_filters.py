"""
Logging filters for enriching log records with Cloud Run trace context and environment metadata.

Automatically extracts trace information from Cloud Run's X-Cloud-Trace-Context header
and adds it to all log records for correlation in Google Cloud Logging.

Reference: https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry
"""
import logging
import os
import threading


# Thread-local storage for trace context
_trace_local = threading.local()


def set_trace_context(trace_context):
    # Store trace context for the current thread/request
    _trace_local.trace_context = trace_context


def get_trace_context():
    # Retrieve trace context for the current thread/request
    return getattr(_trace_local, 'trace_context', None)


def clear_trace_context():
    # Clear trace context for the current thread/request
    _trace_local.trace_context = None


class CloudRunTraceFilter(logging.Filter):
    """
    Enriches log records with Cloud Run trace context and environment metadata.
    
    Automatically adds:
    - trace: projects/PROJECT_ID/traces/TRACE_ID (for Cloud Logging correlation)
    - span_id: Span ID from X-Cloud-Trace-Context
    - environment: ENV_NAME (staging/production)
    - service: K_SERVICE (Cloud Run service name)
    - revision: K_REVISION (Cloud Run revision name)
    """
    
    def __init__(self, name=""):
        super().__init__(name)
        self.project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'unknown')
        self.environment = os.environ.get('ENV_NAME', 'unknown')
        self.service = os.environ.get('K_SERVICE', 'unknown')
        self.revision = os.environ.get('K_REVISION', 'unknown')
    
    def filter(self, record):
        # Add trace and environment context to log record
        # Add environment metadata
        record.environment = self.environment
        record.service = self.service
        record.revision = self.revision
        
        # Add trace context if available
        trace_context = get_trace_context()
        if trace_context:
            try:
                # Parse X-Cloud-Trace-Context: TRACE_ID/SPAN_ID;o=TRACE_TRUE
                # Convert to: projects/PROJECT_ID/traces/TRACE_ID
                parts = trace_context.split('/')
                if len(parts) >= 1:
                    trace_id = parts[0]
                    record.trace = f"projects/{self.project_id}/traces/{trace_id}"
                    
                    if len(parts) >= 2:
                        span_parts = parts[1].split(';')
                        if span_parts:
                            record.span_id = span_parts[0]
            except (IndexError, AttributeError):
                pass
        
        return True
