def test_activity_str_representation(create_activity, like_activity, follow_activity):
    # Test CreateActivity
    assert f"Create by {create_activity.actor.username}" in str(create_activity)

    # Test LikeActivity
    assert f"Like by {like_activity.actor.username}" in str(like_activity)

    # Test FollowActivity
    assert f"Follow by {follow_activity.actor.username}" in str(follow_activity)
    assert follow_activity.target_actor.username in str(follow_activity)
