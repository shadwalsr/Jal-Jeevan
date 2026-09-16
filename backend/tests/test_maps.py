"""Tests for app/core/maps.py's Google Maps deep-link builder."""
from app.core.maps import google_maps_url


def test_google_maps_url_format():
    url = google_maps_url(17.6935526, 83.2921297)
    assert url == "https://www.google.com/maps/search/?api=1&query=17.6935526,83.2921297"


def test_google_maps_url_handles_negative_coordinates():
    url = google_maps_url(-33.87, 151.21)
    assert "query=-33.87,151.21" in url
