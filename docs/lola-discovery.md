# LOLA Discovery Implementation

This document covers the RFC8414-compliant OAuth Authorization Server Metadata endpoint that enables automatic LOLA discovery by destination servers.

## Table of Contents

- [Overview](#overview)
- [RFC8414 Compliance](#rfc8414-compliance)
- [Endpoint Implementation](#endpoint-implementation)
- [LOLA Extensions](#lola-extensions)
- [Discovery Flow](#discovery-flow)
- [Federation Requirements](#federation-requirements)
- [Usage Examples](#usage-examples)
- [Integration with LOLA](#integration-with-lola)

## Overview

The OAuth Authorization Server Metadata endpoint (`/.well-known/oauth-authorization-server`) enables automatic discovery of OAuth capabilities by federated servers. This is essential for LOLA account portability, allowing destination servers to discover:

- OAuth authorization and token endpoints
- Supported scopes (including `activitypub_account_portability`)
- Supported grant types and response types
- LOLA-specific portability endpoints

## RFC8414 Compliance

This implementation follows [RFC8414 - OAuth 2.0 Authorization Server Metadata](https://tools.ietf.org/rfc/rfc8414.txt) specification requirements.

### Endpoint Location

**URL**: `/.well-known/oauth-authorization-server`  
**Method**: `GET`  
**Content-Type**: `application/json`

The endpoint must be at the root level (not under `/api/`) for proper federation discovery.

### Required Metadata Fields

Per RFC8414, the following fields are included:

| Field | Description | Example |
|-------|-------------|---------|
| `issuer` | Authorization server identifier | `"https://server.example"` |
| `authorization_endpoint` | OAuth authorization URL | `"https://server.example/oauth/authorize/"` |
| `token_endpoint` | OAuth token exchange URL | `"https://server.example/oauth/token/"` |
| `scopes_supported` | Array of supported scopes | `["activitypub_account_portability"]` |
| `response_types_supported` | Supported response types | `["code"]` |
| `grant_types_supported` | Supported grant types | `["authorization_code"]` |

## Endpoint Implementation

### View Function

**Location**: `testbed/core/views.py` - `oauth_authorization_server_metadata()`  
**URL Routing**: `testbed/urls.py` (root level)

```python
@api_view(['GET'])
def oauth_authorization_server_metadata(request):
    """
    RFC8414-compliant OAuth Authorization Server Metadata endpoint for LOLA discovery.
    """
    # Build the base URL dynamically from the request
    scheme = request.scheme
    host = request.get_host()
    base_url = f"{scheme}://{host}"
    
    metadata = {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}{reverse('oauth2_provider:authorize')}",
        "token_endpoint": f"{base_url}{reverse('oauth2_provider:token')}",
        "scopes_supported": [
            "activitypub_account_portability"
        ],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        # LOLA-specific parameter
        "activitypub_account_portability": f"{base_url}{reverse('oauth2_provider:authorize')}"
    }
    
    response = JsonResponse(metadata)
    response['Access-Control-Allow-Origin'] = '*'  # Enable federation
    return response
```

### URL Configuration

The endpoint is configured at the root level in `testbed/urls.py`:

```python
from testbed.core.views import oauth_authorization_server_metadata

urlpatterns = [
    # LOLA Discovery: RFC8414-compliant OAuth Authorization Server Metadata
    path(
        ".well-known/oauth-authorization-server",
        oauth_authorization_server_metadata,
        name="oauth-server-metadata",
    ),
    # ... other patterns
]
```

## LOLA Extensions

Beyond RFC8414 requirements, this implementation includes LOLA-specific extensions:

### Additional Scope Support

The `activitypub_account_portability` scope is included in `scopes_supported`:

```json
{
  "scopes_supported": [
    "activitypub_account_portability"
  ]
}
```

### LOLA Endpoint Parameter

A custom parameter provides direct access to the LOLA authorization endpoint:

```json
{
  "activitypub_account_portability": "https://server.example/oauth/authorize/"
}
```

This enables destination servers to directly identify the LOLA portability endpoint.

## Discovery Flow

### 1. Destination Server Discovery

When a destination server needs to migrate an account from `source.example`:

```bash
curl https://source.example/.well-known/oauth-authorization-server
```

### 2. Discovery Response

```json
{
  "issuer": "https://source.example",
  "authorization_endpoint": "https://source.example/oauth/authorize/",
  "token_endpoint": "https://source.example/oauth/token/",
  "scopes_supported": [
    "activitypub_account_portability"
  ],
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code"],
  "activitypub_account_portability": "https://source.example/oauth/authorize/"
}
```

### 3. Capability Validation

The destination server can validate:
- ✅ LOLA scope is supported (`activitypub_account_portability` in `scopes_supported`)
- ✅ Authorization code flow is supported (`"code"` in `response_types_supported`)
- ✅ OAuth endpoints are available and absolute URLs

### 4. OAuth Flow Initiation

With discovered endpoints, the destination can initiate OAuth:

```python
# Use discovered authorization endpoint
auth_url = metadata['authorization_endpoint']
params = {
    'client_id': destination_client_id,
    'response_type': 'code', 
    'scope': 'activitypub_account_portability',
    'redirect_uri': destination_callback_url,
    'state': secure_random_state
}

redirect_url = f"{auth_url}?{urlencode(params)}"
```

## Federation Requirements

### Absolute URLs

All URLs in the metadata response are absolute, enabling cross-domain federation:

```json
{
  "issuer": "https://source.example",
  "authorization_endpoint": "https://source.example/oauth/authorize/",
  "token_endpoint": "https://source.example/oauth/token/"
}
```

### CORS Headers

The endpoint includes CORS headers for cross-origin federation requests:

```python
response['Access-Control-Allow-Origin'] = '*'
```

### Dynamic URL Generation

URLs are generated dynamically based on the request, supporting:
- Different schemes (HTTP/HTTPS)
- Various host configurations
- Development and production environments

```python
scheme = request.scheme  # 'http' or 'https'
host = request.get_host()  # 'localhost:8000' or 'api.example.com'
base_url = f"{scheme}://{host}"
```

## Usage Examples

### Discovery by Destination Server

```python
import requests

# Discover LOLA capabilities for a source server
def discover_lola_capabilities(source_domain):
    discovery_url = f"https://{source_domain}/.well-known/oauth-authorization-server"
    
    try:
        response = requests.get(discovery_url)
        response.raise_for_status()
        metadata = response.json()
        
        # Validate LOLA support
        if 'activitypub_account_portability' not in metadata.get('scopes_supported', []):
            return None, "Server doesn't support LOLA account portability"
        
        return metadata, None
        
    except requests.RequestException as e:
        return None, f"Discovery failed: {e}"

# Usage
metadata, error = discover_lola_capabilities('source.example')
if metadata:
    auth_endpoint = metadata['authorization_endpoint']
    token_endpoint = metadata['token_endpoint']
    # Proceed with OAuth flow...
```

### Testing Discovery Endpoint

```python
# Test RFC8414 compliance of discovery endpoint
def test_discovery_compliance():
    response = requests.get('https://server.example/.well-known/oauth-authorization-server')
    
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/json'
    
    metadata = response.json()
    
    # Required RFC8414 fields
    required_fields = [
        'issuer', 'authorization_endpoint', 'token_endpoint',
        'scopes_supported', 'response_types_supported', 'grant_types_supported'
    ]
    
    for field in required_fields:
        assert field in metadata, f"Missing required field: {field}"
    
    # LOLA-specific validations
    assert 'activitypub_account_portability' in metadata['scopes_supported']
    assert 'activitypub_account_portability' in metadata
    
    # URL format validations
    for url_field in ['issuer', 'authorization_endpoint', 'token_endpoint']:
        assert metadata[url_field].startswith('http'), f"{url_field} must be absolute URL"
```

### Manual Discovery Testing

```bash
# Test discovery endpoint
curl -H "Accept: application/json" \
     https://localhost:8000/.well-known/oauth-authorization-server

# Validate JSON structure
curl -s https://localhost:8000/.well-known/oauth-authorization-server | jq '.'

# Check LOLA scope support  
curl -s https://localhost:8000/.well-known/oauth-authorization-server | \
     jq '.scopes_supported | contains(["activitypub_account_portability"])'
```

## Integration with LOLA

### Actor-based Discovery (Alternative)

While this implementation focuses on RFC8414 discovery, LOLA also supports Actor-based discovery. Both methods can coexist:

**RFC8414 Discovery**: `/.well-known/oauth-authorization-server`
**Actor Discovery**: `accountPortabilityOauth` field in Actor objects

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Person",
  "id": "https://source.example/actors/1",
  "accountPortabilityOauth": "https://source.example/oauth/authorize/"
}
```

### Discovery Preference

Destination servers can use either method:
1. **RFC8414 first**: Standard OAuth discovery
2. **Actor fallback**: If `.well-known` is not available
3. **Validation**: Cross-reference both sources

### LOLA Workflow Integration

The discovery endpoint integrates into the complete LOLA workflow:

1. **Discovery** ← *This endpoint*
2. **Authentication** (OAuth flow using discovered endpoints)
3. **Collection Access** (Following/Followers collections)
4. **Content Migration** (Outbox and content collections)

### Security Considerations

- **Public endpoint**: No authentication required for discovery
- **CORS enabled**: Allows cross-origin federation requests  
- **No sensitive data**: Only public server capabilities exposed
- **Standard compliance**: Follows RFC8414 security guidelines

### Error Handling

The endpoint handles various scenarios gracefully:

```python
# Dynamic URL building handles different environments
try:
    base_url = f"{request.scheme}://{request.get_host()}"
    # Build metadata with base_url...
except Exception:
    # Fallback to configured base URL
    pass
```

### Performance Considerations

- **Lightweight response**: Small JSON payload
- **No database queries**: Metadata built from configuration
- **Cacheable**: Response suitable for HTTP caching
- **Fast response**: No external dependencies

---

## Related Documentation

- [LOLA Collections](lola-collections.md) - Following/Followers implementation
- [LOLA Authentication](lola-authentication.md) - OAuth flow and Actor discovery
- [LOLA Collections Testing](lola-collections-testing.md) - Test coverage for discovery endpoint

## References

- [RFC8414 - OAuth 2.0 Authorization Server Metadata](https://tools.ietf.org/rfc/rfc8414.txt)
- [LOLA Specification](https://swicg.github.io/activitypub-data-portability/lola.html)
- [ActivityPub Specification](https://www.w3.org/TR/activitypub/)
