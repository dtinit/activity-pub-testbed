

def test_create_activity(create_activity):
    assert create_activity.actor is not None
    assert create_activity.visibility in ['public', 'private', 'followers-only']
    # Note is optional for CreateActivity (can be None for Actor creation)

def test_like_activity(like_activity):
    assert like_activity.actor is not None
    assert like_activity.note is not None # Required for Like
    assert like_activity.visibility in ['public', 'private', 'followers-only']

def test_follow_activity(follow_activity):
    assert follow_activity.actor is not None
    assert follow_activity.target_actor is not None # Required for Follow
    assert follow_activity.visibility in ['public', 'private', 'followers-only']

def test_activity_str_representation(create_activity, like_activity, follow_activity):
    for activity in [create_activity, like_activity, follow_activity]:
        assert activity.actor.username in str(activity)
