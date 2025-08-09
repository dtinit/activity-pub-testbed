# **Phase 5: Protected Resource Access**

![Phase 5](../images/phase-5-protected-resource-access.png)

## Overview

Phase 5 represents the culmination of the OAuth 2.0 authorization flow, where the **Destination Service** uses the access token obtained in Phase 4 to securely access protected ActivityPub resources from the **Source Service**. This phase enables the actual data transfer that is the core purpose of LOLA account portability.

In our implementation, Phase 5 introduces a unique **dual-mode authentication system** that allows the same API endpoints to serve both standard ActivityPub federation (unauthenticated) and enhanced LOLA portability data (authenticated with proper OAuth scope). This approach maintains backward compatibility while providing enriched data for authorized account transfers.

## Objectives of Phase 5

- Enable secure access to protected ActivityPub resources using OAuth 2.0 access tokens.
- Provide **dual-mode operation** where the same endpoints serve different data based on authentication status.
- Implement **graceful degradation** that doesn't break standard ActivityPub federation when OAuth fails.
- Deliver **enhanced LOLA data** (private activities, portability endpoints) only to properly authenticated requests.
- Ensure **scope validation** so that only tokens with `activitypub_account_portability` scope unlock enhanced features.
- Maintain full **ActivityPub specification compliance** for both authenticated and unauthenticated requests.

## Context in the LOLA Flow

Within the LOLA portability process, Phase 5 is where the actual data retrieval occurs:

- The **Destination Service** presents the access token to request user data from the Source Service.
- The **Source Service** validates the token and scope, then provides either basic ActivityPub data or enhanced LOLA data.
- Enhanced data includes **private activities**, **LOLA discovery endpoints**, and **account portability metadata**.
- The retrieved data is in **JSON-LD format**, ready for account recreation at the destination.

This phase transforms the authorization (Phases 1-4) into actual data access, enabling the Destination Service to begin reconstructing the user's account with complete fidelity.

## Core Components

### 1. OptionalOAuth2Authentication

Our custom authentication class enables dual-mode operation:

```python
class OptionalOAuth2Authentication(OAuth2Authentication):
    """
    Authentication class that makes OAuth2 authentication optional.
    
    This class allows API endpoints to function in two distinct modes:
    1. Unauthenticated Mode: For standard ActivityPub federation
    2. Authenticated Mode: For LOLA account portability with proper OAuth scope
    """
    
    LOLA_PORTABILITY_SCOPE = 'activitypub_account_portability'
```

**Key Features:**
- **Graceful Degradation:** Authentication failures don't cause API errors; requests continue as unauthenticated
- **Scope Validation:** Only tokens with `activitypub_account_portability` scope unlock LOLA features
- **Request Flags:** Adds `is_oauth_authenticated` and `has_portability_scope` flags to request objects
- **Flexible Authentication:** Supports both Authorization header and URL parameter authentication

### 2. Protected Endpoints

Two primary endpoints provide OAuth-protected access:

#### **Actor Detail Endpoint**
- **URL:** `/api/actors/<int:pk>/`
- **Unauthenticated:** Returns basic ActivityPub Person object
- **Authenticated with Portability Scope:** Adds LOLA discovery fields

#### **Portability Outbox Endpoint**
- **URL:** `/api/actors/<int:pk>/outbox/`  
- **Unauthenticated:** Returns public activities only
- **Authenticated with Portability Scope:** Returns ALL activities (public + private)

### 3. Authentication Context System

The authentication system creates context flags that JSON-LD builders use for conditional data enhancement:

```python
# Set by OptionalOAuth2Authentication
request.is_oauth_authenticated = True/False
request.has_portability_scope = True/False

# Used by JSON-LD builders
auth_context = {
    'is_authenticated': getattr(request, 'is_oauth_authenticated', False),
    'has_portability_scope': getattr(request, 'has_portability_scope', False),
    'request': request
}
```

### 4. Enhanced Data Features

#### **Actor Enhancements (LOLA Fields)**
When authenticated with portability scope, actor objects include:

```json
{
    "accountPortabilityOauth": "https://source.example.com/oauth/authorize/",
    "content": "https://source.example.com/api/actors/1/content",
    "blocked": "https://source.example.com/api/actors/1/blocked", 
    "migration": "https://source.example.com/api/actors/1/outbox"
}
```

#### Outbox Content Filtering
- **Unauthenticated:** Only public activities (`visibility: "public"`)
- **Authenticated:** All activities including private, followers-only, etc.

## Implementation Details

### Token Authentication Process

1. **Authorization Header Authentication** (Primary):
   ```http
   GET /api/actors/1/ HTTP/1.1
   Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
   Accept: application/activity+json
   ```

2. **URL Parameter Authentication** (Testing):
   ```http
   GET /api/actors/1/?auth_token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

### Authentication Flow

```python
def authenticate(self, request):
    # Initialize authentication flags
    request.is_oauth_authenticated = False
    request.has_portability_scope = False
    
    try:
        # Try Authorization header first
        result = super().authenticate(request)
        
        # Fallback to URL parameter for testing
        if result is None:
            result = self._authenticate_with_url_token(request)
        
        if result is not None:
            user, token = result
            request.is_oauth_authenticated = True
            
            # Check for LOLA portability scope
            if self._has_portability_scope(token):
                request.has_portability_scope = True
            
            return user, token
            
    except exceptions.AuthenticationFailed:
        # Continue as unauthenticated - this is the key difference
        pass
    
    return None  # Allow unauthenticated requests
