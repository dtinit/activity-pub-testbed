import pytest
from testbed.core.models import Actor
from django.contrib.auth.models import User

# Test that when a user is created, both source and destination actors are automatically created
@pytest.mark.django_db
def test_user_creation_creates_actors():
    # Create a user directly
    user = User.objects.create_user(
        username="test_signal_user",
        email="test_signal@example.com", 
        password="password123"
    )
    
    # Verify actors were created
    actors = user.actors.all()
    assert actors.count() == 2
    
    # Verify we have one source and one destination actor
    source_actors = [a for a in actors if a.is_source]
    dest_actors = [a for a in actors if a.is_destination]
    
    assert len(source_actors) == 1
    assert len(dest_actors) == 1
    
    # Check actor usernames follow the expected pattern
    source_actor = source_actors[0]
    dest_actor = dest_actors[0]
    
    assert source_actor.username == f"{user.username}_source"
    assert dest_actor.username == f"{user.username}_dest"

# Test that the source actor's outbox is populated when a user is created
@pytest.mark.django_db
def test_source_actor_outbox_populated_on_creation(user_created_via_signal):
    # Get the source actor
    source_actor = user_created_via_signal.actors.get(role=Actor.ROLE_SOURCE)
    
    # Verify outbox exists
    assert hasattr(source_actor, 'portability_outbox')
    
    # Verify outbox is populated with activities
    outbox = source_actor.portability_outbox
    
    # Should have at least one Create activity for the actor itself
    assert outbox.activities_create.count() > 0
    
    # Should have notes
    notes_count = outbox.activities_create.filter(note__isnull=False).count()
    assert notes_count > 0
    
    # Should have remote likes and follows
    assert outbox.activities_like.filter(note__isnull=True).count() > 0  # Remote likes
    assert outbox.activities_follow.filter(target_actor__isnull=True).count() > 0  # Remote follows

# Test the populate_source_actor_outbox utility function directly
@pytest.mark.django_db
def test_populate_source_actor_outbox_utility(populated_source_actor):
    outbox = populated_source_actor.portability_outbox
    
    # Verify notes were created
    notes_count = outbox.activities_create.filter(note__isnull=False).count()
    assert notes_count == 3
    
    # Verify we have activities
    assert outbox.activities_create.count() >= 3  # At least the 3 note creation activities
    assert outbox.activities_like.count() > 0
    assert outbox.activities_follow.count() > 0
    
    # Check that notes belong to the source actor
    for activity in outbox.activities_create.filter(note__isnull=False):
        assert activity.note.actor == populated_source_actor
