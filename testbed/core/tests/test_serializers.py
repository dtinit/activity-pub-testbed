import pytest
from testbed.core.serializers import ActorSerializer


# Test that the ActorSerializer returns the correct data
@pytest.mark.django_db
def test_actor_serializer(actor):
    serializer = ActorSerializer(actor)
    expected = {
        'id': actor.id,
        'json_ld': actor.get_json_ld(),
    }
    assert serializer.data == expected