```

### JSON-LD Building with Authentication Context

```python
def build_actor_json_ld(actor, auth_context=None):
    # Base ActivityPub Actor (always included)
    actor_data = {
        "@context": build_actor_context(),
        "type": "Person", 
        "id": build_actor_id(actor.id),
        "preferredUsername": actor.username,
        # Standard ActivityPub collections
        "outbox": f"{build_actor_id(actor.id)}/outbox",
        # ...
    }
    
    # Add LOLA fields ONLY when authenticated with portability scope
    if auth_context and auth_context.get('has_portability_scope'):
        actor_data["accountPortabilityOauth"] = build_oauth_endpoint_url(auth_context['request'])
        actor_data["content"] = f"{build_actor_id(actor.id)}/content"
        actor_data["blocked"] = f"{build_actor_id(actor.id)}/blocked"
        actor_data["migration"] = f"{build_actor_id(actor.id)}/outbox"
    
    return actor_data
```

### Activity Filtering Logic

```python
def build_outbox_json_ld(outbox, auth_context=None):
    all_activities = create_activities + like_activities + follow_activities
    
    # Filter content based on authentication and scope
    if not auth_context or not auth_context.get('has_portability_scope'):
        # Public only for unauthenticated requests
        all_activities = [activity for activity in all_activities 
                         if activity.visibility == 'public']
    # LOLA authenticated requests get ALL activities
    
    return {
        "@context": build_basic_context(),
        "type": "OrderedCollection",
        "totalItems": len(all_activities),
        "items": [build_activity_json_ld(activity) for activity in all_activities]
    }
```

## Security Considerations

- **Token Validation:** Every request validates the access token against the database and checks expiration
- **Scope Enforcement:** Enhanced LOLA data is only provided when the token explicitly includes `activitypub_account_portability` scope
- **Graceful Degradation:** Invalid tokens don't cause service failures, maintaining ActivityPub federation compatibility
- **Content-Type Validation:** Responses use proper `application/activity+json` content-type for ActivityPub compliance
- **CORS Headers:** `Access-Control-Allow-Origin: *` enables cross-origin federation while maintaining security through authentication

## API Response Examples

### **Unauthenticated Actor Request**
```json
{
    "@context": ["https://www.w3.org/ns/activitystreams"],
    "type": "Person",
    "id": "https://source.example.com/api/actors/1/",
    "preferredUsername": "testuser",
    "name": "testuser",
    "inbox": "https://source.example.com/api/actors/1/inbox",
    "outbox": "https://source.example.com/api/actors/1/outbox",
    "followers": "https://source.example.com/api/actors/1/followers",
    "following": "https://source.example.com/api/actors/1/following"
}
```

### Authenticated Actor Request (with Portability Scope)
```json
{
    "@context": ["https://www.w3.org/ns/activitystreams"],
    "type": "Person",
    "id": "https://source.example.com/api/actors/1/",
    "preferredUsername": "testuser",
    "name": "testuser",
    "inbox": "https://source.example.com/api/actors/1/inbox",
    "outbox": "https://source.example.com/api/actors/1/outbox",
    "followers": "https://source.example.com/api/actors/1/followers",
    "following": "https://source.example.com/api/actors/1/following",
    "accountPortabilityOauth": "https://source.example.com/oauth/authorize/",
    "content": "https://source.example.com/api/actors/1/content",
    "blocked": "https://source.example.com/api/actors/1/blocked",
    "migration": "https://source.example.com/api/actors/1/outbox"
}
```

## User Experience Flow

1. **Destination Service Preparation:** Uses access token from Phase 4 in API requests
2. **API Request:** Includes `Authorization: Bearer <token>` header in HTTP requests
3. **Token Validation:** Source Service validates token and checks for portability scope
4. **Data Enhancement:** If valid scope, JSON-LD response includes LOLA-specific fields
5. **Data Retrieval:** Destination Service receives complete user data for account recreation
6. **Comparison Testing:** Same endpoints serve different data based on authentication status

## Testing Capabilities

Our implementation includes comprehensive testing features:

- **URL Parameter Authentication:** `?auth_token=<token>` for easy browser-based testing
- **Side-by-side Comparison:** Same endpoint with/without authentication shows data differences
- **Scope Validation Testing:** Tokens without portability scope behave like unauthenticated requests
- **DRF Browsable API:** Web interface for testing with proper content-type handling

## Future Enhancements

- **Rate Limiting:** Implement per-token rate limiting to prevent abuse
- **Detailed Activity Streams:** Add pagination support for large outboxes
- **Additional LOLA Endpoints:** Implement `/content`, `/blocked`, and other discovery endpoints
- **Caching:** Add token validation caching to improve performance
- **Enhanced Logging:** Add detailed access logging for security auditing

## Significance of Phase 5

Phase 5 completes the OAuth 2.0 flow and enables the core LOLA functionality:

- **Unified API Design:** Same endpoints serve both ActivityPub federation and LOLA portability
- **Backward Compatibility:** Standard ActivityPub clients continue to work unchanged  
- **Enhanced Data Access:** Authorized clients receive complete account data including private content
- **Secure Token Usage:** Proper scope validation ensures only authorized access to sensitive data
- **JSON-LD Compliance:** All responses conform to ActivityPub and LOLA specifications

With Phase 5 complete, the OAuth implementation provides a secure, standards-compliant foundation for ActivityPub account portability that maintains full compatibility with existing federation while enabling enhanced data access for authorized account transfers.
