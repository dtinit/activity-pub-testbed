from testbed.core.models import Actor

def test_create_activity(create_activity):
    assert create_activity.actor is not None
    assert create_activity.visibility in ["public", "private", "followers-only"]
    # Test both cases: with note and without note (Actor creation)
    if create_activity.note:
        assert str(create_activity) == f"Create by {create_activity.actor.user.username}: {create_activity.note}"
    else:
        assert str(create_activity) == f"Create by {create_activity.actor.user.username}: Actor creation"

def test_create_activity_json_ld(create_activity):
    json_ld = create_activity.get_json_ld()
    assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
    assert json_ld["type"] == "Create"
    assert json_ld["actor"] == f"https://example.com/users/{create_activity.actor.user.username}"
    assert json_ld["visibility"] == create_activity.visibility

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
    
    json_ld = like_activity.get_json_ld()
    assert json_ld["object"]["id"] == "https://remote.example/notes/123"
    assert json_ld["object"]["content"] == "Remote content"

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
    
    json_ld = follow_activity.get_json_ld()
    assert json_ld["object"]["id"] == "https://remote.example/users/remote_user"
    assert json_ld["object"]["preferredUsername"] == "remote_user"

def test_activity_str_representation(create_activity, like_activity, follow_activity):
    # Test that all activities include actor's username in their string representation
    for activity in [create_activity, like_activity, follow_activity]:
        assert activity.actor.user.username in str(activity)

def test_activity_json_ld_common_fields(create_activity, like_activity, follow_activity):
    # Test common JSON-LD fields across all activity types
    for activity in [create_activity, like_activity, follow_activity]:
        json_ld = activity.get_json_ld()
        assert json_ld["@context"] == "https://www.w3.org/ns/activitystreams"
        assert "type" in json_ld
        assert json_ld["actor"] == f"https://example.com/users/{activity.actor.user.username}"
        assert "published" in json_ld
        assert json_ld["visibility"] == activity.visibility