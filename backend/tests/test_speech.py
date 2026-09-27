"""
Unit tests for the speech proxy endpoint and maritime vocabulary corrections.
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import Response
from starlette.testclient import TestClient

from app.api.speech import apply_maritime_corrections
from app.main import app


def test_apply_maritime_corrections():
    raw = "Show me conditions near para deep and cochin with vizag port"
    corrected = apply_maritime_corrections(raw)
    assert "Paradip" in corrected
    assert "Kochi" in corrected
    assert "Visakhapatnam" in corrected
    assert "para deep" not in corrected
    assert "cochin" not in corrected


def test_apply_maritime_corrections_case_insensitive():
    raw = "Is it safe around HALDIA PORT or Nhava Sheva?"
    corrected = apply_maritime_corrections(raw)
    assert "Haldia" in corrected
    assert "Nhava Sheva" in corrected


@pytest.mark.asyncio
async def test_transcribe_endpoint_success():
    client = TestClient(app)

    mock_sarvam_response = Response(
        status_code=200,
        json={"transcript": "Heading out from para deep to vizag", "language_code": "en-IN"},
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_sarvam_response

        wav_bytes = b"RIFF" + b"\x00" * 200  # Fake wav content
        files = {"file": ("test.wav", wav_bytes, "audio/wav")}
        data = {"language_code": "en-IN"}

        resp = client.post("/speech/transcribe", files=files, data=data)
        assert resp.status_code == 200
        res_json = resp.json()
        assert res_json["transcript"] == "Heading out from Paradip to Visakhapatnam"
        assert res_json["language_code"] == "en-IN"


@pytest.mark.asyncio
async def test_transcribe_endpoint_429_retry():
    client = TestClient(app)

    mock_429 = Response(status_code=429, json={"error": "Rate limit"})
    mock_200 = Response(
        status_code=200,
        json={"transcript": "Safe fishing in cochin", "language_code": "ml-IN"},
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # First call fails with 429, second succeeds
        mock_post.side_effect = [mock_429, mock_200]

        wav_bytes = b"RIFF" + b"\x00" * 200
        files = {"file": ("test.wav", wav_bytes, "audio/wav")}

        resp = client.post("/speech/transcribe", files=files)
        assert resp.status_code == 200
        assert mock_post.call_count == 2
        res_json = resp.json()
        assert res_json["transcript"] == "Safe fishing in Kochi"


@pytest.mark.asyncio
async def test_tts_endpoint_success():
    client = TestClient(app)

    mock_tts_response = Response(
        status_code=200,
        json={"request_id": "req-123", "audios": ["UklGRfakeaudiobase64"]},
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_tts_response

        resp = client.post("/speech/tts", json={
            "text": "**Wave height:** 1.2 m. Low risk zone near Paradip.",
            "language_code": "od-IN",
        })
        assert resp.status_code == 200
        res_json = resp.json()
        assert res_json["audio_base64"] == "UklGRfakeaudiobase64"
        assert res_json["language_code"] == "od-IN"
        assert res_json["format"] == "wav"


def test_clean_text_for_speech():
    from app.api.speech import clean_text_for_speech
    raw = "**Wave height:** 1.5 m\n- Wind speed: 12 kt\n[View maps](https://maps.google.com)\n### Summary\n`Safe` to sail."
    cleaned = clean_text_for_speech(raw)
    assert "**" not in cleaned
    assert "https://" not in cleaned
    assert "###" not in cleaned
    assert "`" not in cleaned
    assert "Wave height: 1.5 m" in cleaned


def test_detect_regional_script():
    from app.planner.graph import detect_regional_script
    assert detect_regional_script("ଆସନ୍ତାକାଲି ପୁରୀରେ ମାଛ ଧରିବା ସୁରକ୍ଷିତ କି?") == "od"
    assert detect_regional_script("क्या आज मछली पकड़ना सुरक्षित है?") == "hi"
    assert detect_regional_script("சென்னையில் இன்று கடல் எப்படி இருக்கிறது?") == "ta"
    assert detect_regional_script("విశాఖపట్నం లో వాతావరణం ఎలా ఉంది?") == "te"
    assert detect_regional_script("Is it safe to fish today?") is None

