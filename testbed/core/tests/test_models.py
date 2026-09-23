import pytest
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone
from testbed.core.models import Actor, Note, CreateActivity, LikeActivity, FollowActivity, PortabilityOutbox, Following, Followers
from testbed.core.factories import (
    UserOnlyFactory,
    ActorFactory,
    IsolatedActorFactory,
    NoteFactory,
    CreateActivityFactory,
    LikeActivityFactory,
    FollowActivityFactory,
    FollowingFactory,
    FollowersFactory,
)
from testbed.core.tests.helpers import (
    create_isolated_remote_like,
    create_isolated_remote_follow,
)

# Test basic actor creation
def test_actor_creation(actor):
    assert actor.user is not None
    assert actor.role in [Actor.ROLE_SOURCE, Actor.ROLE_DESTINATION]

# Test actor string representation
def test_actor_str_representation(actor):
    assert str(actor) == f"{actor.user.username}'s {actor.role} actor"

# Test that a user cannot have multiple actors with the same role
def test_actor_unique_role_constraint():
    # Create a user directly
    user = UserOnlyFactory(username="unique_role_test_user")
    
    # Create first actor manually
    first_actor = Actor.objects.create(
        user=user,
        username="unique_role_test_source",
        role=Actor.ROLE_SOURCE
    )
    
    # Try to create another actor with the same role for same user
    second_actor = Actor(
        user=user,
        username="unique_role_test_source2",
        role=Actor.ROLE_SOURCE
    )
    
    with pytest.raises(ValidationError):
        second_actor.clean()

# Test recording actor movement history
def test_actor_move_history(actor):
    test_date = timezone.now()
    
    actor.record_move("old-server.com", "old_username", test_date)
    assert len(actor.previously) == 1
    assert actor.previously[0]["type"] == "Move"
    assert actor.previously[0]["object"] == "https://old-server.com/users/old_username"
    assert actor.previously[0]["published"] == test_date.isoformat()

# Test that record_move stamps the current time when no date is supplied
def test_actor_move_history_defaults_to_now(actor):
    before = timezone.now()
    actor.record_move("old-server.com", "old_username")
    after = timezone.now()

    assert len(actor.previously) == 1
    recorded = datetime.fromisoformat(actor.previously[0]["published"])
    assert before <= recorded <= after

# Test basic note creation
def test_note_creation(note):
    assert note.content is not None
    assert note.visibility in ["public", "private", "followers-only"]

# Test that an explicitly supplied `published` survives to the database
def test_note_published_is_settable(actor):
    original = timezone.now() - timedelta(days=400)

    note = Note.objects.create(actor=actor, content="historical", published=original)
    note.refresh_from_db()

    assert note.published == original

# Test that omitting `published` still stamps the current time, so making the field
# settable did not quietly make it required.
def test_note_published_defaults_to_now(actor):
    before = timezone.now()
    note = Note.objects.create(actor=actor, content="fresh")
    after = timezone.now()

    note.refresh_from_db()
    assert before <= note.published <= after

# Test that every migration metadata field survives a round trip to the database
def test_note_metadata_fields_round_trip(actor):
    breadcrumbs = [
        {"actor": "https://newsite.example/aurora/", "id": "https://newsite.example/items/02751cab"},
        {"actor": "https://lemongrove.example/", "id": "https://lemongrove.example/2016/05/minimal"},
    ]
    note = Note.objects.create(
        actor=actor,
        content="<p>copied</p>",
        summary="A copied article",
        to=["https://lemongrove.example/followers"],
        cc=["https://oakfrost.example/brock"],
        in_reply_to="https://lemongrove.example/2016/05/parent",
        url="https://lemongrove.example/2016/05/minimal",
        source={"content": "A copied article", "mediaType": "text/markdown"},
        previously=breadcrumbs,
    )
    note.refresh_from_db()

    assert note.summary == "A copied article"
    assert note.to == ["https://lemongrove.example/followers"]
    assert note.cc == ["https://oakfrost.example/brock"]
    assert note.in_reply_to == "https://lemongrove.example/2016/05/parent"
    assert note.url == "https://lemongrove.example/2016/05/minimal"
    assert note.source == {"content": "A copied article", "mediaType": "text/markdown"}
    assert note.previously == breadcrumbs

