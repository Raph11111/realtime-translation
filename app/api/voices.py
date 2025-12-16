"""
Voices API Endpoint

Provides endpoints to fetch available ElevenLabs voices.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from app.services.tts import TTSService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voices", tags=["voices"])

# Initialize TTS service for voice fetching
_tts_service = None

def get_tts_service():
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service


class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    category: str
    labels: dict = {}
    preview_url: Optional[str] = None


class VoicesResponse(BaseModel):
    voices: List[VoiceInfo]
    total: int


@router.get("", response_model=VoicesResponse)
async def get_voices():
    """
    Get all available ElevenLabs voices.
    
    Returns premade voices and any cloned voices associated with the account.
    Cloned voices appear first in the list.
    """
    tts = get_tts_service()
    
    try:
        voices_data = await tts.get_voices()
        
        voices = [
            VoiceInfo(
                voice_id=v["voice_id"],
                name=v["name"],
                category=v["category"],
                labels=v.get("labels", {}),
                preview_url=v.get("preview_url")
            )
            for v in voices_data
        ]
        
        return VoicesResponse(
            voices=voices,
            total=len(voices)
        )
        
    except Exception as e:
        logger.error(f"Error fetching voices: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch voices")


@router.get("/{voice_id}")
async def get_voice(voice_id: str):
    """Get details for a specific voice."""
    tts = get_tts_service()
    
    try:
        voices_data = await tts.get_voices()
        
        for v in voices_data:
            if v["voice_id"] == voice_id:
                return VoiceInfo(
                    voice_id=v["voice_id"],
                    name=v["name"],
                    category=v["category"],
                    labels=v.get("labels", {}),
                    preview_url=v.get("preview_url")
                )
        
        raise HTTPException(status_code=404, detail="Voice not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching voice: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch voice")
