"""
Unit tests for Protected Planet API v4 adapter and Geo Agent MPA integration.
"""
import pytest
from app.tools import protected_planet_adapter
from app.agents.geo_agent import check_mpa


@pytest.mark.asyncio
async def test_protected_planet_is_configured():
    assert protected_planet_adapter.is_configured() is True


@pytest.mark.asyncio
async def test_protected_planet_unconfigured(monkeypatch):
    monkeypatch.setattr(protected_planet_adapter.settings, "PROTECTED_PLANET_API_KEY", None)
    assert protected_planet_adapter.is_configured() is False
    res = await protected_planet_adapter.search_protected_areas()
    assert res.get("status") == "unavailable"


@pytest.mark.asyncio
async def test_protected_planet_search():
    res = await protected_planet_adapter.search_protected_areas(country="IND", marine=True)
    assert res.get("status") == "success"
    assert res.get("count", 0) > 0
    names = [pa.get("name_english") or pa.get("name") for pa in res.get("protected_areas", [])]
    assert any("Sundarbans" in n or "Chilika" in n for n in names)


@pytest.mark.asyncio
async def test_protected_planet_get_area():
    # Sundarbans site_id: 14177
    res = await protected_planet_adapter.get_protected_area(14177)
    assert res.get("status") == "success"
    pa = res.get("protected_area", {})
    assert pa.get("site_id") == 14177
    geojson = pa.get("geojson", {})
    assert geojson.get("type") == "Feature"
    assert geojson.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon")


@pytest.mark.asyncio
async def test_geo_agent_check_mpa():
    # Chilika Lake: lat=19.7, lon=85.3 -> should be inside MPA
    chilika = await check_mpa(19.7, 85.3)
    assert chilika.get("status") == "success"
    assert chilika.get("inside_mpa") is True
    assert "Chilika" in chilika.get("name", "")

    # Open Indian Ocean: lat=12.0, lon=85.0 -> should NOT be inside MPA
    open_sea = await check_mpa(12.0, 85.0)
    assert open_sea.get("status") == "success"
    assert open_sea.get("inside_mpa") is False
