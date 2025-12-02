"""
Logging filters for enriching log records with Cloud Run trace context and environment metadata.

Automatically extracts trace information from Cloud Run's X-Cloud-Trace-Context header
and adds it to all log records for correlation in Google Cloud Logging.

Reference: https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry
"""
import logging
import os
import contextvars


_trace_context_var = contextvars.ContextVar("trace_context", default=None)
_request_path_var = contextvars.ContextVar("request_path", default=None)
_request_method_var = contextvars.ContextVar("request_method", default=None)


def set_trace_context(trace_context, request_path=None, request_method=None):
    _trace_context_var.set(trace_context)
    _request_path_var.set(request_path)
    _request_method_var.set(request_method)


def get_trace_context():
    return _trace_context_var.get()


def clear_trace_context():
    _trace_context_var.set(None)
    _request_path_var.set(None)
    _request_method_var.set(None)


class CloudRunTraceFilter(logging.Filter):
    """
    Enrich log records with Cloud Run trace context and environment metadata.
    
    Automatically adds:
    - trace: projects/PROJECT_ID/traces/TRACE_ID (for Cloud Logging correlation)
    - spanId: Span ID from X-Cloud-Trace-Context
    - environment: ENVIRONMENT (staging/production)
    - service: K_SERVICE (Cloud Run service name)
    - revision: K_REVISION (Cloud Run revision name)
    - request_path: HTTP request path
    - request_method: HTTP request method
    """
    
    def __init__(self, name=""):
        
        super().__init__(name)
        self.project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'unknown')
        self.environment = os.environ.get('ENVIRONMENT', 'unknown')
        self.service = os.environ.get('K_SERVICE', 'unknown')
        self.revision = os.environ.get('K_REVISION', 'unknown')
    
    def filter(self, record):
        if self.environment:
            record.environment = self.environment
        if self.service:
            record.service = self.service
        if self.revision:
            record.revision = self.revision
        
        # Add trace correlation if trace header present
        trace_context = _trace_context_var.get()
        if trace_context and self.project_id:
            try:
                # Parse X-Cloud-Trace-Context: TRACE_ID/SPAN_ID;o=1
                # https://docs.cloud.google.com/trace/docs/trace-context
                x_cloud_trace_context_parts = trace_context.split(";")[0].split("/")
                if len(x_cloud_trace_context_parts) >= 1:
                    trace_id = x_cloud_trace_context_parts[0]
                    if trace_id:
                        record.trace = f"projects/{self.project_id}/traces/{trace_id}"
                    
                    if len(x_cloud_trace_context_parts) >= 2:
                        span_id = x_cloud_trace_context_parts[1]
                        if span_id:
                            record.spanId = span_id
            except Exception:
                pass
        
        request_path = _request_path_var.get()
        request_method = _request_method_var.get()
        if request_path:
            record.request_path = request_path
        if request_method:
            record.request_method = request_method
        
        return True
