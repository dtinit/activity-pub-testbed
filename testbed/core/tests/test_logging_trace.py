import os
import logging
from unittest.mock import patch, Mock
import pytest
from django.test import RequestFactory
from testbed.core.utils.logging_filters import (
    CloudRunTraceFilter,
    set_trace_context,
    clear_trace_context,
)
from testbed.core.middleware.logging_trace_context import LoggingTraceContextMiddleware


@pytest.fixture
def mock_environ():
    return {
        'GOOGLE_CLOUD_PROJECT': 'testbed-project',
        'ENVIRONMENT': 'test-env',
        'K_SERVICE': 'testbed-service',
        'K_REVISION': 'testbed-rev-001'
    }

@pytest.fixture
def log_record():
    return logging.LogRecord('test', logging.INFO, 'test.py', 1, 'test', (), None)

@pytest.fixture
def request_factory():
    return RequestFactory()

@pytest.fixture(autouse=True)
def cleanup_context():
    yield
    clear_trace_context()

# Tests CloudRunTraceFilter and LoggingTraceContextMiddleware

# Filter should parse X-Cloud-Trace-Context and add trace/spanId fields
def test_filter_adds_trace_correlation(mock_environ, log_record):
    with patch.dict(os.environ, mock_environ):
        filter_instance = CloudRunTraceFilter()
        set_trace_context('abc123/7890;o=1', '/callback', 'GET')
        
        filter_instance.filter(log_record)
        
        assert log_record.trace == 'projects/testbed-project/traces/abc123'
        assert log_record.spanId == '7890'
        assert log_record.request_path == '/callback'
        assert log_record.request_method == 'GET'

# Filter should add environment, service, and revision as searchable labels
def test_filter_adds_environment_labels(mock_environ, log_record):
    with patch.dict(os.environ, mock_environ):
        filter_instance = CloudRunTraceFilter()
        filter_instance.filter(log_record)
        
        assert log_record.environment == 'test-env'
        assert log_record.service == 'testbed-service'
        assert log_record.revision == 'testbed-rev-001'

# Filter should work when no trace context is set (e.g., local development)
def test_filter_handles_missing_trace(log_record):
    with patch.dict(os.environ, {'ENVIRONMENT': 'test-env'}):
        filter_instance = CloudRunTraceFilter()
        clear_trace_context()
        
        result = filter_instance.filter(log_record)
        
        assert result is True
        assert not hasattr(log_record, 'trace')

# Middleware should extract X-Cloud-Trace-Context from request headers
def test_middleware_extracts_trace_header(request_factory):    
    middleware = LoggingTraceContextMiddleware(lambda r: None)
    request = request_factory.post(
        '/api/actors/1',
        HTTP_X_CLOUD_TRACE_CONTEXT='trace123/span456;o=1'
    )
    
    middleware.process_request(request)

# Middleware should clear context after response to prevent leakage
def test_middleware_clears_context_on_response():
    middleware = LoggingTraceContextMiddleware(lambda r: None)
    request = Mock()
    response = Mock()
    
    result = middleware.process_response(request, response)
    
    assert result == response

# Middleware should clear context on exception to prevent leakage
def test_middleware_clears_context_on_exception():    
    middleware = LoggingTraceContextMiddleware(lambda r: None)
    request = Mock()
    exception = Exception("Test")
    
    result = middleware.process_exception(request, exception)
    
    assert result is None
