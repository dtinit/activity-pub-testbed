# LOLA Authentication Implementation

This document provides comprehensive documentation for the LOLA authentication system implemented in the ActivityPub testbed.

## Table of Contents

- [Overview](#overview)
- [OAuth Client Credentials Encryption System](#oauth-client-credentials-encryption-system)
- [OptionalOAuth2Authentication Class](#optionaloauth2authentication-class)
- [Enhanced API Endpoints](#enhanced-api-endpoints)
- [JSON-LD Builder System](#json-ld-builder-system)
- [JSON-LD Utilities](#json-ld-utilities)
- [Interactive Testing Interface](#interactive-testing-interface)
- [Test Coverage](#test-coverage)
- [Usage Examples](#usage-examples)
- [Security Considerations](#security-considerations)
- [LOLA Specification Compliance](#lola-specification-compliance)

## Overview

The LOLA authentication system enables ActivityPub servers to support account portability while maintaining compatibility with standard ActivityPub federation. The implementation provides:

- **Dual-mode operation**: Same endpoints serve both public ActivityPub data and enhanced LOLA data
- **OAuth 2.0 scope-based access control**: Uses `activitypub_account_portability` scope
- **Graceful degradation**: Unauthenticated requests receive standard ActivityPub responses
- **Privacy protection**: Private content only accessible with proper authentication
- **Developer-friendly testing**: Interactive tools for testing authentication flows

## OAuth Client Credentials Encryption System

A production-grade encrypted storage system that solves persistent "Token Exchange Failed" errors by replacing fragile session-based client secret storage with secure database storage.

### Purpose

The `OAuthClientCredentials` model provides encrypted database storage for OAuth application credentials, eliminating dependency on session lifecycle for critical authentication infrastructure.

### Problem Solved

**"Token Exchange Failed" Errors**: Previously, client secrets were stored in Django sessions, causing failures when sessions expired, browsers were closed, or servers restarted. This architectural misalignment stored permanent application credentials in temporary session storage.

### Implementation Details

**Location**: `testbed/core/models.py` - `OAuthClientCredentials` class

```python
class OAuthClientCredentials(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="oauth_credentials")
    encrypted_client_secret = models.TextField(
        help_text="Client secret encrypted with Fernet using Django SECRET_KEY"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Encryption Methods

**Fernet Symmetric Encryption**: Uses industry-standard Fernet encryption from the cryptography library with Django SECRET_KEY derivation:

```python
def _get_encryption_key(self):
    # Transform Django SECRET_KEY into valid Fernet key
    key_material = settings.SECRET_KEY.encode('utf-8')
    
    # Ensure exactly 32 bytes (Fernet requirement)
    if len(key_material) < 32:
        key_material = key_material.ljust(32, b'0')  # Pad with zeros
    else:
        key_material = key_material[:32]  # Use first 32 bytes
    
    return base64.urlsafe_b64encode(key_material)

def set_client_secret(self, raw_secret):
    f = Fernet(self._get_encryption_key())
    encrypted_bytes = f.encrypt(raw_secret.encode('utf-8'))
    self.encrypted_client_secret = encrypted_bytes.decode('utf-8')

def get_client_secret(self):
    f = Fernet(self._get_encryption_key())
    encrypted_bytes = self.encrypted_client_secret.encode('utf-8')
    return f.decrypt(encrypted_bytes).decode('utf-8')
```

### Security Features

- **Environment-Specific Encryption**: Each environment (development, CI, production) uses different SECRET_KEY, creating cryptographic isolation
- **Database-Level Security**: Client secrets remain encrypted even with database access
- **Automatic Migration**: Seamlessly transitions existing users from session to encrypted storage
- **OneToOne Relationship**: Each user gets exactly one secure credential storage

### Integration with OAuth Flow

The encrypted storage integrates seamlessly with existing OAuth utilities in `testbed/core/utils/oauth_utils.py`:

```python
def get_user_application(user, request=None):
    # Try to get client secret from encrypted storage
    try:
        credentials = OAuthClientCredentials.objects.get(user=user)
        application.raw_client_secret = credentials.get_client_secret()
    except OAuthClientCredentials.DoesNotExist:
        # Migration: Move from session to encrypted storage
        if request and CLIENT_SECRET_SESSION_KEY in request.session:
            client_secret = request.session[CLIENT_SECRET_SESSION_KEY]
            credentials = OAuthClientCredentials.objects.create(user=user)
            credentials.set_client_secret(client_secret)
            application.raw_client_secret = client_secret
```

## OptionalOAuth2Authentication Class

The core of the LOLA authentication system is the `OptionalOAuth2Authentication` class located in `testbed/core/utils/authentication.py`.

### Purpose

This authentication class enables endpoints to function in two distinct modes:
1. **Unauthenticated Mode**: Standard ActivityPub federation (public data only)
2. **Authenticated Mode**: LOLA account portability with enhanced data access

### Three-Tier Authentication Chain

The authentication system implements intelligent prioritization across three authentication methods:

**Tier 1: Authorization Header (Production)**
- Standard OAuth 2.0 RFC 6750 Bearer token authentication
- Used by external ActivityPub servers and production API clients
- Most explicit authentication method (highest priority)

**Tier 2: URL Parameter (Testing)**
- `?auth_token=TOKEN` parameter for development and testing convenience
- Enables simple HTML link-based testing without JavaScript
- Visible authentication method for debugging

**Tier 3: Session Storage (Demo Enhancement)**
- Automatic authentication using tokens stored in Django sessions
- Seamless demo experience after successful OAuth completion
- Implicit authentication method (lowest priority)

### Authentication Method Implementation

```python
def authenticate(self, request):
    # Initialize authentication flags
    request.is_oauth_authenticated = False
    request.has_portability_scope = False
    
    try:
        # Tier 1: Authorization header (production)
        result = super().authenticate(request)
        
        # Tier 2: URL parameter (testing)
        if result is None:
            result = self._authenticate_with_url_token(request)
        
        # Tier 3: Session storage (demo)
        if result is None:
            result = self._try_session_auth(request)
        
        # Process successful authentication
        if result is not None:
            user, token = result
            request.is_oauth_authenticated = True
            
            if self._has_portability_scope(token):
                request.has_portability_scope = True
            
            return user, token
            
    except exceptions.AuthenticationFailed:
        # Graceful degradation: continue as unauthenticated
        pass
    
    return None
```

### Key Features

- **Optional Authentication**: Unlike standard OAuth2Authentication, this doesn't fail requests without tokens
- **Scope Validation**: Checks for `activitypub_account_portability` scope
- **Multiple Auth Methods**: Supports header, URL parameter, and session authentication
- **Request Flag Setting**: Adds authentication status flags to request objects
- **Graceful Error Handling**: Invalid/expired tokens fall back to unauthenticated behavior

### Implementation Details

```python
class OptionalOAuth2Authentication(OAuth2Authentication):
    LOLA_PORTABILITY_SCOPE = 'activitypub_account_portability'
    
    def authenticate(self, request):
        # Initialize flags
        request.is_oauth_authenticated = False
        request.has_portability_scope = False
        
        # Try authentication, gracefully handle failures
        # Set flags based on results
        return result_or_none
```

### Request Flags

After authentication, the following flags are available on request objects:

- `request.is_oauth_authenticated` - Boolean indicating if OAuth authentication succeeded
- `request.has_portability_scope` - Boolean indicating if token has LOLA portability scope

### Authentication Methods

#### 1. Authorization Header (Production)
```http
GET /api/actors/1/ HTTP/1.1
Authorization: Bearer your-oauth-token-here
```

**Implementation**: Standard OAuth 2.0 RFC 6750 Bearer token authentication
**Use Cases**: External ActivityPub servers, production API clients, federation
**Priority**: Highest (Tier 1)

#### 2. URL Parameter (Testing)
```http
GET /api/actors/1/?auth_token=your-oauth-token-here HTTP/1.1
```

**Implementation**: `_authenticate_with_url_token()` method validates URL parameter against OAuth database
**Use Cases**: Development testing, debugging, educational demonstrations
**Priority**: Medium (Tier 2)

The URL parameter method enables simple `<a>` link testing in HTML templates without JavaScript.

#### 3. Session Storage (Demo Enhancement)
```http
GET /api/actors/1/ HTTP/1.1
Cookie: sessionid=abc123...
```

**Implementation**: `_try_session_auth()` method validates session-stored OAuth tokens
**Use Cases**: Seamless demo experience, community education, conference presentations
**Priority**: Lowest (Tier 3)

**Session Authentication Flow**:
1. User completes OAuth authorization and token exchange
2. Access token automatically stored in Django session via `store_token_in_session()`
3. Subsequent requests automatically authenticated via session without manual token handling
4. Template shows "🔐 Session Authentication Active" status

### Session Token Management

**Location**: `testbed/core/utils/oauth_utils.py`

#### Storage Functions

```python
def store_token_in_session(request, token_data):
    # Store OAuth token in session after successful exchange
    access_token = token_data.get('access_token')
    expires_in = token_data.get('expires_in', 3600)
    scope = token_data.get('scope', '')
    
    request.session[ACCESS_TOKEN_SESSION_KEY] = access_token
    request.session[TOKEN_EXPIRY_SESSION_KEY] = (datetime.now() + timedelta(seconds=expires_in)).timestamp()
    request.session[TOKEN_SCOPE_SESSION_KEY] = scope

def get_token_from_session(request):
    # Get valid OAuth token from session, None if expired or missing
    token = request.session.get(ACCESS_TOKEN_SESSION_KEY)
    if not token:
        return None
        
    # Check expiration
    expiry_timestamp = request.session.get(TOKEN_EXPIRY_SESSION_KEY)
    if expiry_timestamp and datetime.now().timestamp() > expiry_timestamp:
        clear_token_from_session(request)
        return None
    
    return token

def clear_token_from_session(request):
    # Clear OAuth token data from session 
    for key in [ACCESS_TOKEN_SESSION_KEY, TOKEN_EXPIRY_SESSION_KEY, TOKEN_SCOPE_SESSION_KEY]:
        request.session.pop(key, None)
```

#### Session Authentication Implementation

```python
def _try_session_auth(self, request):
    """
    Try to authenticate using token stored in session (demo enhancement).
    Supports 'public_only' parameter to disable session auth for comparison demos.
    """
    # Check if public_only parameter is set (for demo comparison)
    if request.GET.get('public_only'):
        return None
    
    # Get token from session (handles expiration checking)
    token_string = get_token_from_session(request)
    if not token_string:
        return None
        
    # Validate against OAuth database
    try:
        access_token = AccessToken.objects.select_related('user', 'application').get(
            token=token_string
        )
        
        if access_token.is_valid():
            return access_token.user, access_token
        else:
            clear_token_from_session(request)
            return None
            
    except AccessToken.DoesNotExist:
        clear_token_from_session(request)
        return None
```

### Public/Authenticated Comparison System

**public_only Parameter**: Enables demonstration comparisons between public and LOLA-authenticated responses:

```python
# Public response (bypasses session auth)
GET /api/actors/1/?public_only=true

# Authenticated response (uses session auth if available)  
GET /api/actors/1/
```

**Template Integration**:
```html
<!-- Authenticated links -->
<a href="/api/actors/{{ actor.pk }}/?format=json&auth_token={{ token }}" target="_blank">
  Details (with LOLA fields)
</a>

<!-- Public comparison links -->
<a href="/api/actors/{{ actor.pk }}/?format=json&public_only=true" target="_blank">
  Details (basic ActivityPub)
</a>
```

**Demonstration Value**: Users can see exactly what data is publicly available versus what requires LOLA scope authorization, demonstrating the privacy model effectively.

### Error Handling

The class handles various authentication scenarios across all three tiers:

**Authorization Header (Tier 1):**
- **Invalid tokens**: Continue as unauthenticated
- **Expired tokens**: Continue as unauthenticated  
- **Malformed headers**: Continue as unauthenticated

**URL Parameter (Tier 2):**
- **Invalid auth_token parameter**: Continue as unauthenticated
- **Missing token in database**: Continue as unauthenticated

**Session Storage (Tier 3):**
- **Expired session tokens**: Automatically cleared and continue as unauthenticated
- **Missing session data**: Continue as unauthenticated
- **public_only parameter**: Bypass session auth for comparison demos

**Scope Validation (All Tiers):**
- **Missing scope**: Authenticated but without portability access
- **Malformed scope**: Continue as unauthenticated

**Network and System Errors:**
- **Database connection errors**: Continue as unauthenticated
- **Network timeouts**: Continue as unauthenticated

## Enhanced API Endpoints

Two core ActivityPub endpoints have been enhanced with LOLA authentication support:

### 1. Actor Detail Endpoint

**Location**: `testbed/core/views.py` - `actor_detail()`  
**URL Pattern**: `/api/actors/{pk}/`

#### Authentication Behavior

| Authentication State | Response Content |
|---------------------|------------------|
| ❌ Unauthenticated | Basic ActivityPub Actor (no LOLA fields) |
| ✅ OAuth without portability scope | Basic ActivityPub Actor (no LOLA fields) |
| ✅ OAuth with portability scope | Enhanced Actor with LOLA discovery fields |

#### LOLA Fields Added (when authenticated with portability scope)

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://swicg.github.io/activitypub-data-portability/lola.jsonld"
  ],
  "type": "Person",
  "id": "https://example.com/actors/1",
  
  // Standard ActivityPub fields...
  
  // LOLA-specific fields (only with portability scope)
  "accountPortabilityOauth": "https://example.com/oauth/authorize/",
  "following": "https://example.com/actors/1/following",
  "followers": "https://example.com/actors/1/followers",
  "content": "https://example.com/actors/1/content",
  "blocked": "https://example.com/actors/1/blocked", 
  "migration": "https://example.com/actors/1/outbox"
}
```

### 2. LOLA Collections Endpoints

**Following Collection**: `testbed/core/views.py` - `following_collection()`  
**URL Pattern**: `/api/actors/{pk}/following`

**Followers Collection**: `testbed/core/views.py` - `followers_collection()`  
**URL Pattern**: `/api/actors/{pk}/followers`

#### Two-Tier Privacy Model

| Collection | Discovery | Access |
|------------|-----------|--------|
| Following | LOLA-gated | Public once discovered |
| Followers | LOLA-gated | LOLA-gated |

**Following Collection**: Public access once URL is discovered (follows ActivityPub standard)
**Followers Collection**: LOLA authentication required for both discovery and access (privacy-sensitive data)

#### Response Format

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "OrderedCollection", 
  "id": "https://example.com/actors/1/following",
  "totalItems": 42,
  "items": [
    // Local relationships: Full Actor objects
    {
      "type": "Person",
      "id": "https://example.com/actors/2",
      "preferredUsername": "localuser"
    },
    // Remote relationships: URL strings with cached data
    "https://remote.example/users/remoteuser"
  ]
}
```

### 3. Portability Outbox Endpoint

**Location**: `testbed/core/views.py` - `portability_outbox_detail()`  
**URL Pattern**: `/api/actors/{pk}/outbox`

#### Content Filtering by Authentication

| Authentication State | Activities Returned |
|---------------------|-------------------|
| ❌ Unauthenticated | Public activities only |
| ✅ OAuth without portability scope | Public activities only |
| ✅ OAuth with portability scope | ALL activities (public + private) |

#### Response Structure

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "OrderedCollection",
  "id": "https://example.com/actors/1/outbox",
  "totalItems": 15,  // Higher count for authenticated requests
  "items": [
    // Activity objects filtered by authentication level
  ]
}
```

### Implementation Pattern

Both endpoints follow a consistent pattern:

```python
@api_view(['GET'])
@authentication_classes([OptionalOAuth2Authentication])
def endpoint_view(request, pk):
    # Get model object
    obj = get_object_or_404(Model, pk=pk)
    
    # Create authentication context
    auth_context = {
        'is_authenticated': getattr(request, 'is_oauth_authenticated', False),
        'has_portability_scope': getattr(request, 'has_portability_scope', False),
        'request': request
    }
    
    # Build response with context
    data = build_json_ld(obj, auth_context)
    response = Response(data)
    
    # Set ActivityPub headers
    if request.accepted_renderer.format == 'json':
        response['Content-Type'] = 'application/activity+json'
        response['Access-Control-Allow-Origin'] = '*'
    
    return response
```

## JSON-LD Builder System

The JSON-LD builders in `testbed/core/json_ld_builders.py` have been enhanced to support authentication-based content generation.

### Authentication Context

All builders accept an optional `auth_context` parameter:

```python
auth_context = {
    'is_authenticated': boolean,      # OAuth authentication status
    'has_portability_scope': boolean, # LOLA portability scope status  
    'request': request_object         # HTTP request for URL building
}
```

### Enhanced Builders

#### 1. `build_actor_json_ld(actor, auth_context=None)`

**Purpose**: Build ActivityPub Actor with optional LOLA enhancements

**Behavior**:
- Always includes standard ActivityPub fields
- Conditionally adds LOLA fields when `has_portability_scope` is True
- Uses extended JSON-LD context for LOLA-enhanced responses

**Example Usage**:
```python
# Basic usage (public response)
actor_data = build_actor_json_ld(actor)

# Enhanced usage (LOLA response) 
auth_context = {
    'is_authenticated': True,
    'has_portability_scope': True,
    'request': request
}
actor_data = build_actor_json_ld(actor, auth_context)
```

#### 2. `build_outbox_json_ld(outbox, auth_context=None)`

**Purpose**: Build ActivityPub outbox with authentication-based content filtering

**Filtering Logic**:
```python
# Get all activities
all_activities = create_activities + like_activities + follow_activities

# Apply authentication-based filtering
if not auth_context or not auth_context.get('has_portability_scope'):
    # Public only for unauthenticated or non-LOLA requests
    all_activities = [a for a in all_activities if a.visibility == 'public']
# LOLA authenticated requests get ALL activities (public + private)
```

**Benefits**:
- **Complete migration support**: LOLA clients can access private content for full account portability
- **Privacy protection**: Non-LOLA clients only see public content
- **Performance**: Filtering happens at the database level where possible

### Activity Type Builders

Individual activity builders (`build_create_activity_json_ld`, `build_like_activity_json_ld`, `build_follow_activity_json_ld`) maintain consistent JSON-LD structure regardless of authentication status.

## JSON-LD Utilities

The `testbed/core/json_ld_utils.py` module provides foundational utilities for JSON-LD generation with LOLA support.

### JSON-LD Context Management

```python
class JsonLDContext:
    ACTIVITY_STREAM = "https://www.w3.org/ns/activitystreams"
    LOLA = "https://swicg.github.io/activitypub-data-portability/lola.jsonld"
```

### Context Builders

#### `build_basic_context()`
Returns standard ActivityStreams context for most responses:
```json
"@context": "https://www.w3.org/ns/activitystreams"
```

#### `build_actor_context()`  
Returns extended context for LOLA-enhanced Actor responses:
```json
"@context": [
  "https://www.w3.org/ns/activitystreams",
  "https://swicg.github.io/activitypub-data-portability/lola.jsonld"
]
```

### URL Builders

Consistent URL generation for ActivityPub resources:

```python
def build_actor_id(actor_id):
    return f"https://example.com/actors/{actor_id}"

def build_activity_id(activity_id):
    return f"https://example.com/activities/{activity_id}"

def build_note_id(note_id):
    return f"https://example.com/notes/{note_id}"

def build_outbox_id(actor_id):
    return f"https://example.com/actors/{actor_id}/outbox"
```

### OAuth Endpoint URL Building

For LOLA discovery, builds OAuth authorization endpoint URLs:

```python
def build_oauth_endpoint_url(request):
    scheme = request.scheme
    host = request.get_host()
    return f"{scheme}://{host}/oauth/authorize/"
```

This ensures LOLA discovery URLs match the current server's configuration.

## Interactive Testing Interface

The enhanced OAuth token exchange template (`testbed/core/templates/oauth_token_exchange.html`) provides a comprehensive testing interface for LOLA authentication.

### Features

#### 1. Token Exchange Results Display
- Shows successful token details (access token, scope, expiry)
- Provides detailed error explanations for common OAuth failures
- Includes troubleshooting guides for "invalid_client" and other errors

#### 2. Interactive LOLA Testing Links
When a token is successfully obtained, the interface provides direct HTML links for testing LOLA authentication using URL parameter authentication:

```html
<!-- LOLA-authenticated links -->
<a href="/api/actors/{{ source_actor.pk }}/?format=json&auth_token={{ token_response.access_token }}" target="_blank">
  Details (with LOLA fields)
</a>

<a href="/api/actors/{{ source_actor.pk }}/outbox?format=json&auth_token={{ token_response.access_token }}" target="_blank">
  Outbox (all activities)
</a>

<!-- Compare with public versions -->
<a href="/api/actors/{{ source_actor.pk }}/?format=json" target="_blank">
  Details (basic ActivityPub)
</a>

<a href="/api/actors/{{ source_actor.pk }}/outbox?format=json" target="_blank">
  Outbox (public only)
</a>
```

**Key Features:**
- Uses URL parameter authentication (`?auth_token=...`) for easy testing without JavaScript
- Provides side-by-side comparison between LOLA-authenticated and public responses
- Opens results in new tabs for easy comparison
- Works directly in any browser without additional tools

#### 3. Educational Content
- OAuth 2.0 flow explanation
- Security implementation notes  
- Common error scenarios and solutions
- Side-by-side comparison guidance

### Usage Scenarios

1. **OAuth Flow Testing**: Complete authorization code to access token exchange
2. **LOLA Discovery**: Test Actor responses with/without authentication
3. **Content Access**: Compare public vs private content in outboxes
4. **Error Handling**: Experience graceful degradation with invalid tokens
5. **Educational**: Learn OAuth 2.0 and LOLA implementation patterns

## Test Coverage

The implementation includes comprehensive test coverage across multiple test files in `testbed/core/tests/` using pytest and factory-based testing patterns.

### Test Structure

#### Core Test Files
- `test_api.py` - Complete LOLA authentication API testing with 12 authentication scenarios
- `test_models.py` - Model validation and business logic testing
- `test_json_ld_builders.py` - JSON-LD builder functionality testing
- `test_json_ld_utils.py` - JSON-LD utility function testing
- `test_activities.py` - Activity model and outbox integration testing
- `conftest.py` - Shared fixtures and helper functions

#### LOLA Authentication Test Categories

**1. Basic API Functionality (4 tests)**
- `test_actor_detail_api()` - Standard Actor endpoint functionality
- `test_outbox_api_for_source_actor()` - Standard outbox functionality  
- `test_actor_not_found()` - 404 error handling
- `test_outbox_not_found()` - 404 error handling

**2. Authentication States (3 tests)**
- `test_actor_detail_unauthenticated_returns_basic_activitypub()` - Public response validation
- `test_actor_detail_with_lola_scope_returns_enhanced_data()` - LOLA response validation
- `test_actor_detail_with_basic_token_returns_basic_data()` - Non-LOLA authenticated response

**3. Content Filtering (2 tests)**
- `test_outbox_content_filtering_by_authentication()` - Public vs private activity filtering
- `test_side_by_side_authentication_comparison()` - Direct comparison of response differences

**4. Error Handling (2 tests)**
- `test_invalid_token_graceful_degradation()` - Invalid token handling
- `test_malformed_authorization_header_handling()` - Malformed header tolerance with parameterized test cases

**5. Technical Implementation (2 tests)**
- `test_actor_detail_url_parameter_authentication()` - URL parameter authentication method
- `test_content_type_headers_set_correctly()` - HTTP header validation

### Test Fixtures and Factories

The test suite uses a factory-based approach with helper functions for creating isolated test data:

#### Core Fixtures (`conftest.py`)
```python
@pytest.fixture
def user():
    return UserOnlyFactory()

@pytest.fixture
def actor():
    user = UserOnlyFactory(username="fixture_test_user")
    return Actor.objects.create(
        user=user,
        username="fixture_test_actor_source",
        role=Actor.ROLE_SOURCE,
    )

@pytest.fixture
def populated_source_actor():
    source_actor = User.objects.create_user(
        username=f"populate_test_user_{random.randint(1000, 9999)}",
        email="populate_test@example.com",
        password="testpass123"
    ).actors.get(role=Actor.ROLE_SOURCE)
    
    populate_source_actor_outbox(
        source_actor=source_actor,
        num_notes=3,
        include_local_interactions=True
    )
    
    return source_actor
```

#### Helper Functions
```python
def create_isolated_actor(username_prefix, role=None):
    # Creates an actor without triggering signals for additional objects
    role = role or Actor.ROLE_SOURCE
    user = UserOnlyFactory(username=f"{username_prefix}_user")
    return Actor.objects.create(
        user=user,
        username=f"{username_prefix}_actor",
        role=role
    )

def create_isolated_remote_like(username_prefix="remote_like_test"):
    # Creates a LikeActivity for a remote object with an isolated actor
    actor = create_isolated_actor(username_prefix)
    return LikeActivityFactory(
        actor=actor,
        note=None,
        object_url=f"https://remote.example/notes/{random.randint(1000, 9999)}",
        object_data={"content": "Remote note content"},
        visibility="public"
    )
```

#### OAuth Token Factories
```python
# From factories.py
class AccessTokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AccessToken
    
    user = factory.SubFactory(UserOnlyFactory)
    application = factory.SubFactory(ApplicationFactory)
    scope = 'read write'
    
    @factory.trait
    def lola_scope(self):
        self.scope = 'activitypub_account_portability read write'
```

#### Test Class Structure (`test_api.py`)
```python
class TestLOLAAuthenticationAPI:
    LOLA_SCOPE = 'activitypub_account_portability read write'
    BASIC_SCOPE = 'read write'
    
    def assert_basic_activitypub_structure(self, data, actor):
        assert data["@context"] == build_actor_context()
        assert data["type"] == "Person"
        assert data["id"] == build_actor_id(actor.id)
        assert data["preferredUsername"] == actor.username
        
    def assert_has_lola_fields(self, data, actor):
        assert "accountPortabilityOauth" in data
        assert data["accountPortabilityOauth"].endswith("/oauth/authorize/")
        # ... additional LOLA field validations
    
    def get_authenticated_client(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')
        return client
```

### Test Validation Examples

#### Enhanced Response Validation
```python
def test_actor_detail_with_lola_scope_returns_enhanced_data(self, lola_token):
    # Setup and request...
    
    # Validate standard fields
    assert data["type"] == "Person"
    assert data["preferredUsername"] == actor.username
    
    # Validate LOLA-specific fields are present
    assert "accountPortabilityOauth" in data
    assert "content" in data
    assert "blocked" in data
    assert "migration" in data
    
    # Validate URL formats
    assert data["accountPortabilityOauth"].endswith("/oauth/authorize/")
    assert data["content"].endswith(f"/actors/{actor.id}/content")
```

#### Content Filtering Validation
```python
def test_outbox_content_filtering_by_authentication(self, lola_token):
    # Test public outbox
    public_response = client.get(outbox_url)
    public_count = public_response.data["totalItems"]
    
    # Test LOLA outbox  
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {lola_token.token}')
    lola_response = client.get(outbox_url)
    lola_count = lola_response.data["totalItems"]
    
    # LOLA should show >= public activities
    assert lola_count >= public_count
```

### Client Usage Examples

#### 1. Standard ActivityPub Client
```python
import requests

# No authentication needed for public data
response = requests.get('https://server.example/api/actors/1/')
actor_data = response.json()

# Standard ActivityPub fields available
print(actor_data['preferredUsername'])
print(actor_data['outbox'])  # Standard outbox URL
```

#### 2. LOLA Account Portability Client
```python
import requests

# First, obtain OAuth token with portability scope
token_response = requests.post('https://server.example/oauth/token/', {
    'grant_type': 'authorization_code',
    'code': authorization_code,
    'scope': 'activitypub_account_portability'
})
token = token_response.json()['access_token']

# Access enhanced Actor data
headers = {'Authorization': f'Bearer {token}'}
response = requests.get('https://server.example/api/actors/1/', headers=headers)
actor_data = response.json()

# LOLA-specific fields now available
print(actor_data['accountPortabilityOauth'])  # OAuth endpoint for discovery
print(actor_data['content'])                  # Content collection endpoint
print(actor_data['blocked'])                  # Blocked actors endpoint
print(actor_data['migration'])                # Migration outbox endpoint

# Access complete outbox (including private activities)
outbox_response = requests.get(
    'https://server.example/api/actors/1/outbox', 
    headers=headers
)
outbox_data = outbox_response.json()
print(f"Total activities (including private): {outbox_data['totalItems']}")
```

#### 3. Testing Authentication States
```python
def test_authentication_differences():
    base_url = 'https://server.example/api/actors/1/'
    
    # Public request
    public_response = requests.get(base_url)
    public_data = public_response.json()
    
    # LOLA authenticated request
    headers = {'Authorization': f'Bearer {lola_token}'}
    lola_response = requests.get(base_url, headers=headers)
    lola_data = lola_response.json()
    
    # Compare responses
    print("Public fields:", set(public_data.keys()))
    print("LOLA fields:", set(lola_data.keys()))
    print("LOLA-specific fields:", set(lola_data.keys()) - set(public_data.keys()))
```

## Security Considerations

### 1. OAuth 2.0 Implementation

**Strengths:**
- Uses industry-standard OAuth 2.0 with proper scope validation
- Supports both HTTP Basic Authentication and request body authentication
- Implements secure state parameter validation to prevent CSRF attacks
- Proper token expiration and validation

**Best Practices:**
```python
# Always validate scope before granting access
if not self._has_portability_scope(token):
    return None

# Use secure random state generation
state = secrets.token_urlsafe(32)

# Implement proper token storage and cleanup
if access_token.is_valid():
    return access_token.user, access_token
```

### 2. Content Access Control

**Privacy Protection:**
- Private activities only accessible with proper LOLA scope
- Graceful degradation prevents data leakage
- Clear separation between public and private content

**Implementation:**
```python
# Content filtering based on authentication
if not auth_context or not auth_context.get('has_portability_scope'):
    # Public only
    activities = [a for a in activities if a.visibility == 'public']
# LOLA authenticated gets all activities
```

### 3. Error Handling Security

**Prevents Information Disclosure:**
- Invalid tokens don't reveal error details to clients
- Authentication failures result in public responses, not errors
- Consistent response formats regardless of authentication status

**Safe Error Handling:**
```python
try:
    result = super().authenticate(request)
    # Process authentication...
except exceptions.AuthenticationFailed:
    # Don't expose authentication failure details
    # Just continue as unauthenticated
    pass
```

### 4. Session Management

**Production-Grade Credential Storage:**
- Client secrets stored in encrypted database using `OAuthClientCredentials` model
- Session storage used only for access tokens in demo workflows
- Environment-specific encryption with Django SECRET_KEY derivation
- Automatic migration from legacy session-based credential storage

**Session Token Security:**
- Access tokens stored temporarily in sessions for demo convenience
- Automatic expiration validation and cleanup
- Session isolation prevents cross-user token access
- Token refresh and cleanup handled by OAuth2 provider

### 5. CORS and Federation

**Headers Set:**
```python
response['Content-Type'] = 'application/activity+json'
response['Access-Control-Allow-Origin'] = '*'  # Federation support
```

**Security Balance:**
- Enables federation while maintaining authentication requirements
- CORS headers allow cross-origin ActivityPub requests
- Authentication still required for enhanced data

## LOLA Specification Compliance

This implementation complies with the LOLA specification across all major requirements:

### 1. Discovery and Authentication ✅

**Specification Requirement**: "Source server advertises an OAuth endpoint for authorizing account portability"

**Implementation**: 
- Actor objects include `accountPortabilityOauth` field when accessed with portability scope
- OAuth endpoint URL dynamically built based on current server configuration
- Proper `activitypub_account_portability` scope implementation
- State parameter validation for CSRF protection

**Note**: This implementation uses Actor-based discovery (via the `accountPortabilityOauth` field) rather than RFC8414 `.well-known` metadata endpoints. The LOLA specification supports both approaches.

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://swicg.github.io/activitypub-data-portability/lola.jsonld"
  ],
  "type": "Person",
  "accountPortabilityOauth": "https://example.com/oauth/authorize/"
}
```

### 2. Authorization Flow ✅

**Specification Requirement**: "Destination server initiates OAuth to gain user authorization and give the destination server a secure token"

**Implementation**:
- Standard OAuth 2.0 Authorization Code flow
- Support for both HTTP Basic Auth and request body client authentication
- Secure state parameter generation and validation
- Proper redirect URI validation
- Token expiration and refresh handling

```python
# OAuth flow initiation
params = {
    'client_id': application.client_id,
    'response_type': 'code',
    'scope': 'activitypub_account_portability',
    'redirect_uri': redirect_uri,
    'state': secure_random_state
}
```

### 3. Content Access and Filtering ✅

**Specification Requirement**: "Destination server can use the secure token and find the right endpoints to start fetching data"

**Implementation**:
- Authentication-based content filtering in outbox responses
- Private activities accessible only with portability scope
- Public activities always available for federation compatibility
- Activity type preservation (Create, Like, Follow)

```python
# Content filtering logic
if not auth_context or not auth_context.get('has_portability_scope'):
    # Public only for unauthenticated/non-LOLA requests
    activities = [a for a in activities if a.visibility == 'public']
# LOLA requests get ALL activities
```

### 4. Discovery Collections ✅

**Specification Requirement**: "Content can be copied from a new content collection endpoint"

**Implementation**:
- `content` endpoint URL provided in authenticated Actor responses
- `blocked` endpoint for block list access
- `migration` endpoint pointing to outbox for activity migration
- Following/followers collections maintained per ActivityPub spec

```json
{
  "content": "https://example.com/actors/1/content",
  "blocked": "https://example.com/actors/1/blocked",
  "migration": "https://example.com/actors/1/outbox"
}
```

### 5. Privacy and Security ✅

**Specification Requirement**: "Activities with extension-defined privacy or authorization properties MAY be requested and sent"

**Implementation**:
- Visibility-based access control (`public`, `private`, `followers-only`)
- OAuth scope validation prevents unauthorized access
- Graceful degradation maintains privacy for unauthenticated requests
- No data leakage through error messages

### 6. Backward Compatibility ✅

**Specification Requirement**: "This specification is compatible with and independent of the OAuth 2.0 Profile for the ActivityPub API specification"

**Implementation**:
- Standard ActivityPub clients work without modification
- LOLA enhancements are additive, not replacement
- Same endpoints serve both standard and enhanced data
- Content-Type headers maintain ActivityPub federation compatibility

## Key Implementation Decisions

### 1. **Optional Authentication Pattern**
Instead of requiring authentication, the system gracefully handles both authenticated and unauthenticated requests, enabling:
- Standard ActivityPub federation to continue working
- Progressive enhancement for LOLA-capable clients
- Backward compatibility with existing tools

### 2. **Scope-Based Access Control**
The `activitypub_account_portability` scope specifically gates access to:
- Enhanced Actor discovery fields
- Private activity content
- Account migration endpoints
- Block list information

### 3. **JSON-LD Context Extension**
LOLA-enhanced responses use extended JSON-LD context:
```json
"@context": [
  "https://www.w3.org/ns/activitystreams",
  "https://swicg.github.io/activitypub-data-portability/lola.jsonld"
]
```

This maintains semantic compatibility while adding LOLA-specific vocabularies.

### 4. **Performance Considerations**
- Content filtering happens at query time to minimize database load
- Authentication context passed through builder chain for efficiency
- Caching-friendly responses (authentication status doesn't change response caching headers)

### 5. **Testing and Development Experience**
- Comprehensive test coverage across all authentication states
- Interactive testing interface for manual verification
- URL parameter authentication for easy template-based testing
- Visual highlighting of LOLA-specific fields in responses

## Related Documentation

### LOLA Implementation Documentation
- [LOLA Discovery System](lola-discovery.md) - RFC8414 discovery endpoint and federation requirements
- [LOLA Collections Implementation](lola-collections.md) - Following/Followers collections with authentication patterns

### Core OAuth Documentation
- [OAuth Overview](oauth/overview.md) - High-level OAuth 2.0 implementation overview
- [Phase 1: Registration and Application Setup](oauth/phase-1-registration-and-application-setup.md)
- [Phase 2: Authorization Request and User Consent](oauth/phase-2-authorization-request-and-user-consent.md)
- [Phase 3: Authorization Code and Callback Handling](oauth/phase-3-authorization-code-and-callback-handling.md)
- [Phase 4: Token Exchange](oauth/phase-4-token-exchange.md)
- [Phase 5: Protected Resource Access](oauth/phase-5-protected-resource-access.md)
