from rest_framework.test import APIClient
from rest_framework import status

"""
Tests for .well-known/oauth-authorization-server endpoint
RFC8414-compliant OAuth Authorization Server Metadata with LOLA extensions
"""

# Validate that discovery endpoint returns RFC8414-compliant OAuth metadata.
def test_rfc8414_returns_valid_metadata():

    client = APIClient()
    
    response = client.get('/.well-known/oauth-authorization-server')
    
    assert response.status_code == status.HTTP_200_OK
    assert response['Content-Type'] == 'application/json'
    assert response['Access-Control-Allow-Origin'] == '*'
    
    data = response.json()
    
    required_fields = [
        'issuer', 
        'authorization_endpoint', 
        'token_endpoint',
        'scopes_supported', 
        'response_types_supported', 
        'grant_types_supported'
    ]
    
    for field in required_fields:
        assert field in data, f"Missing required OAuth field: {field}"

# Verify LOLA-specific parameters are included for account portability discovery
def test_rfc8414_includes_lola_parameters():
    
    client = APIClient()
    
    response = client.get('/.well-known/oauth-authorization-server')
    data = response.json()
    
    # LOLA scope should be supported
    assert 'activitypub_account_portability' in data['scopes_supported'], \
        "LOLA scope 'activitypub_account_portability' must be in scopes_supported"
    
    # LOLA endpoint parameter should be present (LOLA extension to RFC8414)
    assert 'activitypub_account_portability' in data, \
        "LOLA parameter 'activitypub_account_portability' must be present"
    
    lola_metadata = data['activitypub_account_portability']
    
    assert 'supported' in lola_metadata, \
        "LOLA metadata 'supported' flag must be present"
        
    assert lola_metadata['supported'] is True, \
        "LOLA metadata 'supported' flag must be True"
    
    assert 'authorization_endpoint' in lola_metadata, \
         "LOLA metadata 'authorization_endpoint' must be present"
         
    assert lola_metadata['authorization_endpoint'].endswith('/oauth/authorize/'), \
        "LOLA authorization endpoint should point to OAuth authorization endpoint"
    
    assert 'scopes' in lola_metadata, \
        "LOLA metadata 'scopes' must be present"
        
    assert 'activitypub_account_portability' in lola_metadata['scopes'], \
        "LOLA scopes array must include 'activitypub_account_portability'"
        

# Ensure all URLs in discovery response are absolute for federation compatibility
def test_rfc8414_urls_are_absolute():

    client = APIClient()
    
    response = client.get('/.well-known/oauth-authorization-server')
    data = response.json()
    
    # All URL fields must be absolute for proper federation
    url_fields = [
        'issuer', 
        'authorization_endpoint', 
        'token_endpoint'
    ]
    
    for field in url_fields:
        url = data[field]
        assert url.startswith('http'), \
            f"{field} should be absolute URL starting with http/https: {url}"
    
    lola_metadata = data['activitypub_account_portability']
    lola_auth_endpoint = lola_metadata['authorization_endpoint']
    assert lola_auth_endpoint.startswith('http'), \
        f"LOLA authorization_endpoint should be absolute URL: {lola_auth_endpoint}"


def test_rfc8414_authorization_code_flow_support():
    """
    Verify that the authorization code flow is properly advertised.
    
    LOLA uses OAuth 2.0 authorization code flow, so the metadata must
    indicate support for 'code' response type and 'authorization_code' grant type.
    """
    client = APIClient()
    
    response = client.get('/.well-known/oauth-authorization-server')
    data = response.json()
    
    # Authorization code flow requirements
    assert 'code' in data['response_types_supported'], \
        "Must support 'code' response type for authorization code flow"
    assert 'authorization_code' in data['grant_types_supported'], \
        "Must support 'authorization_code' grant type"


# Verify CORS headers are present to enable cross-origin discovery
def test_rfc8414_cors_headers_for_federation():
    
    client = APIClient()
    
    response = client.get('/.well-known/oauth-authorization-server')
    
    # CORS headers are essential for federation
    assert 'Access-Control-Allow-Origin' in response, \
        "CORS header 'Access-Control-Allow-Origin' must be present"
    assert response['Access-Control-Allow-Origin'] == '*', \
        "CORS should allow all origins for public discovery"


# Verify that OAuth endpoint URLs match the actual django-oauth-toolkit routes.
def test_rfc8414_oauth_endpoints_match():
    
    client = APIClient()
    
    response = client.get('/.well-known/oauth-authorization-server')
    data = response.json()
    
    """
    Check that OAuth endpoints use the correct paths
    This ensures consistency between the advertised endpoints and the actual OAuth implementation.
    """
    assert '/oauth/authorize/' in data['authorization_endpoint'], \
        "Authorization endpoint should use /oauth/authorize/ path"
    assert '/oauth/token/' in data['token_endpoint'], \
        "Token endpoint should use /oauth/token/ path"
    
    lola_metadata = data['activitypub_account_portability']
    assert lola_metadata['authorization_endpoint'] == data['authorization_endpoint'], \
        "LOLA portability endpoint should point to the same authorization endpoint"
