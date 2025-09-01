# LOLA Collections Implementation

This document covers the Following and Followers collections implementation for LOLA account portability, including models, endpoints, and access control patterns.

## Table of Contents

- [Overview](#overview)
- [Collections Architecture](#collections-architecture)
- [Following Collection](#following-collection)
- [Followers Collection](#followers-collection)
- [Model Implementation](#model-implementation)
- [Endpoint Implementation](#endpoint-implementation)
- [Access Control Patterns](#access-control-patterns)
- [JSON-LD Format](#json-ld-format)
- [Usage Examples](#usage-examples)
- [LOLA Specification Compliance](#lola-specification-compliance)

## Overview

LOLA collections represent the current state of social relationships, separate from historical activity records. The implementation provides two key collections with different access patterns:

- **Following Collection**: Who an actor is currently following (**public access**)
- **Followers Collection**: Who is currently following an actor (**LOLA-gated access**)

These collections enable complete social graph migration during account portability while maintaining proper privacy controls.

## Collections Architecture

### Current State vs Historical Activities

The collections represent **current relationship state**, not historical activities:

| Aspect | Collections | Activities |
|--------|-------------|------------|
| **Purpose** | Current relationships | Historical events |
| **Data Model** | `Following`/`Followers` models | `FollowActivity` model |
| **Updates** | Status changes (active/inactive) | Immutable records |
| **LOLA Usage** | Account migration | Activity history |
| **Access Control** | Collection-based | Activity-based |

### Key Design Decisions

1. **Separate Models**: Collections use dedicated models rather than querying activities
2. **Status Management**: Relationships have active/inactive states for lifecycle management
3. **Federation Support**: Both local and remote actor relationships
4. **Privacy Controls**: Different access levels per collection type

## Following Collection

### Purpose

Represents who an actor is currently following. This collection supports account migration by enabling users to rebuild their following list on a new server.

### Access Control

**Public Access**: Following collections are publicly accessible per ActivityPub specification. However, the collection URLs only appear in LOLA-authenticated Actor responses (LOLA-gated discovery).

**Key Point**: Once you have the URL, the collection itself requires no authentication.

### Model Structure

```python
class Following(models.Model):
    # The actor doing the following
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, related_name="following_relationships")
    
    # Local relationship
    target_actor = models.ForeignKey(Actor, on_delete=models.CASCADE, null=True, blank=True)
    
    # Remote relationship
    target_actor_url = models.URLField(max_length=500, null=True, blank=True)
    target_actor_data = models.JSONField(null=True, blank=True)
    
    # Status management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Endpoint

**URL**: `/api/actors/{id}/following`  
**Method**: `GET`  
**Authentication**: None required (public access)  
**Discovery**: URL appears only in LOLA-authenticated Actor responses

## Followers Collection

### Purpose

Represents who is currently following an actor. This is privacy-sensitive data that enables users to understand their follower base when migrating accounts.

### Access Control

**LOLA Authentication Required**: Only accessible with `activitypub_account_portability` scope to protect user privacy.

### Model Structure

```python
class Followers(models.Model):
    # The actor being followed
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, related_name="follower_relationships")
    
    # Local follower
    follower_actor = models.ForeignKey(Actor, on_delete=models.CASCADE, null=True, blank=True)
    
    # Remote follower
    follower_actor_url = models.URLField(max_length=500, null=True, blank=True)
    follower_actor_data = models.JSONField(null=True, blank=True)
    
    # Status management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Endpoint

**URL**: `/api/actors/{id}/followers`  
**Method**: `GET`  
**Authentication**: LOLA scope required  
**Discovery**: URL appears only in LOLA-authenticated Actor responses

## Model Implementation

### Validation Rules

Both models enforce strict validation to ensure data integrity:

```python
def clean(self):
    super().clean()
    # Ensure exactly one target is specified
    if not self.target_actor and not (self.target_actor_url and self.target_actor_data):
        raise ValidationError("Either local target_actor or remote actor data must be provided")
    if self.target_actor and self.target_actor_url:
        raise ValidationError("Cannot specify both local and remote targets")
```

### Unique Constraints

Database-level constraints prevent duplicate relationships:

```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=['actor', 'target_actor'],
            name='unique_local_following',
            condition=models.Q(target_actor__isnull=False)
        ),
        models.UniqueConstraint(
            fields=['actor', 'target_actor_url'],
            name='unique_remote_following',
            condition=models.Q(target_actor_url__isnull=False)
        )
    ]
```

### Status Management

Relationships support lifecycle management through status fields:

- **`STATUS_ACTIVE`**: Currently following/followed (appears in collections)
- **`STATUS_INACTIVE`**: No longer following/followed (filtered out)

This enables soft deletion and relationship history while keeping collections current.

### Federation Support

Both local and remote relationships are supported:

```python
# Local relationship
following = Following.objects.create(
    actor=user_actor,
    target_actor=local_actor,
    status=Following.STATUS_ACTIVE
)

# Remote relationship
following = Following.objects.create(
    actor=user_actor,
    target_actor_url="https://remote.example/users/someone",
    target_actor_data={
        "type": "Person",
        "preferredUsername": "someone",
        "name": "Someone Remote"
    },
    status=Following.STATUS_ACTIVE
)
```

## Endpoint Implementation

### Following Collection Endpoint

**Location**: `testbed/core/views.py` - `following_collection()`

```python
@api_view(['GET'])
@authentication_classes([OptionalOAuth2Authentication])
def following_collection(request, pk):
    """
    LOLA Following collection endpoint.
    
    Note: While the collection URL only appears in LOLA-authenticated Actor objects,
    the collection itself follows standard ActivityPub public access patterns.
    """
    actor = get_object_or_404(Actor, pk=pk)
    
    # NO authentication check - this collection is publicly accessible
    
    # Get all active following relationships
    following_qs = Following.objects.filter(
        actor=actor, 
        status=Following.STATUS_ACTIVE
    ).order_by('-created_at')
    
    # Build collection items
    items = []
    for following in following_qs:
        if following.target_actor:
            # Local actor - return full Actor object
            items.append(build_actor_json_ld(following.target_actor))
        else:
            # Remote actor - return cached actor data
            actor_data = following.target_actor_data.copy()
            actor_data['id'] = following.target_actor_url
            items.append(actor_data)
    
    # Build ActivityPub OrderedCollection
    collection_data = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "OrderedCollection", 
        "id": f"{request.scheme}://{request.get_host()}/api/actors/{pk}/following",
        "totalItems": len(items),
        "orderedItems": items
    }
    
    return Response(collection_data)
```

### Followers Collection Endpoint

**Location**: `testbed/core/views.py` - `followers_collection()`

```python
@api_view(['GET'])
@authentication_classes([OptionalOAuth2Authentication])
def followers_collection(request, pk):
    """
    LOLA Followers collection endpoint.
    
    This is privacy-sensitive data that requires LOLA scope authentication.
    """
    actor = get_object_or_404(Actor, pk=pk)
    
    # Check authentication - requires LOLA scope
    if not getattr(request, 'has_portability_scope', False):
        return Response(
            {
                "error": "unauthorized",
                "description": "This collection requires activitypub_account_portability scope"
            },
            status=401
        )
    
    # Get all active follower relationships
    followers_qs = Followers.objects.filter(
        actor=actor,
        status=Followers.STATUS_ACTIVE
    ).order_by('-created_at')
    
    # Build collection items
    items = []
    for follower in followers_qs:
        if follower.follower_actor:
            # Local actor - return full Actor object
            items.append(build_actor_json_ld(follower.follower_actor))
        else:
            # Remote actor - return cached actor data
            actor_data = follower.follower_actor_data.copy()
            actor_data['id'] = follower.follower_actor_url
            items.append(actor_data)
    
    # Build ActivityPub OrderedCollection
    collection_data = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "OrderedCollection",
        "id": f"{request.scheme}://{request.get_host()}/api/actors/{pk}/followers", 
        "totalItems": len(items),
        "orderedItems": items
    }
    
    return Response(collection_data)
```

## Access Control Patterns

### LOLA-Gated Discovery

Collection URLs only appear in LOLA-authenticated Actor responses, but access patterns differ:

```python
# Public Actor response
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Person",
  "id": "https://server.example/actors/1",
  "preferredUsername": "user"
  // No collection URLs visible
}

# LOLA-authenticated Actor response
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://swicg.github.io/activitypub-data-portability/lola.jsonld"
  ],
  "type": "Person",
  "id": "https://server.example/actors/1",
  "preferredUsername": "user",
  "following": "https://server.example/api/actors/1/following",    // Public access
  "followers": "https://server.example/api/actors/1/followers"     // LOLA scope required
}
```

### Collection Access Matrix

| Collection | URL Discovery | Collection Access | Authentication Required |
|-----------|---------------|-------------------|------------------------|
| Following | LOLA-gated | **Public** | **No** |
| Followers | LOLA-gated | **Private** | **Yes (LOLA scope)** |

### Authentication Implementation Difference

```python
# Following collection - NO authentication check
def following_collection(request, pk):
    actor = get_object_or_404(Actor, pk=pk)
    # Immediately proceeds to build collection - no auth check
    following_qs = Following.objects.filter(actor=actor, status=Following.STATUS_ACTIVE)
    # ...

# Followers collection - LOLA scope REQUIRED
def followers_collection(request, pk):
    actor = get_object_or_404(Actor, pk=pk)
    # Authentication check REQUIRED
    if not getattr(request, 'has_portability_scope', False):
        return Response({
            "error": "unauthorized",
            "description": "This collection requires activitypub_account_portability scope"
        }, status=401)
    # ...
```

## JSON-LD Format

Both collections follow ActivityPub OrderedCollection format:

### Collection Structure

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "OrderedCollection",
  "id": "https://server.example/api/actors/1/following",
  "totalItems": 2,
  "orderedItems": [
    {
      "type": "Person",
      "id": "https://server.example/actors/2",
      "preferredUsername": "friend1",
      "name": "Friend One"
    },
    {
      "type": "Person", 
      "id": "https://remote.example/users/friend2",
      "preferredUsername": "friend2",
      "name": "Friend Two"
    }
  ]
}
```

### Local Actor Items

Local actors are returned with full Actor JSON-LD:

```json
{
  "type": "Person",
  "id": "https://server.example/actors/2",
  "preferredUsername": "friend1",
  "name": "Friend One",
  "inbox": "https://server.example/actors/2/inbox",
  "outbox": "https://server.example/actors/2/outbox"
}
```

### Remote Actor Items

Remote actors use cached data with original URLs:

```json
{
  "type": "Person",
  "id": "https://remote.example/users/friend2",
  "preferredUsername": "friend2", 
  "name": "Friend Two"
}
```

### Federation Headers

Both endpoints include proper federation headers:

```python
response = Response(collection_data)
if request.accepted_renderer.format == 'json':
    response['Content-Type'] = 'application/activity+json'
    response['Access-Control-Allow-Origin'] = '*'
```

## Usage Examples

### Accessing Following Collection (Public)

```python
import requests

# NO authentication required - public access
response = requests.get('https://server.example/api/actors/1/following')
following_data = response.json()

print(f"Following {following_data['totalItems']} actors:")
for actor in following_data['orderedItems']:
    print(f"- {actor['preferredUsername']} ({actor['id']})")
```

### Accessing Followers Collection (LOLA-gated)

```python
import requests

# LOLA authentication REQUIRED
headers = {'Authorization': f'Bearer {lola_access_token}'}
response = requests.get('https://server.example/api/actors/1/followers', headers=headers)

if response.status_code == 401:
    print("LOLA scope required for followers collection")
else:
    followers_data = response.json()
    print(f"Has {followers_data['totalItems']} followers:")
    for actor in followers_data['orderedItems']:
        print(f"- {actor['preferredUsername']} ({actor['id']})")
```

### LOLA Migration Client Example

```python
# Complete social graph migration
def migrate_social_graph(source_actor_id, lola_token):
    # Get following list (public - no token needed)
    following_response = requests.get(f'https://source.example/api/actors/{source_actor_id}/following')
    following_data = following_response.json()
    
    # Get followers list (requires LOLA scope)
    headers = {'Authorization': f'Bearer {lola_token}'}
    followers_response = requests.get(
        f'https://source.example/api/actors/{source_actor_id}/followers', 
        headers=headers
    )
    followers_data = followers_response.json()
    
    return {
        'following': following_data['orderedItems'],
        'followers': followers_data['orderedItems'],
        'following_count': following_data['totalItems'],
        'followers_count': followers_data['totalItems']
    }
```

### Collection Discovery Pattern

```python
# Discover collection URLs via LOLA-authenticated Actor endpoint
def discover_collections(actor_id, lola_token):
    headers = {'Authorization': f'Bearer {lola_token}'}
    response = requests.get(f'https://server.example/api/actors/{actor_id}', headers=headers)
    actor_data = response.json()
    
    collections = {}
    
    # Following URL (public access once discovered)
    if 'following' in actor_data:
        following_response = requests.get(actor_data['following'])  # No auth needed!
        collections['following'] = following_response.json()
    
    # Followers URL (LOLA scope still required)  
    if 'followers' in actor_data:
        followers_response = requests.get(actor_data['followers'], headers=headers)  # Auth required!
        collections['followers'] = followers_response.json()
    
    return collections
```

## LOLA Specification Compliance

### Following Collection Requirements

**LOLA Specification**: "The Following collection as per https://www.w3.org/TR/activitypub/#following SHOULD be provided on the Actor object when accessed with the account migration authorization token."

**Implementation**: ✅
- Collection URL appears only in LOLA-authenticated Actor responses (discovery gated)
- Collection itself follows ActivityPub public access patterns (collection public)
- Includes complete Actor objects for migration
- Maintains federation compatibility

### ActivityPub Compatibility

**ActivityPub Standard**: Following collections are typically public per ActivityPub specification.

**Implementation**: ✅
- Following collection is publicly accessible (no authentication required)  
- LOLA adds discovery gating (URL only visible with LOLA auth)
- Maintains backward compatibility with standard ActivityPub clients
- Follows OrderedCollection format

### Privacy Protection

**LOLA Consideration**: Followers data is privacy-sensitive and should be protected.

**Implementation**: ✅
- Followers collection requires LOLA scope authentication
- Following collection remains public (per ActivityPub standard)
- URLs only discovered through LOLA authentication  
- Proper error responses for unauthorized access

### Federation Support

**LOLA Requirement**: Support for both local and remote relationships during migration.

**Implementation**: ✅
- Local relationships with full Actor objects
- Remote relationships with cached metadata
- Proper URL preservation for remote actors
- Federation headers for cross-origin access

### Two-Tier Privacy Model

**LOLA Innovation**: Discovery gating + access control provides flexible privacy:

1. **Discovery Privacy**: Collection URLs only visible to LOLA-authenticated requests
2. **Access Privacy**: Different authentication requirements per collection type

**Benefits**:
- Following: Public access maintains ActivityPub compatibility
- Followers: Private access protects sensitive follower information
- Discovery gating prevents unauthorized collection enumeration
- Flexible privacy model supports various use cases

---

## Related Documentation

- [LOLA Discovery](lola-discovery.md) - RFC8414 .well-known endpoint for LOLA discovery
- [LOLA Authentication](lola-authentication.md) - OAuth flow and Actor-based authentication
- [LOLA Collections Testing](lola-collections-testing.md) - Comprehensive test coverage for collections

## References

- [LOLA Specification](https://swicg.github.io/activitypub-data-portability/lola.html)
- [ActivityPub Specification](https://www.w3.org/TR/activitypub/)
- [ActivityStreams OrderedCollection](https://www.w3.org/TR/activitystreams-vocabulary/#dfn-orderedcollection)
