from rest_framework.test import APIClient
from rest_framework import status
from testbed.core.models import Actor
from testbed.core.factories import (
    UserWithActorsFactory,
    AccessTokenFactory,
)
from testbed.core.tests.conftest import bind_portability_token

"""
LOLA Compliance Tests for Actor Endpoint

Actor.endpoints.oauthMigrationEndpoint (Public OAuth Discovery)
- MUST always be present so destinations can discover where to authorize,
  even from an unauthenticated Actor fetch (§4.2).
- Advertised in parallel with endpoints.oauthAuthorizationEndpoint.
- No authentication required (public visibility)

Actor.migration.* (Authenticated Feature Discovery)
- Migration properties MUST only appear with valid portability scope
- Contains exactly outbox / content / following / blocked, each pointing at a
  dedicated actors/<pk>/migration/... route (§4.4).
"""

# Verify Actor without token includes OAuth migration endpoint but NO migration object
def test_actor_without_token_includes_oauth_endpoint_but_no_migration():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    # Make unauthenticated request
    response = client.get(f'/api/actors/{actor.id}/')
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # endpoints object must be present for public discovery
    assert 'endpoints' in data, \
        "endpoints object must be present for public OAuth discovery"
    endpoints = data['endpoints']
    assert endpoints['oauthMigrationEndpoint'].endswith('/oauth/authorize/'), \
        "oauthMigrationEndpoint should point to the authorization endpoint"
    # Parallel authorization endpoint must also be advertised
    assert endpoints['oauthAuthorizationEndpoint'].endswith('/oauth/authorize/'), \
        "oauthAuthorizationEndpoint should be advertised in parallel"

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


# Verify OAuth migration endpoint URL is absolute and correctly formatted
def test_oauth_migration_endpoint_url_is_absolute_and_valid():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    response = client.get(f'/api/actors/{actor.id}/')
    data = response.json()
    
    oauth_url = data['endpoints']['oauthMigrationEndpoint']
    
    # URL must be absolute with scheme
    assert oauth_url.startswith('http://') or oauth_url.startswith('https://'), \
        "oauthMigrationEndpoint must be an absolute URL"
    
    # URL must point to the correct path
    assert oauth_url.endswith('/oauth/authorize/'), \
        "oauthMigrationEndpoint must point to /oauth/authorize/"


# Verify Actor with portability token includes corrected migration object
def test_actor_with_portability_token_includes_migration():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    token = bind_portability_token(actor, user=user)
    
    # Make authenticated request
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')
    response = client.get(f'/api/actors/{actor.id}/')
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # OAuth discovery endpoints still present (always public)
    assert 'endpoints' in data, \
        "endpoints object must always be present"
    
    # Migration object must be present with authentication
    assert 'migration' in data, \
        "migration object required with portability token"
    
    # Migration object must be present and absolute URLs
    migration = data['migration']
    assert set(migration.keys()) == {'outbox', 'content', 'following', 'blocked'}, \
        "migration object must contain exactly outbox/content/following/blocked"
    for field in ['outbox', 'content', 'following', 'blocked']:
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
    
    # Should have public OAuth discovery endpoints
    assert 'endpoints' in data
    
    # Should NOT have migration data (insufficient scope)
    assert 'migration' not in data
    assert 'following' not in data
    assert 'followers' not in data


# Verify migration URLs point to the dedicated migration routes
def test_migration_urls_point_to_dedicated_migration_routes():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    token = bind_portability_token(actor, user=user)
    
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')
    response = client.get(f'/api/actors/{actor.id}/')
    data = response.json()
    
    migration = data['migration']
    actor_url = f'http://testserver/api/actors/{actor.id}'
    
    # Each migration URL points to its dedicated /migration/... route
    assert migration['outbox'] == f'{actor_url}/migration/outbox'
    assert migration['content'] == f'{actor_url}/migration/content'
    assert migration['following'] == f'{actor_url}/migration/following'
    assert migration['blocked'] == f'{actor_url}/migration/blocked'


# Verify every advertised dedicated migration route is real and resolves
def test_dedicated_migration_routes_resolve():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)

    # The migration routes enforce token-to-actor binding, so bind a portability
    # token to this actor (an unbound token would be rejected with actor_mismatch).
    token = bind_portability_token(actor, user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')

    # All four advertised migration URLs must resolve (routed and implemented)
    for surface in ['outbox', 'content', 'following', 'blocked']:
        response = client.get(f'/api/actors/{actor.id}/migration/{surface}/')
        assert response.status_code == status.HTTP_200_OK, \
            f"migration/{surface} route must resolve for a bound portability token"


# Compare public and authenticated responses side-by-side
def test_public_vs_authenticated_response_comparison():
    client = APIClient()
    user = UserWithActorsFactory()
    actor = Actor.objects.get(user=user, role=Actor.ROLE_SOURCE)
    
    # Get public response
    public_response = client.get(f'/api/actors/{actor.id}/')
    public_data = public_response.json()
    
    token = bind_portability_token(actor, user=user)

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
    
    # Both should expose the same public OAuth discovery endpoints
    assert 'endpoints' in public_data
    assert 'endpoints' in auth_data
    assert public_data['endpoints'] == auth_data['endpoints']
    
    # Only authenticated should have migration data
    assert 'migration' not in public_data
    assert 'migration' in auth_data
    
    # Only authenticated should have privacy-sensitive collections
    for collection in ['following', 'followers', 'liked', 'blocked', 'outbox']:
        assert collection not in public_data
        assert collection in auth_data
