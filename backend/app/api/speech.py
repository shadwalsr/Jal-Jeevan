"""
JalJeev backend — Speech-to-text proxy router for Sarvam AI (PRD Section 1 / SIH26176).
Provides voice recognition with maritime keyterms support and domain vocabulary correction.
"""
import asyncio
import json
import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["speech"])

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"

MARITIME_CORRECTIONS = {
    r"\bpara\s+deep\b": "Paradip",
    r"\bpara\s+dip\b": "Paradip",
    r"\bparadip\s+port\b": "Paradip",
    r"\bcochin\b": "Kochi",
    r"\bvizag\b": "Visakhapatnam",
    r"\bvishakhapatnam\b": "Visakhapatnam",
    r"\bvishakha\b": "Visakhapatnam",
    r"\bjnpt\b": "JNPT",
    r"\bnhava\s+sheva\b": "Nhava Sheva",
    r"\bhaldia\s+port\b": "Haldia",
    r"\bkakinada\s+port\b": "Kakinada",
    r"\bpfz\b": "PFZ",
    r"\bincois\b": "INCOIS",
    r"\bmosdac\b": "MOSDAC",
    r"\bisro\b": "ISRO",
    r"\bjal\s*jeev\b": "JalJeev",
}

DEFAULT_KEYTERMS = [
    "Paradip", "Haldia", "Kolkata", "Dhamra", "Gopalpur",
    "Visakhapatnam", "Kakinada", "Gangavaram", "Krishnapatnam",
    "Chennai", "Ennore", "Tuticorin", "Kochi", "Mangaluru",
    "New Mangalore", "Mundra", "Kandla", "Pipavav", "Dahej",
    "Hazira", "Mumbai", "JNPT", "Nhava Sheva", "Mormugao",
    "Goa Port", "Karaikal", "Nagapattinam", "Cuddalore",
    "trawler", "gillnet", "purse seine", "dhow", "catamaran",
    "mechanized boat", "country boat", "fishing vessel",
    "draft", "freeboard", "squat", "UKC", "ballast",
    "significant wave height", "swell", "wave period",
    "cyclone", "depression", "trough", "storm surge",
    "Potential Fishing Zone", "PFZ", "EEZ"
]


def apply_maritime_corrections(text: str) -> str:
    """Correct frequent phonetic mishearings for Indian ports and maritime terms."""
    result = text
    for pattern, replacement in MARITIME_CORRECTIONS.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


class TranscribeResponse(BaseModel):
    transcript: str
    language_code: Optional[str] = None


class TranslateTextRequest(BaseModel):
    text: str
    target_language: str = "English"


class TranslateTextResponse(BaseModel):
    translated_text: str
    original_text: str


@router.post("/speech/translate-text", response_model=TranslateTextResponse)
@router.post("/api/speech/translate-text", response_model=TranslateTextResponse)
async def translate_text(req: TranslateTextRequest):
    """Translate regional text to English or chosen target language."""
    from app.planner.graph import _call_llm
    prompt = (
        f"Translate the following marine/coastal user query into {req.target_language}. "
        f"Output ONLY the translated text with no extra commentary or markdown formatting:\n"
        f"{req.text}"
    )
    ans, _ = await _call_llm(prompt)
    if ans:
        clean = ans.strip().strip('"').strip("'")
        return TranslateTextResponse(translated_text=clean, original_text=req.text)
    return TranslateTextResponse(translated_text=req.text, original_text=req.text)