# Test that unset list fields default to [] rather than None
def test_note_metadata_defaults_are_empty_not_null(actor):
    note = Note.objects.create(actor=actor, content="bare")
    note.refresh_from_db()

    assert note.to == []
    assert note.cc == []
    assert note.previously == []
    assert note.summary == ""
    assert note.source is None
    assert note.in_reply_to is None
    assert note.url is None

# Test that the list defaults are per-instance
def test_note_list_defaults_are_not_shared(actor):
    first = Note.objects.create(actor=actor, content="first")
    second = Note.objects.create(actor=actor, content="second")

    first.to.append("https://example.test/followers")

    assert second.to == []
    assert Note.objects.get(pk=second.pk).to == []

# Test that the factory spreads timestamps, so `-published` is a total order with no ties.
def test_note_factory_spreads_published(actor):
    notes = NoteFactory.create_batch(5, actor=actor)
    stamps = [n.published for n in notes]

    assert len(set(stamps)) == 5
    assert stamps == sorted(stamps, reverse=True)

# Test note string representation
def test_note_str_representation(note):
    expected = f"Note by {note.actor.user.username}: {note.content[:30]}"
    assert str(note) == expected

# Test string representation of Create activity with note
def test_create_activity_str_with_note(create_activity):
    expected = f"Create by {create_activity.actor.user.username}: {create_activity.note}"
    assert str(create_activity) == expected

# Test string representation of Create activity for actor creation
def test_create_activity_str_for_actor_creation(actor_create_activity):
    expected = f"Create by {actor_create_activity.actor.user.username}: Actor creation"
    assert str(actor_create_activity) == expected

# Test that Like activity requires either note or remote object data
def test_like_activity_validation():
    # Create isolated actor using helper function
    actor = IsolatedActorFactory(prefix="like_validation_test")
    
    # Create invalid activity (no note and no remote object data)
    activity = LikeActivity(
        actor=actor,
        note=None,
        object_url=None,
        visibility="public"
    )
    
    with pytest.raises(ValidationError):
        activity.clean()

# Test Like activity with remote object data
def test_like_activity_remote_object_validation():
    # Use helper function that creates isolated actor and uses factory
    activity = create_isolated_remote_like()
    
    # Verify remote object data
    assert activity.object_url.startswith("https://remote.example/notes/")
    assert activity.object_data["content"] == "Remote note content"

# Test that Follow activity requires either target_actor or remote actor data
def test_follow_activity_validation():
    # Create isolated actor using helper function
    actor = IsolatedActorFactory(prefix="follow_validation_test")
    
    # Create invalid activity (no target_actor and no remote actor data)
    activity = FollowActivity(
        actor=actor,
        target_actor=None,
        target_actor_url=None,
        target_actor_data=None,
        visibility="public"
    )
    
    with pytest.raises(ValidationError):
        activity.clean()

# Test Follow activity with remote actor data
def test_follow_activity_remote_actor_validation():
    # Use helper function that creates isolated actor and uses factory
    activity = create_isolated_remote_follow()
    
    # Verify remote actor data
    assert activity.target_actor_url.startswith("https://remote.example/users/")
    assert "preferredUsername" in activity.target_actor_data

