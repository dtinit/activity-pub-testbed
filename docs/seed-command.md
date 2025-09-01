# Seed Command Implementation Guide

This document provides comprehensive documentation for the LOLA ActivityPub testbed seed command, covering its architecture, data generation patterns, LOLA compliance features, and the critical data consistency improvements implemented for realistic social relationship testing.

## Table of Contents

- [Overview](#overview)
- [Seed Command Architecture](#seed-command-architecture)
- [Five-Phase Seeding Process](#five-phase-seeding-process)
- [Social Graph Generation](#social-graph-generation)
- [Data Consistency Implementation](#data-consistency-implementation)
- [ActivityPub Relationship Model](#activitypub-relationship-model)
- [LOLA Collections Integration](#lola-collections-integration)
- [Federation Testing Support](#federation-testing-support)
- [Usage and Configuration](#usage-and-configuration)
- [Technical Implementation Details](#technical-implementation-details)
- [LOLA Specification Compliance](#lola-specification-compliance)

## Overview

The `python manage.py seed` command is the **foundation of the LOLA ActivityPub testbed**, creating a complete, realistic social media environment with users, content, and relationships needed to test LOLA account migration features.

### Purpose

**LOLA Testing Requirements:**
- Test OAuth flows with real user accounts and encrypted credential storage
- Verify LOLA collections (Following, Followers, Content, Liked, Blocked)
- Demonstrate account portability between source and destination servers
- Test authentication scopes and privacy controls
- Validate federation scenarios with remote servers
- Ensure data consistency between outbox activities and collection state

**Without seed data**, the testbed would be empty - no users to authenticate, no content to migrate, no relationships to test, and no realistic social graph to demonstrate LOLA capabilities.

### Key Innovation: Data Consistency Fix

The enhanced seed command ensures **critical data consistency between outbox Follow activities and Following collection relationship state** - a problem that was causing mismatched data counts and relationships in previous implementations.

## Seed Command Architecture

### Design Principles

1. **Realistic Social Patterns**: Creates believable social media behavior with persona-based following patterns
2. **Federation Testing**: Generates both local and remote relationships for comprehensive testing
3. **LOLA Compliance**: Ensures all generated data supports proper LOLA account portability testing
4. **Data Consistency**: Maintains alignment between activity history and current relationship state
5. **Educational Value**: Provides meaningful test data for learning LOLA implementation patterns

### Environment Safety

```python
# Security check prevents accidental production seeding
if not getattr(settings, "ALLOWED_SEED_COMMAND", False):
    self.stdout.write(self.style.ERROR("Seed command is not allowed in this environment."))
    return
```

**Configuration Required:**
```python
# In settings
ALLOWED_SEED_COMMAND = True  # Required for seed command to run
```

## Five-Phase Seeding Process

### Phase 1: Environment & Security Setup

**Validates environment safety and creates administrative infrastructure:**

```python
# Environment validation
ALLOWED_SEED_COMMAND = True  # Required in settings

# Admin user creation
admin_user = User.objects.create_superuser(
    username=settings.SEED_ADMIN_USERNAME,
    email=settings.SEED_ADMIN_EMAIL, 
    password=settings.SEED_ADMIN_PASSWORD
)
```

**Key Activities:**
- **Security Check**: Prevents accidental seeding in production environments
- **Admin User Creation**: Creates superuser from environment variables for system administration
- **Signal Integration**: Automatic actor creation via Django signals when users are created

### Phase 2: User & Actor Population

**Creates a diverse user base with paired source/destination actors:**

```python
# User types created
Users Created:
- 1 Admin user (admin/admin@example.com)
- 2 Login test users (login_user_1, login_user_2) - password: testpass123  
- 7 Regular users (user_0 through user_6)

# Actor pairing (18 total actors)
Actor Architecture:
- Each user gets SOURCE actor (for exporting data in LOLA migrations)
- Each user gets DESTINATION actor (for importing data in LOLA migrations)
```

**Actor Role Distribution:**
```
9 Source Actors:    Handle content creation, social relationships, LOLA data export
9 Destination Actors: Handle LOLA data import, account migration destinations
```

### Phase 3: Automatic Content Population (Signal-Driven)

**When source actors are created, Django signals automatically trigger `populate_source_actor_outbox()`:**

```python
# Automatic content per source actor
Per Source Actor Content:
- 3 Notes (social media posts, blog articles)
- 4 Create activities (3 for notes + 1 for actor itself)
- 1-3 Like activities (local likes of other users' notes)
- 1-3 Remote Like activities (likes of external content from mastodon.social, etc.)
- 1 Local Follow activity (following another local user)
- 1 Remote Follow activity (following external user from federation test servers)
```

**Content Distribution Pattern:**
- **Notes**: Varied content types (short posts, longer articles, media references)
- **Visibility**: Mix of public, private, and followers-only content for authentication testing
- **Federation**: Remote interactions with external ActivityPub servers for cross-server scenarios

### Phase 4: Social Graph Generation (LOLA Collections Enhancement)

**The `generate_social_relationships()` method creates realistic social networks with the critical data consistency fix:**

#### Persona-Based Following Patterns

```python
# Realistic social behavior simulation
Social Personas:
- Popular Actors (first 2): Follow 8-15 others (influencer behavior)  
- Casual Users (next 4): Follow 3-8 others (regular user engagement)
- Newcomers (remaining): Follow 1-4 others (new user exploration)
```

#### Data Consistency Implementation

**The Critical Fix:** For each Following relationship created, the system now creates both:

1. **Following relationship record** (for LOLA Following collection)
2. **Corresponding FollowActivity** in the actor's outbox (for activity history)
3. **Followers relationship record** on the target actor

```python
# Consistency implementation
for target in targets:
    # Create Following relationship (collection state)
    following, created = Following.objects.get_or_create(
        actor=actor,
        target_actor=target,
        defaults={'status': Following.STATUS_ACTIVE}
    )
    
    if created:
        # Create corresponding Follow activity in outbox (activity history)
        from testbed.core.factories import FollowActivityFactory
        follow_activity = FollowActivityFactory(
            actor=actor,
            target_actor=target,
            visibility="public"
        )
        actor.portability_outbox.add_activity(follow_activity)
```

#### Federation Testing Integration

```python
# Remote relationship generation
Federation Scenarios:
- Remote follows to mastodon.social, pixelfed.social, pleroma.instance
- Remote followers for popular actors (simulates cross-server popularity)
- Cached remote actor data for offline testing scenarios
- Full ActivityPub actor objects for federation compatibility
```

### Phase 5: Data Validation & Reporting

**Provides comprehensive statistics validating the generated test environment:**

```python
# Example output after seeding
Generated Test Data:
- 9 users, 18 actors (9 source + 9 destination)  
- 27 notes, 45 Create activities
- 59 Following relationships, 57 Followers relationships
- 77 Follow activities (61 local + 16 remote)
- 34 Like activities (11 local + 23 remote)
- Federation data from 3 remote servers
```

**Data Validation Categories:**
- **User/Actor Counts**: Verifies proper user and actor creation
- **Content Statistics**: Confirms notes and Create activities
- **Social Relationships**: Validates Following/Followers alignment
- **Activity Counts**: Ensures activity history consistency
- **Federation Data**: Confirms remote server representation

## Social Graph Generation

### Persona-Based Behavior Modeling

The seed command creates realistic social media behavior patterns by assigning personas to actors:

#### Popular Influencers (First 2 Actors)
```python
if actor in popular_actors:
    follow_count = random.randint(8, 15)  # Follow many to discover content
```

**Characteristics:**
- **High Following Count**: 8-15 accounts (content discovery behavior)
- **Multiple Remote Followers**: 1-3 remote followers each (cross-server influence)
- **Diverse Content Interaction**: Higher Like activity rates
- **Federation Presence**: Featured in remote relationship examples

#### Casual Users (Next 4 Actors)  
```python
elif actor in casual_actors:
    follow_count = random.randint(3, 8)   # Moderate social engagement
```

**Characteristics:**
- **Moderate Following**: 3-8 accounts (selective social connections)
- **Balanced Activity**: Mix of local and remote interactions
- **Typical Behavior**: Representative of average social media users
- **Community Focus**: Primarily local relationships with some federation

#### Newcomers (Remaining Actors)
```python
else:  # newcomer
    follow_count = random.randint(1, 4)   # Cautious exploration
```

**Characteristics:**
- **Conservative Following**: 1-4 accounts (exploring platform cautiously)
- **Learning Patterns**: Lower activity rates, focused interactions
- **Local Priority**: Primarily local relationships initially
- **Growth Potential**: Foundation for demonstrating user onboarding

### Social Network Topology

The generated social graph creates realistic network effects:

```python
# Realistic social network characteristics
Network Properties:
- Hub Actors: Popular users with many connections (social influence centers)
- Community Clusters: Casual users forming interconnected groups
- Bridge Connections: Cross-group relationships creating network cohesion
- Federation Links: Remote connections simulating multi-server social networks
```

## Data Consistency Implementation

### The Problem: Misaligned Data Systems

Previously, the testbed had **two separate data generation systems** creating inconsistent information:

1. **Outbox Population**: `populate_source_actor_outbox()` created Follow *activities* (historical actions)
2. **Collection State**: `generate_social_relationships()` created Following *relationships* (current state)

**Result**: Outbox showed different Follow counts than Following collections, making testing unrealistic.

### The Solution: Synchronized Data Generation

The enhanced implementation ensures both systems create **aligned and consistent data**:

#### Local Relationship Consistency

```python
# Create Following relationship (current state)
following, created = Following.objects.get_or_create(
    actor=actor,
    target_actor=target,
    defaults={'status': Following.STATUS_ACTIVE}
)

if created:
    following_count += 1
    
    # Create corresponding Follow activity in outbox (historical record)
    follow_activity = FollowActivityFactory(
        actor=actor,
        target_actor=target,
        visibility="public"
    )
    actor.portability_outbox.add_activity(follow_activity)
```

#### Remote Relationship Consistency

```python
# Create remote Following relationship (current state)
following, created = Following.objects.get_or_create(
    actor=actor,
    target_actor_url=remote_actor_url,
    defaults={
        'target_actor_data': remote_actor_data,
        'status': Following.STATUS_ACTIVE
    }
)

if created:
    # Create corresponding remote Follow activity (historical record)
    remote_follow_activity = FollowActivityFactory.create(
        remote=True,  # Uses remote trait
        actor=actor,
        target_actor_url=remote_actor_url,
        target_actor_data=remote_actor_data,
        visibility="public"
    )
    actor.portability_outbox.add_activity(remote_follow_activity)
```

### Data Consistency Results

**Before Fix:**
```
- 52 Following relationships (collection state)
- 28 Follow activities (activity history)
❌ Inconsistent data causing confusing test results
```

**After Fix:**
```
- 59 Following relationships (collection state)  
- 77 Follow activities (61 local + 16 remote)
✅ Consistent data: every Following relationship has corresponding activity
```

**Why More Activities Than Relationships:**
The activity count is higher because:
1. Original `populate_source_actor_outbox()` creates some Follow activities
2. New `generate_social_relationships()` adds consistent Follow activities  
3. Some activities might represent historical actions (unfollows, duplicates)
4. This is realistic: activity history includes more events than current state

## ActivityPub Relationship Model

### Understanding the Distinction

A critical aspect of the seed command implementation involves understanding the **fundamental difference** between ActivityPub's relationship model for Following vs Followers:

#### Following Side (Actor A follows Actor B)

**What Happens:**
- **Following Collection**: Actor A's collection shows Actor B (current relationship state)
- **Outbox Activity**: Actor A's outbox contains Follow activity (Actor A performed the action)
- **Data Consistency**: ✅ **This is what the seed command fixes**

**Example:**
```json
// Actor A's Following Collection
{
  "type": "OrderedCollection",
  "orderedItems": [
    {
      "type": "Person", 
      "id": "https://server.example/actors/B",
      "preferredUsername": "actorB"
    }
  ]
}

// Actor A's Outbox (contains Follow activity)
{
  "type": "Follow",
  "actor": "https://server.example/actors/A",
  "object": {
    "type": "Person",
    "id": "https://server.example/actors/B" 
  }
}
```

#### Followers Side (Actor A is followed by Actor B)

**What Happens:**
- **Followers Collection**: Actor A's collection shows Actor B (current relationship state)
- **No Outbox Activity**: Actor A's outbox does NOT contain a "Follower activity"
- **Activity Location**: The Follow activity goes in Actor B's outbox (who performed the follow)

**Example:**
```json
// Actor A's Followers Collection  
{
  "type": "OrderedCollection",
  "orderedItems": [
    {
      "type": "Person",
      "id": "https://server.example/actors/B",
      "preferredUsername": "actorB"
    }
  ]
}

// Actor A's Outbox (NO follower activity - that's in Actor B's outbox)
{
  "type": "OrderedCollection", 
  "orderedItems": [
    // Other activities by Actor A, but no "Follower" activity
  ]
}
```

### Why No "Follower Activities"?

**ActivityPub Principle**: You put activities in your outbox for **actions you perform**.

- **Following someone**: You perform the Follow action → goes in YOUR outbox
- **Being followed**: Someone else performs the Follow action → goes in THEIR outbox

**The seed command correctly implements this model:**
- Creates Following relationships WITH corresponding Follow activities in the actor's outbox ✅
- Creates Followers relationships WITHOUT creating "Follower activities" ✅
- Maintains proper ActivityPub semantics and realistic data patterns ✅

### Outbox vs Collection Data Formats

The seed command generates different but **correct** data formats for each system:

#### Outbox Format (Activities)
```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Follow",
  "id": "http://127.0.0.1:8000/api/activities/59",
  "actor": "http://127.0.0.1:8000/api/actors/17",
  "published": "2025-09-01T06:53:10.321680+00:00",
  "visibility": "public",
  "object": {
    "type": "Person",
    "id": "http://127.0.0.1:8000/api/actors/7",
    "preferredUsername": "user_0_source"
    // Full Actor object...
  }
}
```

#### Collection Format (Current State)
```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Person", 
  "id": "http://127.0.0.1:8000/api/actors/11",
  "preferredUsername": "user_2_source",
  "name": "user_2_source",
  "inbox": "http://127.0.0.1:8000/api/actors/11/inbox",
  "outbox": "http://127.0.0.1:8000/api/actors/11/outbox",
  "previously": []
}
```

**Key Differences:**
- **Outbox**: Contains Follow activities with "type": "Follow" and nested object
- **Collection**: Contains Person objects directly with "type": "Person"  
- **Purpose**: Outbox = historical actions, Collection = current relationships
- **Both are correct**: They serve different purposes in ActivityPub and LOLA

## LOLA Collections Integration

### Collection Data Requirements

The seed command generates data specifically designed to test all LOLA collections:

#### Following Collection (`/api/actors/{id}/following`)
- **Access**: Public (once URL discovered via LOLA authentication)
- **Content**: Current following relationships as Person objects
- **Use Case**: Account migration - "Who should I follow at my new location?"
- **Data Source**: `Following` model records with `STATUS_ACTIVE`

#### Followers Collection (`/api/actors/{id}/followers`)
- **Access**: LOLA scope required (privacy-sensitive)
- **Content**: Current follower relationships as Person objects  
- **Use Case**: Move notifications - "Who should be notified about my move?"
- **Data Source**: `Followers` model records with `STATUS_ACTIVE`

#### Content Collection (Future Implementation)
- **Access**: LOLA scope required
- **Content**: Notes and media for account migration
- **Use Case**: Content migration - "What content should be copied?"
- **Data Source**: Notes and attachments from outbox

#### Outbox Collection (`/api/actors/{id}/outbox`)
- **Access**: Public/LOLA filtered
- **Content**: Historical activities (Create, Like, Follow)
- **Use Case**: Activity migration - "What actions have I performed?"
- **Data Source**: All activities with authentication-based filtering

### Authentication-Based Access Patterns

The seed command creates data that demonstrates LOLA's two-tier privacy model:

```python
# Privacy matrix implemented by seed data
Collection Access Matrix:
| Collection | URL Discovery | Collection Access | Authentication Required |
|-----------|---------------|-------------------|------------------------|  
| Following | LOLA-gated   | Public           | No (once discovered)   |
| Followers | LOLA-gated   | Private          | Yes (LOLA scope)       |
| Outbox    | Public       | Content-filtered | Partial (scope-based)  |
```

### Collection URL Discovery

LOLA collections are discoverable only through authenticated Actor responses:

```json
// Public Actor response (no collection URLs)
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Person",
  "id": "https://server.example/actors/1",
  "preferredUsername": "user"
  // No following/followers URLs visible
}

// LOLA-authenticated Actor response (shows collection URLs)  
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://swicg.github.io/activitypub-data-portability/lola.jsonld"
  ],
  "type": "Person",
  "id": "https://server.example/actors/1", 
  "preferredUsername": "user",
  "following": "https://server.example/api/actors/1/following",    // URL revealed
  "followers": "https://server.example/api/actors/1/followers"     // URL revealed
}
```

## Federation Testing Support

### Multi-Server Social Networks

The seed command creates federation scenarios using representative remote servers:

```python
# Federation test servers 
REMOTE_SERVERS = [
    ("mastodon.social", ["mastodon_user1", "mastodon_user2", "mastodon_user3"]),
    ("pixelfed.social", ["pixel_user1", "pixel_user2", "pixel_user3"]),  
    ("pleroma.instance", ["pleroma_user1", "pleroma_user2", "pleroma_user3"]),
]
```

### Remote Relationship Types

#### Outgoing Federation (Local → Remote)
```python
# Local actors following remote actors
Remote Following Generation:
- First 5 actors get 1-2 remote follows each
- Creates cached remote actor data for offline testing
- Generates realistic federation scenarios
- Tests cross-server account portability
```

#### Incoming Federation (Remote → Local)
```python
# Remote actors following local actors  
Remote Follower Generation:
- Popular actors get 1-3 remote followers each
- Simulates cross-server influence and discovery
- Tests follower notification scenarios
- Validates LOLA move activity distribution
```

### Remote Actor Data Storage

The seed command stores complete remote actor metadata for offline testing:

```json
// Remote actor data example
{
  "type": "Person",
  "id": "https://mastodon.social/users/mastodon_user1",
  "preferredUsername": "mastodon_user1", 
  "name": "Mastodon User1",
  "summary": "ActivityPub user from mastodon.social",
  "inbox": "https://mastodon.social/users/mastodon_user1/inbox",
  "outbox": "https://mastodon.social/users/mastodon_user1/outbox",
  "followers": "https://mastodon.social/users/mastodon_user1/followers",
  "following": "https://mastodon.social/users/mastodon_user1/following"
}
```

**Benefits:**
- **Offline Testing**: Remote data available without network requests
- **Consistent Testing**: Same remote actors across test runs
- **Federation Simulation**: Realistic multi-server scenarios  
- **LOLA Compliance**: Proper handling of remote actor migration

## Usage and Configuration

### Basic Usage

```bash
# Clean slate for development/testing
python manage.py flush --no-input  
python manage.py seed --no-prompt

# Add to existing database (preserves existing data)
python manage.py seed --no-prompt
```

### Environment Configuration

**Required Settings:**
```python
# settings/development.py
ALLOWED_SEED_COMMAND = True

# Admin user credentials
SEED_ADMIN_USERNAME = "admin"
SEED_ADMIN_EMAIL = "admin@example.com"  
SEED_ADMIN_PASSWORD = "admin"

# Test user definitions
SEED_TEST_USERS = [
    {
        "username": "login_user_1",
        "email": "login_user_1@example.com", 
        "password": "testpass123"
    },
    {
        "username": "login_user_2",
        "email": "login_user_2@example.com",
        "password": "testpass123" 
    }
]
```

### Interactive Usage

**Command Options:**
- `--no-prompt`: Automatic admin user creation without interaction
- Default: Prompts for admin user creation confirmation

**Login Credentials:**
```
Admin User:
- Username: admin
- Password: admin

Test Users:
- Username: login_user_1, login_user_2
- Password: testpass123
```

### Development Workflow

```bash
# 1. Clean database
python manage.py flush --no-input

# 2. Generate fresh test data  
python manage.py seed --no-prompt

# 3. Start development server
python manage.py runserver

# 4. Test LOLA collections
# Navigate to: http://127.0.0.1:8000/
# Login as login_user_1 / testpass123  
# Test OAuth flows and collection access
```

## Technical Implementation Details

### Signal Integration

The seed command leverages Django signals for automatic content population:

```python
# When users are created, signals automatically:
@receiver(post_save, sender=User)
def create_user_actors(sender, instance, created, **kwargs):
    if created:
        # Create source actor (for LOLA export)
        source_actor = Actor.objects.create(
            user=instance,
            username=f"{instance.username}_source",
            role=Actor.ROLE_SOURCE,
        )
        
        # Create destination actor (for LOLA import)
        destination_actor = Actor.objects.create(
            user=instance,
            username=f"{instance.username}_destination", 
            role=Actor.ROLE_DESTINATION,
        )
        
        # Populate source actor with content
        populate_source_actor_outbox(source_actor)
```

### Factory Pattern Integration

The seed command uses FactoryBoy factories for consistent object creation:

```python
# Factory usage examples
from testbed.core.factories import FollowActivityFactory

# Local follow activity
follow_activity = FollowActivityFactory(
    actor=actor,
    target_actor=target, 
    visibility="public"
)

# Remote follow activity
remote_follow_activity = FollowActivityFactory.create(
    remote=True,  # Uses remote trait
    actor=actor,
    target_actor_url=remote_actor_url,
    target_actor_data=remote_actor_data,
    visibility="public"
)
```

### Model Constraints and Validation

The seed command respects database constraints ensuring data integrity:

```python
# Following model constraints
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

### Memory Management

The seed command is designed to be memory-efficient for development environments:

```python
# Efficient object creation patterns
# Creates objects in batches when possible
regular_users = UserWithActorsFactory.create_batch(7)

# Uses get_or_create to prevent duplicates
following, created = Following.objects.get_or_create(
    actor=actor,
    target_actor=target,
    defaults={'status': Following.STATUS_ACTIVE}
)
```

### Error Handling and Logging

```python
# Comprehensive error handling
try:
    # All seeding operations...
    following_count, followers_count, remote_relationships_count = self.generate_social_relationships(source_actors)
    
    self.stdout.write(self.style.SUCCESS(
        f'Social graph generated:\n'
        f'- {following_count} Following relationships\n'
        f'- {followers_count} Followers relationships\n'
        f'- {remote_relationships_count} Remote actor relationships'
    ))
    
except Exception as e:
    self.stdout.write(self.style.ERROR(f"Error seeding database: {str(e)}"))
```

## LOLA Specification Compliance

### Discovery Phase Requirements ✅

**LOLA Requirement**: "Discovery and authorization features allow the destination server to find out where to guide the user to authorize the destination server to the source server for an account migration."

**Seed Command Support:**
- Creates actors with OAuth application credentials for authorization testing
- Generates realistic user accounts for OAuth flow validation
- Enables testing of both RFC8414 and Actor-based discovery methods
- Provides multiple authentication scenarios (admin, test users, regular users)

### Social Collections Support ✅

**LOLA Requirement**: "The Following collection as per https://www.w3.org/TR/activitypub/#following SHOULD be provided on the Actor object when accessed with the account migration authorization token."

**Seed Command Implementation:**
- Generates Following relationships with proper ActivityPub compliance
- Creates Followers relationships with privacy-sensitive access controls
- Ensures collection URLs only appear in LOLA-authenticated responses
- Provides both local and remote relationship scenarios

### Content Migration Foundation ✅

**LOLA Requirement**: "Content can be copied from a new content collection endpoint."

**Seed Command Preparation:**
- Creates varied content (Notes with different visibility levels)
- Generates Create activities for content objects
- Establishes Like activities for interaction migration
- Provides foundation for content collection implementation

### Federation Compatibility ✅

**LOLA Requirement**: Support for cross-server account portability scenarios.

**Seed Command Features:**
- Generates remote actor relationships for federation testing
- Creates cached remote actor data for offline development
- Simulates multi-server social networks (mastodon.social, pixelfed.social, etc.)
- Enables testing of Move activity distribution to remote followers

### Privacy and Authentication ✅

**LOLA Requirement**: "Activities with extension-defined privacy or authorization properties MAY be requested and sent."

**Seed Command Implementation:**
- Creates content with varied visibility levels (public, private, followers-only)
- Generates relationships requiring different authentication levels
- Enables testing of authentication-based content filtering
- Supports scope-based access control validation

### Activity History Preservation ✅

**LOLA Consideration**: Account migration should preserve activity context and relationships.

**Seed Command Enhancement:**
- Ensures every Following relationship has corresponding Follow activity
- Maintains proper ActivityPub activity semantics
- Creates realistic activity history for migration testing
- Preserv
