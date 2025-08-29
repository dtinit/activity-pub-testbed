# LOLA Rate Limiting Implementation Guide

## Overview

This document provides a comprehensive guide to the rate limiting system implemented in the ActivityPub LOLA testbed. The rate limiting middleware ensures LOLA specification compliance while protecting OAuth and API endpoints from abuse.

**LOLA Compliance**: Per LOLA specification: *"The source server MAY rate limit requests by sending a 429 Too Many Requests response as defined in RFC6585, with a Retry-After header."*

## Table of Contents

1. [LOLA Specification Requirements](#lola-specification-requirements)
2. [Implementation Architecture](#implementation-architecture)
3. [Rate Limit Configuration](#rate-limit-configuration)
4. [Request Processing Flow](#request-processing-flow)
5. [Real-World Usage Scenarios](#real-world-usage-scenarios)
6. [Development Testing](#development-testing)
7. [Production Readiness Assessment](#production-readiness-assessment)
8. [Federation Compatibility](#federation-compatibility)
9. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)

---

## LOLA Specification Requirements

### RFC6585 Compliance

Our implementation strictly follows [RFC6585 - Additional HTTP Status Codes](https://tools.ietf.org/html/rfc6585) for 429 responses:

- **Status Code 429**: "Too Many Requests"
- **Retry-After Header**: Specifies when client may retry (in seconds)
- **Response Body**: Human-readable explanation

### ActivityPub Federation Requirements

Rate limiting is crucial for LOLA source servers because:

1. **External Server Protection**: Destination servers implementing LOLA need reliable source servers
2. **OAuth Endpoint Security**: OAuth authorization is critical for account portability workflows  
3. **Service Availability**: Prevents individual clients from impacting legitimate LOLA operations
4. **Specification Compliance**: Enables real-world LOLA implementations to test against standards-compliant infrastructure

### LOLA-Specific Considerations

- **Account Migration Workflows**: OAuth endpoints get stricter limits due to sensitivity
- **Federation Compatibility**: CORS headers enable destination servers to handle rate limits gracefully
- **Educational Balance**: Limits are strict enough for protection but permissive enough for learning

---

## Implementation Architecture

### Sliding Window Algorithm

The rate limiting uses a **sliding time window** approach that tracks request timestamps per client IP:

```python
# Example for IP 203.0.113.42 with 5-minute window
request_timestamps = [
    1693315800,  # 14:30:00
    1693315815,  # 14:30:15  
    1693315930,  # 14:32:10
    1693316025   # 14:33:45
]

# At 14:34:02, window is 14:29:02 to 14:34:02
# All 4 requests are within window
```

**Algorithm Benefits:**
- **Fair Distribution**: Allows bursts but prevents sustained abuse
- **Automatic Recovery**: Old requests automatically expire from window
- **Memory Efficient**: Only stores timestamps, not full request data

### In-Memory Storage Design

**Data Structure:**
```python
# Collections.defaultdict(list) stores IP -> timestamp list
request_counts = {
    '203.0.113.42': [1693315800, 1693315815, 1693315930],
    '198.51.100.10': [1693316000, 1693316050],
    # ... more IPs
}
```

**Storage Characteristics:**
- **Temporary**: Lost on server restart (acceptable for basic production)
- **Per-Server**: Each application instance has separate counters
- **Bounded**: Automatic cleanup prevents unlimited growth
- **Fast**: In-memory access with O(1) IP lookup

### Client IP Detection

The middleware attempts to identify real client IPs through proxy headers:

```python
def get_client_ip(self, request):
    # Priority order for IP detection
    
    # 1. X-Forwarded-For (most common proxy header)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    
    # 2. X-Real-IP (alternative proxy header)  
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip
    
    # 3. Direct connection (fallback)
    return request.META.get('REMOTE_ADDR', '127.0.0.1')
```

**Production Considerations:**
- Configure proxy headers based on infrastructure
- Validate proxy sources to prevent header spoofing
- Consider subnet-based limiting for complex networks

### Memory Management and Cleanup

**Automatic Cleanup Process:**
- **Trigger**: Runs on every request
- **Age Limit**: Removes entries older than 1 hour
- **Scope**: Cleans both old timestamps and empty IP records
- **Performance**: O(n) where n = number of tracked IPs

```python
def cleanup_old_entries(self, current_time, max_age=3600):
    cutoff_time = current_time - max_age
    
    for ip in list(self.request_counts.keys()):
        # Remove old timestamps
        self.request_counts[ip] = [
            t for t in self.request_counts[ip] if t > cutoff_time
        ]
        
        # Remove empty IP records
        if not self.request_counts[ip]:
            del self.request_counts[ip]
```

---

## Rate Limit Configuration

### Endpoint-Specific Limits

The middleware applies different limits based on endpoint sensitivity:

| Endpoint | Requests | Window | Rationale |
|----------|----------|---------|-----------|
| `/oauth/authorize/` | 10 | 5 minutes | Critical for LOLA authentication |
| `/oauth/token/` | 20 | 5 minutes | Token exchange endpoint |  
| `/.well-known/oauth-authorization-server` | 30 | 1 minute | LOLA discovery |
| `/api/actors/` | 100 | 1 minute | LOLA collections |
| **Default** | 200 | 1 minute | General endpoints |

### Path-Based Matching Logic

The system uses **longest prefix matching** to find the most specific rate limit:

```python
def get_rate_limit_for_path(self, path):
    # Example: path = "/api/actors/123/followers"
    # Matches: "/api/actors/" (not "/api/" or "/")
    
    best_match = self.default_limit
    best_match_length = 0
    
    for pattern, limit in self.rate_limits.items():
        if path.startswith(pattern) and len(pattern) > best_match_length:
            best_match = limit
            best_match_length = len(pattern)
    
    return best_match
```

### Customization Options

**BasicRateLimitingMiddleware** (Development/Basic Production):
```python
rate_limits = {
    '/oauth/authorize/': {'requests': 10, 'window': 300},
    '/oauth/token/': {'requests': 20, 'window': 300},
    '/api/actors/': {'requests': 100, 'window': 60},
}
default_limit = {'requests': 200, 'window': 60}
```

**LOLARateLimitingMiddleware** (Strict Production):
```python
rate_limits = {
    '/oauth/authorize/': {'requests': 5, 'window': 300},    # Stricter
    '/oauth/token/': {'requests': 10, 'window': 300},       # Stricter
    '/api/actors/': {'requests': 50, 'window': 60},         # Stricter
}
default_limit = {'requests': 100, 'window': 60}  # More conservative
```

---

## Request Processing Flow

### Step-by-Step Processing

Every HTTP request goes through this detailed evaluation:

```
1. REQUEST INTERCEPTION
   ├── Middleware activates early in Django stack
   ├── Positioned after sessions, before CSRF
   └── Has access to session data for IP tracking

2. CLIENT IDENTIFICATION  
   ├── Extract IP from proxy headers or direct connection
   ├── Handle X-Forwarded-For, X-Real-IP scenarios
   └── Fallback to REMOTE_ADDR if needed

3. MEMORY CLEANUP
   ├── Remove timestamps older than 1 hour
   ├── Delete IPs with no recent activity
   └── Maintain bounded memory usage

4. RATE LIMIT EVALUATION
   ├── Find most specific rate limit for request path
   ├── Get request history for client IP
   ├── Filter to requests within time window
   ├── Count recent requests vs limit
   └── Calculate retry time if exceeded

5. DECISION & RESPONSE
   ├── If under limit: Record request, continue
   └── If over limit: Generate 429 response
```

### 429 Response Generation

When rate limits are exceeded, the middleware generates RFC6585-compliant responses:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: text/plain
Retry-After: 238
Access-Control-Allow-Origin: *
Access-Control-Expose-Headers: Retry-After

Rate limit exceeded. Try again in 238 seconds.
```

**Retry-After Calculation:**
```python
# Find when oldest request in window expires
oldest_request = min(recent_requests)
window_expires = oldest_request + rate_limit['window']
retry_after = max(window_expires - current_time, 1)  # At least 1 second
```

---

## Real-World Usage Scenarios

### Scenario: External ActivityPub Server Testing LOLA

**Background**: MastodonPlus.social is implementing LOLA account portability and testing their destination server against our testbed.

**Timeline with Real Requests:**

**14:30:00 - Developer starts OAuth testing**
```
Request 1: POST /oauth/authorize/ from 203.0.113.42
✅ ALLOWED (1/10 requests in window)
Response: 200 OK
Memory: ['14:30:00']
```

**14:30:15 to 14:33:45 - Rapid development testing**
```
Requests 2-10: POST /oauth/authorize/ from 203.0.113.42
✅ ALL ALLOWED (10/10 requests in window)
Memory: ['14:30:00', '14:30:15', ..., '14:33:45']
```

**14:34:02 - Rate limit triggered**
```
Request 11: POST /oauth/authorize/ from 203.0.113.42
❌ RATE LIMITED!

Calculation:
- Window: 14:29:02 to 14:34:02 (5 minutes)
- Recent requests: 10 (all within window)
- Limit: 10 per 5 minutes → EXCEEDED
- Oldest request: 14:30:00
- Retry after: (14:30:00 + 300) - 14:34:02 = 238 seconds

Response: HTTP 429 with Retry-After: 238
```

**14:38:05 - Automatic recovery**
```
Request 12: POST /oauth/authorize/ from 203.0.113.42
✅ ALLOWED!

Why? Sliding window moved:
- Window: 14:33:05 to 14:38:05
- Oldest request (14:30:00) expired from window
- Now only 9 requests in current window
```

### Memory State Evolution

**Before Rate Limit (14:34:02):**
```python
request_counts = {
    '203.0.113.42': [
        1693315800,  # 14:30:00
        1693315815,  # 14:30:15
        1693315882,  # 14:31:22  
        1693315930,  # 14:32:10
        1693315965,  # 14:32:45
        1693316000,  # 14:33:20
        1693316025,  # 14:33:45
        # ... 3 more timestamps ...
    ]
    # Total: 10 requests in memory
}
```

**After Rate Limit + Recovery (14:38:05):**
```python
request_counts = {
    '203.0.113.42': [
        # 14:30:00, 14:30:15 expired (outside window)
        1693315882,  # 14:31:22  
        1693315930,  # 14:32:10
        # ... remaining requests ...
        1693316285   # 14:38:05 (new allowed request)
    ]
    # Total: 9 requests (oldest expired naturally)
}
```

---

## Development Testing

### Method 1: Browser Testing (Easiest)

**OAuth Authorization Endpoint (10 requests/5 minutes):**

1. Start development server: `python manage.py runserver`
2. Navigate to OAuth URL:
   ```
   http://127.0.0.1:8000/oauth/authorize/?client_id=YOUR_CLIENT_ID&response_type=code&scope=activitypub_account_portability
   ```
3. **Rapid refresh test**: Press F5 or Ctrl+R rapidly 11+ times
4. **Expected result**: 11th request shows "Rate limit exceeded"

### Method 2: curl Command Testing (Most Reliable)

**Quick Rate Limit Test:**
```bash
# Test OAuth authorization endpoint
for i in {1..11}; do
  echo "Request $i:"
  curl -v http://127.0.0.1:8000/oauth/authorize/ 2>&1 | grep -E "(HTTP|Retry-After)"
  echo "---"
done
```

**Expected Output (11th request):**
```
Request 11:
< HTTP/1.1 429 Too Many Requests
< Retry-After: 287
< Access-Control-Allow-Origin: *
---
```

### Method 3: Python Test Script (Most Controlled)

```python
import requests
import time

def test_oauth_rate_limiting():
    # Test OAuth endpoint rate limiting with detailed output
    url = "http://127.0.0.1:8000/oauth/authorize/"
    
    print("Testing OAuth Rate Limiting (10 requests/5 minutes)")
    print("=" * 50)
    
    for i in range(1, 12):
        start_time = time.time()
        response = requests.get(url)
        end_time = time.time()
        
        print(f"Request {i:2d}: Status {response.status_code} "
              f"({end_time - start_time:.3f}s)")
        
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After', 'Not set')
            cors_origin = response.headers.get('Access-Control-Allow-Origin', 'Not set')
            
            print(f"  ⚠️  Rate Limited!")
            print(f"  📅 Retry-After: {retry_after} seconds") 
            print(f"  🌐 CORS Origin: {cors_origin}")
            print(f"  📝 Body: {response.text[:50]}...")
            break
        else:
            print(f"  ✅ Allowed")
            
        time.sleep(0.1)  # Small delay between requests

if __name__ == "__main__":
    test_oauth_rate_limiting()
```

### Method 4: Testing Different Endpoints

**Fastest to Trigger (Discovery - 30/minute):**
```bash
for i in {1..31}; do
  echo -n "Request $i: "
  curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/.well-known/oauth-authorization-server
  echo
done
```

**API Endpoints (100/minute):**
```bash
for i in {1..101}; do
  curl -s -o /dev/null -w "Request $i: %{http_code}\n" http://127.0.0.1:8000/api/actors/1/
done
```

## Production Readiness Assessment

### ✅ Production-Ready Aspects

**LOLA Specification Compliance:**
- RFC6585 compliant 429 responses
- Proper Retry-After header calculation  
- ActivityPub federation CORS support
- Standard HTTP semantics for automated clients

**Security Protection:**
- OAuth endpoint protection against brute force
- Resource conservation preventing server overload
- Graceful degradation with clear error messaging
- IP-based tracking prevents individual client abuse

**Operational Stability:**
- Automatic memory cleanup prevents leaks
- Reasonable limits balance protection with usability
- Basic proxy support for common nginx setups
- No external dependencies simplifying deployment

### Production Deployment Scenarios

**✅ Works Well For:**

**Single-Server Deployments:**
- Small to medium LOLA testbeds (< 1000 users)
- Educational/research instances  
- Single Django server behind nginx reverse proxy
- Community demonstration servers
- Docker containerized deployments (single instance)

**Moderate Traffic Volumes:**
- Hundreds of OAuth requests per hour
- Developer testing and integration scenarios  
- Community learning and experimentation
- Basic ActivityPub federation testing

**Simple Infrastructure:**
- nginx → Django application server
- Cloud Run single instance deployments
- Basic load balancer with session affinity
- Development/staging environments

### ⚠️ Current Limitations

**Multi-Server Challenges:**
- **Issue**: Each app server maintains separate rate limit counters
- **Impact**: Rate limiting becomes less effective with horizontal scaling
- **Workaround**: Use sticky sessions or single-server deployments
- **Future**: Upgrade to Redis storage for shared state

**Server Restart Behavior:**
- **Issue**: Rate limit memory cleared on application restart
- **Impact**: Brief period where all rate limits reset
- **Mitigation**: Usually not critical for basic production use
- **Future**: Persistent storage will maintain state

**Advanced IP Detection:**
- **Issue**: Basic proxy header parsing may not handle complex chains
- **Impact**: Could rate limit wrong IPs in edge cases
- **Mitigation**: Configure X-Forwarded-For properly for your proxy setup
- **Future**: Enhanced proxy validation and trusted proxy lists

### 🚀 When to Upgrade

**Consider advanced rate limiting when you reach:**
- **Multiple Application Servers**: Need shared rate limit state
- **High Traffic Volumes**: Thousands of requests per hour requiring optimization
- **Complex Proxy Infrastructure**: Multiple load balancers, CDN, cloud proxies
- **Enterprise Security**: Need IP whitelisting, progressive penalties
- **Detailed Monitoring**: Require metrics, alerts, dashboards

---

## Federation Compatibility

### CORS Headers for ActivityPub Clients

Our rate limiting includes ActivityPub-specific CORS headers:

```python
response['Access-Control-Allow-Origin'] = '*'
response['Access-Control-Expose-Headers'] = 'Retry-After'
```

**Why This Matters:**
- External ActivityPub servers can read rate limit headers from JavaScript
- Enables destination servers to implement proper backoff logic
- Follows web standards for cross-origin resource sharing

### Error Response Format

Our 429 responses follow standards that work with automated systems:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: text/plain
Retry-After: 180
Access-Control-Allow-Origin: *
Access-Control-Expose-Headers: Retry-After
Date: Thu, 29 Aug 2025 19:34:02 GMT

Rate limit exceeded. Try again in 180 seconds.
```

**Machine-Readable Elements:**
- **Status Code 429**: Universally recognized
- **Retry-After Header**: Precise retry timing
- **CORS Headers**: Enable browser-based clients
- **Plain Text Body**: Human-readable explanation

---

## Monitoring and Troubleshooting

### Log Messages and Levels

**Warning Level (Always Logged):**
```
WARNING Rate limit exceeded for IP 203.0.113.42 on /oauth/authorize/. Retry after 240 seconds.
```

**Info Level (LOLA-Specific Middleware):**
```
INFO LOLA rate limit triggered: IP=203.0.113.42, path=/oauth/authorize/, retry_after=240s
```

**Debug Level (Development Only):**
```
DEBUG Rate limit check: IP=127.0.0.1, path=/api/actors/1/, count=3/100, window=60s
```

### Common Issues and Solutions

**Issue: Rate limits too strict for development**
```python
# Solution: Use BasicRateLimitingMiddleware instead of LOLARateLimitingMiddleware
MIDDLEWARE = [
    # ...
    'testbed.core.middleware.rate_limiting.BasicRateLimitingMiddleware',
    # ...
]
```

**Issue: Rate limits not working after server restart**
```
# Expected behavior: In-memory storage is cleared on restart
# This is normal for current implementation
# Solution: Wait for limits to rebuild naturally, or upgrade to persistent storage
```

---

## Configuration Reference

### Middleware Setup

**settings/base.py:**
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # Position rate limiting early to protect all endpoints
    'testbed.core.middleware.rate_limiting.BasicRateLimitingMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    # ... rest of middleware stack
]
```

### Rate Limit Customization

**Custom Rate Limits:**
```python
# In middleware class
rate_limits = {
    '/oauth/authorize/': {'requests': 5, 'window': 300},  # 5 per 5 minutes
    '/oauth/token/': {'requests': 15, 'window': 300},     # 15 per 5 minutes  
    '/api/actors/': {'requests': 50, 'window': 60},       # 50 per minute
    '/.well-known/': {'requests': 20, 'window': 60},      # 20 per minute
}
```

## Conclusion

The LOLA rate limiting implementation provides a solid foundation for protecting ActivityPub OAuth infrastructure while maintaining LOLA specification compliance. It balances security, usability, and educational value, making it suitable for development, demonstration, and basic production deployments.

The middleware's design enables easy enhancement for more advanced production scenarios while providing immediate value for LOLA compliance and basic abuse protection.
