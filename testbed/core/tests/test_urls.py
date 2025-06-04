from django.urls import reverse, resolve
from django.urls.exceptions import Resolver404
import pytest

# Test actor detail URL patterns
def test_actor_detail_url():
    # Test URL generation
    url = reverse('actor-detail', kwargs={'pk': 1})
    assert url == '/api/actors/1/'
    
    # Test URL resolution
    resolver = resolve("/api/actors/1/")
    assert resolver.view_name == "actor-detail"
    assert resolver.kwargs['pk'] == 1  # URL parameters are integers

# Test outbox detail URL patterns
def test_outbox_detail_url():
    # Test URL generation
    url = reverse('actor-outbox', kwargs={'pk': 1})
    assert url == '/api/actors/1/outbox/'
    
    # Test URL resolution
    resolver = resolve("/api/actors/1/outbox/")
    assert resolver.view_name == "actor-outbox"
    assert resolver.kwargs['pk'] == 1  # URL parameters are integers

# Test that invalid URLs don't resolve
def test_invalid_urls():
    invalid_urls = [
        "/api/actors/",
        "/api/actors/1/invalid/",
        "/api/actors/abc/",  # Non-numeric ID
        "/api/actors//outbox/",  # Missing ID
    ]
    
    for url in invalid_urls:
        with pytest.raises(Resolver404):
            resolve(url)

# Test URL reverse lookup with different inputs
def test_url_reversing():
    # Test with integer ID
    assert reverse('actor-detail', kwargs={'pk': 1}) == '/api/actors/1/'
    
    # Test with string ID (should work the same)
    assert reverse('actor-detail', kwargs={'pk': '1'}) == '/api/actors/1/'
    
    # Test outbox URLs
    assert reverse('actor-outbox', kwargs={'pk': 1}) == '/api/actors/1/outbox/'