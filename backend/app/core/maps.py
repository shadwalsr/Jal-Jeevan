"""
Deterministic Google Maps deep-link builder. No LLM involved — a URL built
from a lat/lon we already computed is not something to hand to a model
(see CLAUDE.md's core philosophy: the LLM never computes anything, only
phrases what it's given).

Uses the `?api=1&query=lat,lon` search form (not a raw `/maps?q=` link) —
this is Google's documented stable deep-link format: it drops a pin at the
exact coordinates on web, and hands off to the Google Maps app on mobile if
installed, both without needing a place name.
"""


def google_maps_url(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
