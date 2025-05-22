from django.urls import resolve, reverse
from django.urls.exceptions import Resolver404
import pytest


def test_actor_detail_url():
    url = reverse('actor-detail', kwargs={'pk': 1})
    assert url == '/api/actors/1/'
    
    resolver = resolve("/api/actors/1/")
    assert resolver.view_name == "actor-detail"
    assert resolver.kwargs['pk'] == 1  # Compare as integer


def test_outbox_detail_url():
    url = reverse('actor-outbox', kwargs={'pk': 1})
    assert url == '/api/actors/1/outbox/'
    
    resolver = resolve("/api/actors/1/outbox/")
    assert resolver.view_name == "actor-outbox"
    assert resolver.kwargs['pk'] == 1  # Compare as integer


def test_url_patterns():
    # Test invalid URLs return 404
    with pytest.raises(Resolver404):
        resolve("/api/actors/")
    with pytest.raises(Resolver404):
        resolve("/api/actors/1/invalid/")