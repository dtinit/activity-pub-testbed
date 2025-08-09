# Phase 4: Token Exchange

![Phase 4](../images/phase-4-token-exchange.png)

## Overview

Phase 4 represents the critical security bridge between **user authorization** (Phase 2) and **protected resource access** (Phase 5) in our OAuth 2.0 flow. After a user grants consent and the client receives an authorization code (Phase 3), Phase 4 is where the **Destination Service (Client)** securely exchanges this temporary code for a longer-lived **access token** that grants actual API access permissions.

In the context of LOLA account portability, this phase transforms the user's authorization decision into secure credentials that allow the Destination Service to begin the actual data transfer process from the Source Service.

## Objectives of Phase 4

- Securely exchange the short-lived authorization code for a longer-lived access token.
- Authenticate the client application using secure methods (HTTP Basic Authentication or request body).
- Verify all aspects of the authorization code (validity, expiration, client binding).
- Generate standardized token responses that adhere to OAuth 2.0 specifications.
- Implement strict security controls to prevent token theft or misuse.
- Provide clear error handling for common token exchange issues.

## Context in the LOLA Flow

Within the LOLA portability process:

- The **Destination Service** proves its identity to the Source Service using client credentials.
- The **Source Service** validates the authorization code and issues tokens for continued access.
- The tokens are bound to the specific **scope** requested during authorization (activitypub_account_portability).
- This establishes a secure context for subsequent data retrieval operations.

This phase acts as the "handshake" that establishes trust between services for data transfer. Once complete, the security context shifts from "proving authorization" to "accessing authorized resources."

## Core Components

### 1. Token Request Construction

The Destination Service constructs a token request with the following required parameters:

- **grant_type** – Always set to "authorization_code" for this flow
- **code** – The authorization code received in Phase 3
- **redirect_uri** – Must exactly match the URI used in the authorization request
- **Client authentication** (via one of two methods):
  - HTTP Basic Authentication header (preferred method)
  - Client credentials in request body

Example token request:

```http
POST /oauth/token HTTP/1.1
Host: source-service.example.com
Content-Type: application/x-www-form-urlencoded
Authorization: Basic base64(client_id:client_secret)

grant_type=authorization_code&code=SplxlOBeZQQYbYS6WxSbIA&redirect_uri=https%3A%2F%2Fdestination.example.com%2Fcallback
```

### 2. Server-Side Token Generation

Upon receiving the token request, the Source Service performs multiple validation steps:

- Verifies the authorization code is valid and unexpired (typically 10 minutes)
- Confirms the redirect URI matches the one used during authorization
- Authenticates the client using the provided credentials
- Validates that the code was issued to the requesting client
- Ensures the code hasn't been used before (one-time use)

If all validations pass, the server generates:

- An access token
- Optional refresh token (for long-term access)
- Scope information
- Token expiration time

### 3. Token Response

The Source Service returns a standardized token response:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "tGzv3JOkF0XG5Qx2TlKWIA",
  "scope": "activitypub_account_portability"
}
```

### 4. Client-Side Token Storage

The Destination Service securely stores:

- The access token for immediate API requests
- The refresh token (if provided) for obtaining new access tokens without user interaction
- Token metadata including expiration and scope

## Implementation Details

In our testbed implementation:

1. The `test_token_exchange_view` function handles the token exchange process:
   - Retrieves the authorization code from the callback
   - Obtains client credentials from the session
   - Constructs the token request with proper headers and authentication
   - Makes a secure POST request to the token endpoint
   - Processes the response and handles success/error conditions

2. The token endpoint itself (provided by Django OAuth Toolkit) performs:
   - Code validation (expiration, usage)
   - Client authentication
   - Scope validation via our custom `ActivityPubOAuth2Validator`
   - Token generation with configurable lifetimes

3. Our implementation offers two authentication methods:
   - HTTP Basic Authentication (preferred according to OAuth spec)
   - Request body authentication (as a fallback)

### Client Authentication Methods

```python
# First try: Use HTTP Basic Authentication for client credentials (preferred method)
token_response = requests.post(
    token_url, 
    data=token_data.copy(),
    headers=headers,
    auth=(client_id, client_secret)  # HTTP Basic Authentication
)

# If first method fails with 401 Unauthorized, try the alternative method
if token_response.status_code == 401:
    # Create a new copy of token_data with client credentials included
    body_auth_data = token_data.copy()
    body_auth_data['client_id'] = client_id
    body_auth_data['client_secret'] = client_secret
    
    # Make the request with credentials in the request body
    token_response = requests.post(
        token_url, 
        data=body_auth_data,
        headers=headers
    )
