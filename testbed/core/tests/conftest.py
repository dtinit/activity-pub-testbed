import pytest
import random
from testbed.core.factories import (
    UserOnlyFactory,
    UserWithActorsFactory,
    IsolatedActorFactory,
    NoteFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
)
from testbed.core.models import Actor, User
from testbed.core.utils.actor_utils import populate_source_actor_outbox

# Creates an isolated actor with note for validation tests
@pytest.fixture
def isolated_actor_with_note():
    actor = IsolatedActorFactory(prefix="isolated_note_test")
    note = NoteFactory(actor=actor)
    return {"actor": actor, "note": note}

# Creates a user without actors
@pytest.fixture
def user():
    return UserOnlyFactory()

# Creates a user with associated actors
@pytest.fixture
def user_with_actors():
    return UserWithActorsFactory()

# Returns an actor for testing
@pytest.fixture
def actor():
    # Create a unique user for this actor
    user = UserOnlyFactory(username="fixture_test_user")
    return Actor.objects.create(
        user=user,
        username="fixture_test_actor_source",
        role=Actor.ROLE_SOURCE,
    )

# Returns another actor for interaction testing
@pytest.fixture
def other_actor():
    # Create a unique user for this actor
    user = UserOnlyFactory(username="fixture_other_user")
    return Actor.objects.create(
        user=user,
        username="fixture_test_actor_dest",
        role=Actor.ROLE_DESTINATION,
    )

# Creates a note from an actor
@pytest.fixture
def note(actor):
    return NoteFactory(actor=actor)

# Creates a Create activity for a note
@pytest.fixture
def create_activity(actor, note):
    return CreateActivityFactory(actor=actor, note=note)

# Creates a Create activity for actor creation
@pytest.fixture
def actor_create_activity(actor):
    return CreateActivityFactory(
        actor=actor,
        note=None,  # No note means this is an Actor creation activity
        visibility="public"
    )

# Creates a Like activity for a note
@pytest.fixture
def like_activity(actor, note):
    return LikeActivityFactory(actor=actor, note=note)

# Creates a Follow activity between actors
@pytest.fixture
def follow_activity(actor, other_actor):
    return FollowActivityFactory(
        actor=actor,
        target_actor=other_actor
    )

# Returns the actor's outbox
@pytest.fixture
def outbox():
    # Create a unique user for this actor's outbox
    user = UserOnlyFactory(username="fixture_outbox_user")
    source_actor = Actor.objects.create(
        user=user,
        username="fixture_outbox_actor",
        role=Actor.ROLE_SOURCE,
    )
    return source_actor.portability_outbox

# Creates a user via the User model directly to test signal-based actor creation
@pytest.fixture
def user_created_via_signal():
    user = User.objects.create_user(
        username="signal_test_user",
        email="signal_test@example.com",
        password="testpass123"
    )
    return user

# Creates a source actor with populated outbox for testing
@pytest.fixture
def populated_source_actor():
    # Get an existing source actor
    source_actor = User.objects.create_user(
        username=f"populate_test_user_{random.randint(1000, 9999)}",
        email="populate_test@example.com",
        password="testpass123"
    ).actors.get(role=Actor.ROLE_SOURCE)
    
    # Now manually repopulate the outbox with our controlled content for testing
    # First clear the existing content
    source_actor.portability_outbox.activities_create.all().delete()
    source_actor.portability_outbox.activities_like.all().delete()
    source_actor.portability_outbox.activities_follow.all().delete()
    
    # Now populate with known content
    populate_source_actor_outbox(
        source_actor=source_actor,
        num_notes=3,
        include_local_interactions=True
    )
    
    return source_actor


# Provide consistent request objects and authentication contexts for JSON-LD builder testing

@pytest.fixture
def mock_request():
    """
    Create a mock request object for testing JSON-LD URL generation.
    
    This fixture provides a consistent request object that can be used across
    all test files for building URLs in JSON-LD responses.
    
    Returns:
        Mock request object with proper META data for URL building
    """
    from django.test import RequestFactory
    
    factory = RequestFactory()
    request = factory.get('/api/actors/')
    request.META['HTTP_HOST'] = 'testserver'
    
    return request

@pytest.fixture
def basic_auth_context(mock_request):
    """
    Auth context for unauthenticated requests (basic ActivityPub).
    
    This fixture provides the authentication context used for public/unauthenticated
    requests that should receive basic ActivityPub data without LOLA enhancements.
    
    Args:
        mock_request: Automatically injected mock request fixture
        
    Returns:
        Dict with authentication context for basic ActivityPub responses
    """
    return {
        'is_authenticated': False,
        'has_portability_scope': False,
        'request': mock_request
    }

@pytest.fixture
def lola_auth_context(mock_request):
    """
    Auth context for LOLA authenticated requests (enhanced data).
    
    This fixture provides the authentication context used for requests with
    proper LOLA portability scope that should receive enhanced data including
    discovery fields and private content.
    
    Args:
        mock_request: Automatically injected mock request fixture
        
    Returns:
        Dict with authentication context for LOLA enhanced responses
    """
    return {
        'is_authenticated': True,
        'has_portability_scope': True,
        'request': mock_request
    }

@pytest.fixture
def oauth_auth_context(mock_request):
    """
    Auth context for OAuth authenticated requests without portability scope.
    
    This fixture provides the authentication context for requests that have
    OAuth authentication but lack the LOLA portability scope, so they receive
    basic ActivityPub data like unauthenticated requests.
    
    Args:
        mock_request: Automatically injected mock request fixture
        
    Returns:
        Dict with authentication context for OAuth-only responses
    """
    return {
        'is_authenticated': True,
        'has_portability_scope': False,
        'request': mock_request
    }