# Test outbox is created automatically for actors
def test_portability_outbox_creation():
    from testbed.core.utils.actor_utils import populate_source_actor_outbox
    from testbed.core.models import Note, CreateActivity
    
    # Create an isolated actor for testing
    actor = IsolatedActorFactory(prefix="outbox_test")
    
    # Actor should have an outbox created automatically
    assert actor.portability_outbox is not None
    
    # The outbox should have the actor creation activity
    assert actor.portability_outbox.activities_create.count() >= 1
    
    # At least one Create activity should be for actor creation (no note)
    actor_create_activities = actor.portability_outbox.activities_create.filter(note__isnull=True)
    assert actor_create_activities.count() >= 1
    
    # Manually populate the outbox with additional content for testing
    populate_source_actor_outbox(actor, num_notes=2)
    
    # Now verify we have notes
    note_activities = actor.portability_outbox.activities_create.filter(note__isnull=False)
    assert note_activities.count() > 0
    
    # And we should have likes and follows
    assert actor.portability_outbox.activities_like.count() > 0
    assert actor.portability_outbox.activities_follow.count() > 0

# Test adding different types of activities to outbox
def test_outbox_activity_types():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="types_test")
    target_actor = IsolatedActorFactory(prefix="target_test")
    
    # Create a note for the like activity
    note = NoteFactory(actor=actor, content="Test note for liking")
    
    outbox = actor.portability_outbox
    initial_create_count = outbox.activities_create.count()
    initial_like_count = outbox.activities_like.count()
    initial_follow_count = outbox.activities_follow.count()

    # Use factories but pass in our manually created actors
    create_activity = CreateActivityFactory(actor=actor, note=note)
    like_activity = LikeActivityFactory(actor=actor, note=note)
    follow_activity = FollowActivityFactory(actor=actor, target_actor=target_actor)

    outbox.add_activity(create_activity)
    outbox.add_activity(like_activity)
    outbox.add_activity(follow_activity)

    # Check that counts have increased by 1
    assert outbox.activities_create.count() == initial_create_count + 1
    assert outbox.activities_like.count() == initial_like_count + 1
    assert outbox.activities_follow.count() == initial_follow_count + 1

# Test adding multiple activities to outbox
def test_outbox_activity_addition():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="addition_test")
    target_actor = IsolatedActorFactory(prefix="target_addition_test")
    
    # Create a note for the like activity
    note = NoteFactory(actor=actor, content="Test note for addition")
    
    outbox = actor.portability_outbox
    
    activities = [
        CreateActivityFactory(actor=actor, note=note),
        LikeActivityFactory(actor=actor, note=note),
        FollowActivityFactory(actor=actor, target_actor=target_actor)
    ]
    
    for activity in activities:
        outbox.add_activity(activity)
        
    assert activities[0] in outbox.activities_create.all()
    assert activities[1] in outbox.activities_like.all()
    assert activities[2] in outbox.activities_follow.all()


# LOLA Following Model Tests

# Test basic Following relationship creation (local)
def test_following_creation_local():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="following_test")
    target_actor = IsolatedActorFactory(prefix="target_test")
    
    # Create local following relationship using factory
    following = FollowingFactory(actor=actor, target_actor=target_actor)
    
    assert following.actor == actor
    assert following.target_actor == target_actor
    assert following.status == Following.STATUS_ACTIVE
    assert following.target_actor_url is None
    assert following.target_actor_data is None

# Test Following relationship creation (remote)
def test_following_creation_remote():
    # Create isolated actor using helper function
    actor = IsolatedActorFactory(prefix="following_remote_test")
    
    # Create remote following relationship using factory trait
    following = FollowingFactory.build(actor=actor, remote=True)
    following.save()
    
    assert following.actor == actor
    assert following.target_actor is None
    assert following.target_actor_url.startswith("https://remote.example/users/")
    assert following.target_actor_data["type"] == "Person"
    assert "preferredUsername" in following.target_actor_data