@router.post("/speech/transcribe", response_model=TranscribeResponse)
@router.post("/api/speech/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str = Form("saaras:v4"),
    language_code: str = Form("unknown"),
    mode: str = Form("transcribe"),
    with_timestamps: str = Form("false"),
    keyterms: Optional[str] = Form(None),
):
    """
    Transcribe audio stream to text using Sarvam AI saaras:v4 model.
    Applies maritime terms and post-processing phonetic corrections.
    """
    if model in ("saaras:v2", "saaras:v2.5", "saaras:v3"):
        model = "saaras:v4"
    if not settings.SARVAM_API_KEY:
        logger.error("SARVAM_API_KEY is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sarvam AI service is not configured on this server.",
        )

    audio_bytes = await file.read()
    if len(audio_bytes) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio recording is too short or empty.",
        )

    # Prepare keyterms JSON array
    keyterms_val = keyterms
    if not keyterms_val:
        keyterms_val = json.dumps(DEFAULT_KEYTERMS[:50])

    # Sarvam STT uses od-IN for Odia
    if language_code == "or-IN":
        language_code = "od-IN"

    data_payload = {
        "model": model,
        "language_code": language_code,
        "mode": mode,
        "with_timestamps": with_timestamps,
        "keyterms": keyterms_val,
    }

    files = {
        "file": (file.filename or "audio.wav", audio_bytes, file.content_type or "audio/wav")
    }
    headers = {
        "api-subscription-key": settings.SARVAM_API_KEY,
    }

    # Attempt call with single 429 retry
    async with httpx.AsyncClient(timeout=35.0) as client:
        resp = None
        for attempt in range(2):
            try:
                resp = await client.post(
                    SARVAM_STT_URL,
                    data=data_payload,
                    files=files,
                    headers=headers,
                )
                if resp.status_code == 429 and attempt == 0:
                    logger.warning("Sarvam API 429 received, retrying after 2s...")
                    await asyncio.sleep(2.0)
                    continue
                break
            except httpx.RequestError as exc:
                if attempt == 0:
                    logger.warning(f"Sarvam connection attempt 1 failed: {exc}, retrying...")
                    await asyncio.sleep(1.0)
                    continue
                logger.error(f"Sarvam API connection error: {exc}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to connect to Sarvam AI speech service: {exc}",
                )

        if resp is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No response received from Sarvam AI",
            )

        if resp.status_code != 200:
            logger.error(f"Sarvam API returned error {resp.status_code}: {resp.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Sarvam AI speech recognition error: {resp.status_code} {resp.text}",
            )

        sarvam_data = resp.json()
        raw_transcript = sarvam_data.get("transcript", "")
        detected_lang = sarvam_data.get("language_code", language_code)

        corrected = apply_maritime_corrections(raw_transcript)

        return TranscribeResponse(
            transcript=corrected,
            language_code=detected_lang,
        )


class TTSRequest(BaseModel):
    text: str
    language_code: Optional[str] = "hi-IN"
    speaker: Optional[str] = "shubh"
    pace: Optional[float] = 1.0


class TTSResponse(BaseModel):
    audio_base64: str
    language_code: str
    format: str = "wav"


def clean_text_for_speech(text: str) -> str:
    """Clean markdown and special symbols so speech synthesis sounds fluent and natural."""
    # Remove markdown links [text](url) -> text
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove URLs
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    # Remove markdown bold/italics
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
    # Remove markdown headers
    cleaned = re.sub(r'#+\s*', '', cleaned)
    # Remove markdown bullet points
    cleaned = re.sub(r'^\s*[-*•]\s+', '', cleaned, flags=re.MULTILINE)
    # Remove backticks
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
    # Clean newlines into sentence stops
    cleaned = re.sub(r'\n+', '. ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Limit to reasonable sentence length for TTS
    if len(cleaned) > 1200:
        cut = cleaned[:1200]
        last_period = max(cut.rfind('.'), cut.rfind('।'))
        if last_period > 600:
            cleaned = cut[:last_period + 1]
        else:
            cleaned = cut + "..."
    return cleaned


SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"


@router.post("/speech/tts", response_model=TTSResponse)
@router.post("/api/speech/tts", response_model=TTSResponse)
async def text_to_speech(req: TTSRequest):
    """
    Synthesize regional language text to speech audio using Sarvam AI bulbul:v3 model.
    Returns base64 encoded WAV audio.
    """
    if not settings.SARVAM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sarvam AI service is not configured on this server.",
        )

    clean_text = clean_text_for_speech(req.text)
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text to synthesize is empty.",
        )

    lang = req.language_code or "hi-IN"
    if lang in ("or", "or-IN", "od"):
        lang = "od-IN"
    elif "-" not in lang:
        candidate = f"{lang}-IN"
        if candidate in ("hi-IN", "ta-IN", "te-IN", "bn-IN", "ml-IN", "gu-IN", "mr-IN", "kn-IN", "en-IN"):
            lang = candidate

    payload = {
        "text": clean_text,
        "language_code": lang,
        "speaker": req.speaker or "shubh",
        "model": "bulbul:v3",
    }
    headers = {
        "api-subscription-key": settings.SARVAM_API_KEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(SARVAM_TTS_URL, json=payload, headers=headers)
        except httpx.RequestError as exc:
            logger.error(f"Sarvam TTS connection error: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to Sarvam TTS service: {exc}",
            )

        if resp.status_code != 200:
            logger.error(f"Sarvam TTS returned error {resp.status_code}: {resp.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Sarvam TTS error: {resp.status_code} {resp.text}",
            )

        data = resp.json()
        audios = data.get("audios", [])
        if not audios:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No audio returned from Sarvam TTS",
            )

        return TTSResponse(
            audio_base64=audios[0],
            language_code=lang,
            format="wav",
        )

