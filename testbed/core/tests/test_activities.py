from testbed.core.models import Actor

# Test CreateActivity basic properties and relationships
def test_create_activity(create_activity):
    assert create_activity.actor is not None
    assert create_activity.visibility in ["public", "private", "followers-only"]
    # Test both cases: with note and without note (Actor creation)
    if create_activity.note:
        assert str(create_activity) == f"Create by {create_activity.actor.user.username}: {create_activity.note}"
    else:
        assert str(create_activity) == f"Create by {create_activity.actor.user.username}: Actor creation"

# Test LikeActivity basic properties and relationships
def test_like_activity(like_activity):
    assert like_activity.actor is not None
    assert like_activity.note is not None  # Required for Like
    assert like_activity.visibility in ["public", "private", "followers-only"]
    assert str(like_activity) == f"Like by {like_activity.actor.user.username}: {like_activity.note}"

def test_like_activity_remote_object(like_activity):
    # Test with remote object instead of local note
    like_activity.note = None
    like_activity.object_url = "https://remote.example/notes/123"
    like_activity.object_data = {"content": "Remote content"}
    
    assert str(like_activity) == f"Like by {like_activity.actor.user.username}: Remote content..."
    assert like_activity.object_url == "https://remote.example/notes/123"
    assert like_activity.object_data["content"] == "Remote content"

# Test FollowActivity basic properties and relationships
def test_follow_activity(follow_activity):
    assert follow_activity.actor is not None
    assert follow_activity.target_actor is not None  # Required for Follow
    assert follow_activity.visibility in ["public", "private", "followers-only"]
    assert str(follow_activity) == f"Follow by {follow_activity.actor.user.username}: {follow_activity.target_actor.user.username}"

def test_follow_activity_remote_actor(follow_activity):
    # Test with remote actor instead of local target
    follow_activity.target_actor = None
    follow_activity.target_actor_url = "https://remote.example/users/remote_user"
    follow_activity.target_actor_data = {"preferredUsername": "remote_user"}
    
    assert str(follow_activity) == f"Follow by {follow_activity.actor.user.username}: remote_user (remote)"
    assert follow_activity.target_actor_url == "https://remote.example/users/remote_user"
    assert follow_activity.target_actor_data["preferredUsername"] == "remote_user"

# Test string representation for all activity types
def test_activity_str_representation(create_activity, like_activity, follow_activity):
    # Test that all activities include actor's username in their string representation
    for activity in [create_activity, like_activity, follow_activity]:
        assert activity.actor.user.username in str(activity)

# Test visibility field for all activity types
def test_activity_visibility(create_activity, like_activity, follow_activity):
    for activity in [create_activity, like_activity, follow_activity]:
        assert activity.visibility in ["public", "private", "followers-only"]