# Test Following model validation - requires exactly one target
def test_following_validation_no_target():
    # Create isolated actor using helper function
    actor = IsolatedActorFactory(prefix="following_validation_test")
    
    # Create invalid following (no target_actor and no remote data)
    following = Following(
        actor=actor,
        target_actor=None,
        target_actor_url=None,
        target_actor_data=None,
        status=Following.STATUS_ACTIVE
    )
    
    with pytest.raises(ValidationError):
        following.clean()

# Test Following model validation - cannot have both local and remote targets
def test_following_validation_both_targets():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="following_both_test")
    target_actor = IsolatedActorFactory(prefix="target_both_test")
    
    # Create invalid following (both local and remote targets)
    following = Following(
        actor=actor,
        target_actor=target_actor,
        target_actor_url="https://remote.example/users/someone",
        target_actor_data={"type": "Person", "preferredUsername": "someone"},
        status=Following.STATUS_ACTIVE
    )
    
    with pytest.raises(ValidationError):
        following.clean()

# Test Following string representation (local)
def test_following_str_representation_local():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="following_str_test")
    target_actor = IsolatedActorFactory(prefix="target_str_test")
    
    following = FollowingFactory(actor=actor, target_actor=target_actor)
    expected = f'{actor.username} follows {target_actor.username} (local)'
    assert str(following) == expected

# Test Following string representation (remote)
def test_following_str_representation_remote():
    # Create isolated actor using helper function
    actor = IsolatedActorFactory(prefix="following_str_remote_test")
    
    following = FollowingFactory.build(actor=actor, remote=True)
    following.save()
    username = following.target_actor_data.get('preferredUsername', 'unknown')
    expected = f'{actor.username} follows {username} (remote)'
    assert str(following) == expected

# Test Following unique constraint for local relationships
def test_following_unique_constraint_local():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="following_unique_test")
    target_actor = IsolatedActorFactory(prefix="target_unique_test")
    
    # Create first following relationship
    first_following = FollowingFactory(actor=actor, target_actor=target_actor)
    
    # Try to create duplicate - should raise IntegrityError on save
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        FollowingFactory(actor=actor, target_actor=target_actor)

# Test Following unique constraint for remote relationships  
def test_following_unique_constraint_remote():
    # Create isolated actor using helper function
    actor = IsolatedActorFactory(prefix="following_unique_remote_test")
    remote_url = "https://remote.example/users/unique_test"
    
    # Create first remote following relationship
    first_following = FollowingFactory.build(actor=actor, remote=True)
    first_following.target_actor_url = remote_url
    first_following.save()
    
    # Try to create duplicate - should raise IntegrityError on save
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        second_following = FollowingFactory.build(actor=actor, remote=True)
        second_following.target_actor_url = remote_url
        second_following.save()


# LOLA Followers Model Tests

# Test basic Followers relationship creation (local)
def test_followers_creation_local():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="followers_test")
    follower_actor = IsolatedActorFactory(prefix="follower_test")
    
    # Create local followers relationship using factory
    followers = FollowersFactory(actor=actor, follower_actor=follower_actor)
    
    assert followers.actor == actor
    assert followers.follower_actor == follower_actor
    assert followers.status == Followers.STATUS_ACTIVE
    assert followers.follower_actor_url is None
    assert followers.follower_actor_data is None

# Test Followers relationship creation (remote)
def test_followers_creation_remote():
    # Create isolated actor using helper function
    actor = IsolatedActorFactory(prefix="followers_remote_test")
    
    # Create remote followers relationship using factory trait
    followers = FollowersFactory.build(actor=actor, remote=True)
    followers.save()
    
    assert followers.actor == actor
    assert followers.follower_actor is None
    assert followers.follower_actor_url.startswith("https://remote.example/users/")
    assert followers.follower_actor_data["type"] == "Person"
    assert "preferredUsername" in followers.follower_actor_data

