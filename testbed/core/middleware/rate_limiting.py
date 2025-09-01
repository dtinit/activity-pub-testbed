"""
Rate limiting middleware for LOLA compliance.

Per LOLA specification: "The source server MAY rate limit requests by sending 
a 429 Too Many Requests response as defined in RFC6585, with a Retry-After header."

This middleware implements basic rate limiting for OAuth endpoints to ensure
production-ready behavior for real-world LOLA account portability usage.
"""

import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.conf import settings

logger = logging.getLogger(__name__)

class BasicRateLimitingMiddleware:
    """
    Simple in-memory rate limiting middleware for LOLA OAuth endpoints.
    
    This middleware tracks request rates per IP address and returns RFC6585-compliant
    429 responses with Retry-After headers when rate limits are exceeded.
    
    Focuses on OAuth authorization endpoints which are most critical for LOLA
    account portability operations.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # In-memory storage for rate limiting (production would use database)
        self.request_counts = defaultdict(list)  # IP -> list of request timestamps
        
        # Rate limiting configuration
        # OAuth endpoints get stricter limits since they're more sensitive
        self.rate_limits = {
            # OAuth authorization endpoint (most critical for LOLA)
            '/oauth/authorize/': {'requests': 10, 'window': 300},  # 10 requests per 5 minutes
            '/oauth/token/': {'requests': 20, 'window': 300},      # 20 requests per 5 minutes
            
            # LOLA discovery endpoints
            '/.well-known/oauth-authorization-server': {'requests': 30, 'window': 60},  # 30 per minute
            
            # LOLA collection endpoints (less strict, but still limited)
            '/api/actors/': {'requests': 100, 'window': 60},       # 100 requests per minute
        }
        
        # Default rate limit for other endpoints
        self.default_limit = {'requests': 200, 'window': 60}  # 200 requests per minute
    
    def __call__(self, request):
        # Check if this request should be rate limited
        client_ip = self.get_client_ip(request)
        current_time = time.time()
        
        # Clean up old entries to prevent memory bloat
        self.cleanup_old_entries(current_time)
        
        # Check rate limit for this request
        rate_limit_result = self.check_rate_limit(request, client_ip, current_time)
        
        if rate_limit_result['exceeded']:
            # Return 429 Too Many Requests with Retry-After header
            retry_after = rate_limit_result['retry_after']
            
            logger.warning(
                f"Rate limit exceeded for IP {client_ip} on {request.path}. "
                f"Retry after {retry_after} seconds."
            )
            
            response = HttpResponse(
                f"Rate limit exceeded. Try again in {retry_after} seconds.",
                status=429,
                content_type='text/plain'
            )
            response['Retry-After'] = str(retry_after)
            
            # Add CORS headers for ActivityPub federation compatibility
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Expose-Headers'] = 'Retry-After'
            
            return response
        
        # Record this request and continue
        self.request_counts[client_ip].append(current_time)
        
        response = self.get_response(request)
        return response
    
    def get_client_ip(self, request):
        """
        Get client IP address, handling proxy headers.
        
        In production, this should be configured based on our proxy setup.
        """
        # Check for forwarded IP (common with reverse proxies)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        # Check for real IP (some proxy configurations)
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        # Fallback to direct connection IP
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    def check_rate_limit(self, request, client_ip, current_time):
        """
        Check if the request should be rate limited.
        
        Returns dict with 'exceeded' boolean and 'retry_after' seconds.
        """
        # Find the most specific rate limit for this path
        rate_limit = self.get_rate_limit_for_path(request.path)
        
        # Get request timestamps for this IP
        request_times = self.request_counts[client_ip]
        
        # Filter to requests within the time window
        window_start = current_time - rate_limit['window']
        recent_requests = [t for t in request_times if t > window_start]
        
        # Check if limit is exceeded
        if len(recent_requests) >= rate_limit['requests']:
            # Calculate when the oldest request in the window will expire
            oldest_request = min(recent_requests)
            retry_after = int(oldest_request + rate_limit['window'] - current_time) + 1
            
            return {
                'exceeded': True,
                'retry_after': max(retry_after, 1)  # At least 1 second
            }
        
        return {'exceeded': False, 'retry_after': 0}
    
    def get_rate_limit_for_path(self, path):
        """
        Get the rate limit configuration for a specific path.
        
        Uses the most specific match (longest matching prefix).
        """
        best_match = self.default_limit
        best_match_length = 0
        
        for pattern, limit in self.rate_limits.items():
            if path.startswith(pattern) and len(pattern) > best_match_length:
                best_match = limit
                best_match_length = len(pattern)
        
        return best_match
    
    def cleanup_old_entries(self, current_time, max_age=3600):
        """
        Remove old entries to prevent memory bloat.
        
        Removes entries older than max_age seconds (default: 1 hour).
        """
        cutoff_time = current_time - max_age
        
        for ip in list(self.request_counts.keys()):
            # Filter out old entries
            self.request_counts[ip] = [
                t for t in self.request_counts[ip] if t > cutoff_time
            ]
            
            # Remove IP if no recent requests
            if not self.request_counts[ip]:
                del self.request_counts[ip]


class LOLARateLimitingMiddleware(BasicRateLimitingMiddleware):
    """
    LOLA-specific rate limiting middleware with enhanced configuration.
    
    This extends the basic rate limiting with LOLA-specific considerations:
    - More restrictive limits for OAuth endpoints
    - Special handling for LOLA discovery endpoints  
    - ActivityPub federation-friendly error responses
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        
        # Override with LOLA-specific rate limits
        self.rate_limits.update({
            # Very strict OAuth limits for production LOLA usage
            '/oauth/authorize/': {'requests': 5, 'window': 300},   # 5 requests per 5 minutes
            '/oauth/token/': {'requests': 10, 'window': 300},      # 10 requests per 5 minutes
            
            # LOLA discovery endpoints (moderate limits)
            '/.well-known/oauth-authorization-server': {'requests': 20, 'window': 60},
            
            # LOLA collection endpoints (per LOLA spec considerations)
            '/api/actors/': {'requests': 50, 'window': 60},        # 50 requests per minute
        })
        
        # More conservative default for LOLA production usage
        self.default_limit = {'requests': 100, 'window': 60}  # 100 requests per minute
    
    def check_rate_limit(self, request, client_ip, current_time):
        """
        Enhanced rate limit checking with LOLA-specific logic.
        """
        result = super().check_rate_limit(request, client_ip, current_time)
        
        # Log rate limiting events for LOLA monitoring
        if result['exceeded']:
            logger.info(
                f"LOLA rate limit triggered: IP={client_ip}, path={request.path}, "
                f"retry_after={result['retry_after']}s"
            )
        
        return result


# Configuration helper for settings.py
def get_rate_limiting_middleware():
    """
    Helper function to get the appropriate rate limiting middleware class.
    
    Can be used in settings.py to choose between basic and LOLA-specific middleware.
    """
    # Use LOLA-specific middleware if explicitly configured
    if getattr(settings, 'USE_LOLA_RATE_LIMITING', False):
        return 'testbed.core.middleware.rate_limiting.LOLARateLimitingMiddleware'
    else:
        return 'testbed.core.middleware.rate_limiting.BasicRateLimitingMiddleware'
