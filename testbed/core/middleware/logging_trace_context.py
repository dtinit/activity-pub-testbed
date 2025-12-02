"""
Middleware for extracting Cloud Run trace context and request metadata.

Reads and extract X-Cloud-Trace-Context header from Cloud Run at request start
and stores it in contextvars so CloudRunTraceFilter can add trace correlation to log records.
Lastly, clears the context at request end (response or exception).

GCP DOC: https://docs.cloud.google.com/trace/docs/trace-context
Format: TRACE_ID/SPAN_ID;o=TRACE_ENABLED
"""
from django.utils.deprecation import MiddlewareMixin
from testbed.core.utils.logging_filters import set_trace_context, clear_trace_context


class LoggingTraceContextMiddleware(MiddlewareMixin):
    
    X_CLOUD_HEADER_NAME = "HTTP_X_CLOUD_TRACE_CONTEXT"
    
    def process_request(self, request):
        
        trace_header = request.META.get(self.X_CLOUD_HEADER_NAME)
        
        set_trace_context(
            trace_header,
            request_path=request.path,
            request_method=request.method,
        )
    
    def process_response(self, request, response):
        clear_trace_context()
        return response
    
    def process_exception(self, request, exception):
        clear_trace_context()
        return None