# Test Followers model validation - requires exactly one follower
def test_followers_validation_no_follower():
    # Create isolated actor using helper function
    actor = IsolatedActorFactory(prefix="followers_validation_test")
    
    # Create invalid followers (no follower_actor and no remote data)
    followers = Followers(
        actor=actor,
        follower_actor=None,
        follower_actor_url=None,
        follower_actor_data=None,
        status=Followers.STATUS_ACTIVE
    )
    
    with pytest.raises(ValidationError):
        followers.clean()

# Test Followers model validation - cannot have both local and remote followers
def test_followers_validation_both_followers():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="followers_both_test")
    follower_actor = IsolatedActorFactory(prefix="follower_both_test")
    
    # Create invalid followers (both local and remote followers)
    followers = Followers(
        actor=actor,
        follower_actor=follower_actor,
        follower_actor_url="https://remote.example/users/someone",
        follower_actor_data={"type": "Person", "preferredUsername": "someone"},
        status=Followers.STATUS_ACTIVE
    )
    
    with pytest.raises(ValidationError):
        followers.clean()

# Test Followers string representation (local)
def test_followers_str_representation_local():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="followers_str_test")
    follower_actor = IsolatedActorFactory(prefix="follower_str_test")
    
    followers = FollowersFactory(actor=actor, follower_actor=follower_actor)
    expected = f'{follower_actor.username} follows {actor.username} (local)'
    assert str(followers) == expected

# Test Followers string representation (remote)
def test_followers_str_representation_remote():
    # Create isolated actor using helper function
    actor = IsolatedActorFactory(prefix="followers_str_remote_test")
    
    followers = FollowersFactory.build(actor=actor, remote=True)
    followers.save()
    username = followers.follower_actor_data.get('preferredUsername', 'unknown')
    expected = f'{username} follows {actor.username} (remote)'
    assert str(followers) == expected

# Test Followers unique constraint for local relationships
def test_followers_unique_constraint_local():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="followers_unique_test")
    follower_actor = IsolatedActorFactory(prefix="follower_unique_test")
    
    # Create first followers relationship
    first_followers = FollowersFactory(actor=actor, follower_actor=follower_actor)
    
    # Try to create duplicate - should raise IntegrityError on save
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        FollowersFactory(actor=actor, follower_actor=follower_actor)

# Test Followers unique constraint for remote relationships  
def test_followers_unique_constraint_remote():
    # Create isolated actor using helper function
    actor = IsolatedActorFactory(prefix="followers_unique_remote_test")
    remote_url = "https://remote.example/users/unique_follower_test"
    
    # Create first remote followers relationship
    first_followers = FollowersFactory.build(actor=actor, remote=True)
    first_followers.follower_actor_url = remote_url
    first_followers.save()
    
    # Try to create duplicate - should raise IntegrityError on save
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        second_followers = FollowersFactory.build(actor=actor, remote=True)
        second_followers.follower_actor_url = remote_url
        second_followers.save()

# Test Following status field functionality
def test_following_status_field():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="following_status_test")
    target_actor = IsolatedActorFactory(prefix="target_status_test")
    
    # Test with inactive trait
    following = FollowingFactory(actor=actor, target_actor=target_actor, inactive=True)
    assert following.status == Following.STATUS_INACTIVE
    
    # Update status back to active
    following.status = Following.STATUS_ACTIVE
    following.save()
    following.refresh_from_db()
    assert following.status == Following.STATUS_ACTIVE

# Test Followers status field functionality
def test_followers_status_field():
    # Create isolated actors using helper functions
    actor = IsolatedActorFactory(prefix="followers_status_test")
    follower_actor = IsolatedActorFactory(prefix="follower_status_test")
    
    # Test with inactive trait
    followers = FollowersFactory(actor=actor, follower_actor=follower_actor, inactive=True)
    assert followers.status == Followers.STATUS_INACTIVE
    
    # Update status back to active
    followers.status = Followers.STATUS_ACTIVE
    followers.save()
    followers.refresh_from_db()
    assert followers.status == Followers.STATUS_ACTIVE