```

### Token Validation Process

The token endpoint performs sequential validation steps:

1. **Parameter Validation** – Ensures all required fields are present
2. **Client Authentication** – Verifies client identity through credentials
3. **Code Validation** – Checks the authorization code's validity
4. **Scope Validation** – Uses our custom validator:

```python
def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
    # Ensure 'activitypub_account_portability' is included in the scopes
    if 'activitypub_account_portability' not in scopes:
        logger.warning(f"Client {client_id} requested OAuth without 'activitypub_account_portability' scope")
        return False
    return super().validate_scopes(client_id, scopes, client, request, *args, **kwargs)
```

## Security Considerations

- **Client Authentication** – This phase is critical for security as it ensures only the legitimate client with correct credentials can exchange the code for tokens.

- **Transport Security** – All token requests and responses must use HTTPS to prevent token theft through network interception.

- **Code Reuse Prevention** – Authorization codes are single-use only. Our implementation automatically invalidates codes after successful exchange.

- **Short Code Lifetime** – Authorization codes are valid for only 10 minutes, minimizing the window of opportunity for attacks.

- **Token Security** – Access tokens provide access to protected resources, so their secure storage is essential. In production systems, tokens should be:
  - Stored securely (not in localStorage or cookies accessible by JavaScript)
  - Never exposed to client-side code
  - Protected against CSRF attacks when used

## Error Handling

Common errors during token exchange include:

- **invalid_request** – The request is missing a required parameter or is malformed
- **invalid_client** – Client authentication failed
- **invalid_grant** – The authorization code is invalid, expired, or revoked
- **unauthorized_client** – The client is not authorized to use this grant type
- **unsupported_grant_type** – The server doesn't support this grant type
- **invalid_scope** – The requested scope is invalid or exceeds the original scope

Our implementation provides detailed error responses and logging to facilitate debugging and resolution:

```python
# Handle error response with detailed logging
logger.warning(f"Token exchange failed with status {token_response.status_code}")
logger.warning(f"Response headers: {dict(token_response.headers)}")

try:
    error_details = token_response.json()
    logger.warning(f"Response JSON: {error_details}")
    context['token_error'] = f"Error: {error_details.get('error', 'Unknown error')}"
    if 'error_description' in error_details:
        context['token_error'] += f" - {error_details['error_description']}"
except:
    logger.warning(f"Response text: {token_response.text}")
    context['token_error'] = f"Error: HTTP {token_response.status_code} - {token_response.text}"
```

## Testing Interface

Our implementation includes an testing interface in `oauth_token_exchange.html` that:

1. **Displays Token Structure** – Shows all components of the token response:
   - Access token
   - Token type
   - Expiration time
   - Scope
   - Refresh token (if provided)

2. **Demonstrates Usage** – Provides code examples for using the token:

```http
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

```python
import requests

headers = {
    'Authorization': 'Bearer YOUR_ACCESS_TOKEN',
}

response = requests.get('https://api.example.com/activity-pub/user', headers=headers)
```

3. **Explains Errors** – Provides troubleshooting guidance for common token exchange errors.

## Best Practices Implemented

1. **Session-Based Secret Management** – Client secrets are stored in raw form in the database for testbed simplicity, with secure session-based access during OAuth flows. Hashed storage is planned as a future security enhancement.

2. **Robust Error Handling** – Clear error messages with proper HTTP status codes and OAuth error responses.

3. **Flexible Authentication** – Support for multiple client authentication methods with automatic fallback.

4. **Comprehensive Logging** – Detailed logging at each step for security audit and debugging.

5. **Strict Validation** – Thorough validation of all parameters including redirect URI matching and scope validation.

## Configuration Settings

Our implementation has specific settings in Django's settings.py:

```python
# OAuth2 provider configuration
OAUTH2_PROVIDER = {
    'SCOPES': {
        'activitypub_account_portability': 'ActivityPub Account Portability',
    },
    'ACCESS_TOKEN_EXPIRE_SECONDS': 3600,  # 1 hour
    'REFRESH_TOKEN_EXPIRE_SECONDS': 86400,  # 1 day
    'AUTHORIZATION_CODE_EXPIRE_SECONDS': 600,  # 10 minutes
    'OAUTH2_VALIDATOR_CLASS': 'testbed.core.utils.oauth_validators.ActivityPubOAuth2Validator',
    # For testing purposes -> make PKCE optional
    'PKCE_REQUIRED': False,
}
```

## Future Enhancements

- **PKCE Support** – Enable Proof Key for Code Exchange for improved security with public clients.
- **JWT Tokens** – Consider using JWT tokens with custom claims for enhanced security and portability.
- **Refresh Token Rotation** – Implement refresh token rotation for improved security.
- **Monitoring and Alerts** – Add monitoring for unusual token exchange patterns that might indicate attacks.
- **Rate Limiting** – Implement token endpoint rate limiting to prevent brute force attacks.

## Significance of Phase 4

This phase completes the secure authorization process and enables protected resource access:

- Establishes secure credentials for the entire account transfer process
- Binds the access token to the `activitypub_account_portability` scope
- Creates the security context required for transferring potentially sensitive user data
- Enables the Destination Service to begin requesting specific ActivityPub resources in JSON-LD format
