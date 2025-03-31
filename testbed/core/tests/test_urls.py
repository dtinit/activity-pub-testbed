from django.urls import resolve


# Test that the Actor detail URL resolves correctly
def test_actor_detail_url():
    resolver = resolve("/api/actors/1/")
    assert resolver.view_name == "actor-detail"


# Test that the PortabilityOutbox URL resolves correctly
def test_outbox_detail_url():
    resolver = resolve("/api/actors/1/outbox/")
    assert resolver.view_name == "actor-outbox"
