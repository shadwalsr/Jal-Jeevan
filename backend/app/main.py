"""
JalJeev backend — FastAPI entrypoint.
Phase 0 scope: health check + a couple of raw data-adapter test endpoints
so the team can confirm INCOIS/IMD connectivity before the agent layer exists.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.chat import router as chat_router
from app.api.map import router as map_router
from app.api.marine import router as marine_router
from app.core.config import settings
from app.tools.incois_adapter import get_incois_wave_forecast
from app.tools.imd_adapter import get_imd_current_weather

# Rate limiting (readiness-audit item): protects both this API and every
# upstream source it calls — an unthrottled caller here previously meant an
# unthrottled caller against Copernicus/Open-Meteo too, contributing to the
# throttling/slowdowns observed during development. Per-IP, in-memory (fine
# for a single-process dev/demo deployment; swap the storage backend for a
# multi-worker production deployment — see slowapi's Redis storage option).
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="JalJeev API",
    description="Agentic Marine Intelligence System — SIH26176",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Dev-only wide-open CORS so the Vite frontend (localhost:5173) can call this
# API (localhost:8000) during development. Tighten to an explicit allowlist
# before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENV == "development" else [],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(marine_router)
app.include_router(chat_router)
app.include_router(map_router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.ENV}


@app.get("/debug/incois/wave")
async def debug_incois_wave(lat: float, lon: float):
    """Sanity-check endpoint for the INCOIS ERDDAP adapter (no auth required)."""
    return await get_incois_wave_forecast(lat, lon)


@app.get("/debug/imd/weather")
async def debug_imd_weather(lat: float, lon: float):
    """Sanity-check endpoint for the IMD adapter (requires IMD_API_KEY in .env)."""
    return await get_imd_current_weather(lat, lon)
