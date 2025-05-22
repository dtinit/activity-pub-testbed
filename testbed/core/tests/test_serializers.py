import pytest
from testbed.core.serializers import ActorSerializer


@pytest.mark.django_db
def test_actor_serializer(actor):
    serializer = ActorSerializer(actor)
    data = serializer.data
    
    assert data["id"] == actor.id
    assert "json_ld" in data
    
    json_ld = data["json_ld"]
    assert json_ld["type"] == "Person"
    assert json_ld["preferredUsername"] == actor.user.username
    assert json_ld["previously"] == actor.previously
