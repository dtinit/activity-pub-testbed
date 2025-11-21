from rest_framework.test import APIClient
from rest_framework import status
from testbed.core.models import Actor
from testbed.core.factories import UserWithActorsFactory, AccessTokenFactory

"""
LOLA Compliance Tests for Actor Endpoint

Actor.accountPortabilityOauth Field (Public OAuth Discovery)
- The accountPortabilityOauth field MUST always be present for OAuth discovery
- No authentication required (public visibility)

Actor Migration Properties (Authenticated Access) 
- Migration properties MUST only appear with valid portability scope
- Requires 'activitypub_account_portability' scope
"""

# Verify Actor without token includes OAuth endpoint but NO migration data
def test_actor_without_token_includes_oauth_endpoint_but_no_migration():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    # Make unauthenticated request
    response = client.get(f'/api/actors/{actor.id}/')
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # OAuth endpoint must be present for public discovery
    assert 'accountPortabilityOauth' in data, \
        "OAuth endpoint must be present for public discovery"
    assert data['accountPortabilityOauth'].endswith('/oauth/authorize/'), \
        "OAuth endpoint should point to authorization endpoint"
    
    # Migration data must NOT be present without authentication
    assert 'migration' not in data, \
        "migration object requires portability token"
    
    # Privacy-sensitive collections must NOT be present
    assert 'following' not in data, "following requires authentication"
    assert 'followers' not in data, "followers requires authentication"
    assert 'liked' not in data, "liked requires authentication"
    assert 'blocked' not in data, "blocked requires authentication"
    assert 'outbox' not in data, "outbox requires authentication"
    
    # Basic Actor fields must be present
    assert data['type'] == 'Person'
    assert data['id'] == f'http://testserver/api/actors/{actor.id}'
    assert 'inbox' in data
    assert 'preferredUsername' in data
    
    # Context must include both ActivityStreams and blocked (per LOLA spec)
    assert isinstance(data['@context'], list)
    assert 'https://www.w3.org/ns/activitystreams' in data['@context']
    assert 'https://purl.archive.org/socialweb/blocked' in data['@context']


# Verify OAuth endpoint URL is properly formatted
def test_oauth_endpoint_url_is_absolute_and_valid():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    response = client.get(f'/api/actors/{actor.id}/')
    data = response.json()
    
    oauth_url = data['accountPortabilityOauth']
    
    # URL must be absolute with scheme
    assert oauth_url.startswith('http://') or oauth_url.startswith('https://'), \
        "OAuth endpoint must be absolute URL"
    
    # URL must point to correct path
    assert oauth_url.endswith('/oauth/authorize/'), \
        "OAuth endpoint must point to /oauth/authorize/"


# Verify Actor with portability token includes migration data
def test_actor_with_portability_token_includes_migration():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    # Create OAuth token with portability scope
    token = AccessTokenFactory(lola_scope=True)
    
    # Make authenticated request
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')
    response = client.get(f'/api/actors/{actor.id}/')
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # OAuth endpoint still present (always public)
    assert 'accountPortabilityOauth' in data, \
        "OAuth endpoint must always be present"
    
    # Migration object must be present with authentication
    assert 'migration' in data, \
        "migration object required with portability token"
    
    # All migration properties must be present and absolute URLs
    migration = data['migration']
    for field in ['outbox', 'content', 'following', 'blocked', 'liked']:
        assert field in migration, f"migration.{field} is required"
        assert migration[field].startswith('http'), f"migration.{field} must be absolute URL"
    
    # Privacy-sensitive collections must be present
    for collection in ['following', 'followers', 'liked', 'blocked', 'outbox']:
        assert collection in data, f"{collection} required with authentication"
        assert data[collection].startswith('http'), f"{collection} must be absolute URL"
    
    # Blocked context must be present
    assert 'https://purl.archive.org/socialweb/blocked' in data['@context']
    
    # Basic fields must still be present
    assert data['type'] == 'Person'
    assert data['id'] == f'http://testserver/api/actors/{actor.id}'


# Verify wrong OAuth scope does not grant access to migration data
def test_actor_with_wrong_scope_returns_public_response():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    # Create token WITHOUT portability scope
    token = AccessTokenFactory(scope='read write')
    
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')
    response = client.get(f'/api/actors/{actor.id}/')
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Should have OAuth endpoint (public)
    assert 'accountPortabilityOauth' in data
    
    # Should NOT have migration data (insufficient scope)
    assert 'migration' not in data
    assert 'following' not in data
    assert 'followers' not in data


# Verify migration URLs point to correct endpoints
def test_migration_urls_point_to_correct_collection_endpoints():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    # Create OAuth token with portability scope
    token = AccessTokenFactory(lola_scope=True)
    
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')
    response = client.get(f'/api/actors/{actor.id}/')
    data = response.json()
    
    migration = data['migration']
    actor_url = f'http://testserver/api/actors/{actor.id}'
    
    # Verify each migration URL points to correct endpoint
    assert migration['outbox'] == f'{actor_url}/outbox'
    assert migration['content'] == f'{actor_url}/content'
    assert migration['following'] == f'{actor_url}/following'
    assert migration['blocked'] == f'{actor_url}/blocked'
    assert migration['liked'] == f'{actor_url}/liked'


# Compare public and authenticated responses side-by-side
def test_public_vs_authenticated_response_comparison():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    # Get public response
    public_response = client.get(f'/api/actors/{actor.id}/')
    public_data = public_response.json()
    
    # Get authenticated response with portability token
    token = AccessTokenFactory(lola_scope=True)
    
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')
    auth_response = client.get(f'/api/actors/{actor.id}/')
    auth_data = auth_response.json()
    
    # Both should succeed
    assert public_response.status_code == status.HTTP_200_OK
    assert auth_response.status_code == status.HTTP_200_OK
    
    # Basic fields should be identical
    for field in ['@context', 'type', 'id', 'preferredUsername', 'inbox']:
        assert public_data[field] == auth_data[field], \
            f"Basic field '{field}' should match in both responses"
    
    # Both should have accountPortabilityOauth
    assert 'accountPortabilityOauth' in public_data
    assert 'accountPortabilityOauth' in auth_data
    assert public_data['accountPortabilityOauth'] == auth_data['accountPortabilityOauth']
    
    # Only authenticated should have migration data
    assert 'migration' not in public_data
    assert 'migration' in auth_data
    
    # Only authenticated should have privacy-sensitive collections
    for collection in ['following', 'followers', 'liked', 'blocked', 'outbox']:
        assert collection not in public_data
        assert collection in auth_data
