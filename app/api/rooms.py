"""
Room API Endpoints

REST and WebSocket endpoints for managing translation rooms:
- Create/close rooms
- List rooms
- Generate QR codes for joining
- Listener WebSocket connections
"""

import os
import io
import json
import asyncio
import logging
from typing import Optional, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.room_manager import room_manager, TranslationRoom
from app.services.parallel_translation import parallel_translation_service, LANGUAGE_CODE_TO_NAME
from app.services.tts import TTSService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


# -------------------- Pydantic Models --------------------

class CreateRoomRequest(BaseModel):
    room_name: str
    source_language: str = "auto"
    host_id: Optional[str] = None


class CreateRoomResponse(BaseModel):
    room_id: str
    room_name: str
    join_url: str
    qr_url: str


class RoomStats(BaseModel):
    room_id: str
    room_name: str
    source_language: str
    is_active: bool
    total_listeners: int
    channels: dict


class ChannelConfig(BaseModel):
    target_language: str
    voice: str = "alloy"


# -------------------- REST Endpoints --------------------

@router.post("", response_model=CreateRoomResponse)
async def create_room(request: CreateRoomRequest):
    """Create a new translation room."""
    import secrets
    
    host_id = request.host_id or secrets.token_urlsafe(8)
    
    room = room_manager.create_room(
        room_name=request.room_name,
        host_id=host_id,
        source_language=request.source_language
    )
    
    # Build URLs
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    join_url = f"{base_url}/join/{room.room_id}"
    qr_url = f"{base_url}/api/rooms/{room.room_id}/qr"
    
    return CreateRoomResponse(
        room_id=room.room_id,
        room_name=room.room_name,
        join_url=join_url,
        qr_url=qr_url
    )


@router.get("", response_model=List[RoomStats])
async def list_rooms(active_only: bool = True):
    """List all translation rooms."""
    rooms = room_manager.list_rooms(active_only=active_only)
    return rooms


@router.get("/{room_id}", response_model=RoomStats)
async def get_room(room_id: str):
    """Get room details."""
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room.get_stats()


@router.delete("/{room_id}")
async def close_room(room_id: str):
    """Close a translation room."""
    success = room_manager.close_room(room_id)
    if not success:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"status": "success", "message": f"Room {room_id} closed"}


@router.get("/{room_id}/qr")
async def get_room_qr(room_id: str):
    """Generate QR code for joining a room."""
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    try:
        import qrcode
        from qrcode.image.styledpil import StyledPilImage
        from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
        from qrcode.image.styles.colormasks import SolidFillColorMask
    except ImportError:
        # Fallback simple QR if styled version not available
        try:
            import qrcode
        except ImportError:
            raise HTTPException(
                status_code=500, 
                detail="QR code generation not available. Install qrcode: pip install qrcode[pil]"
            )
    
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    join_url = f"{base_url}/join/{room_id}"
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(join_url)
    qr.make(fit=True)
    
    # Create image
    try:
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            color_mask=SolidFillColorMask(
                back_color=(255, 255, 255),
                front_color=(112, 0, 255)  # Purple-ish
            )
        )
    except:
        img = qr.make_image(fill_color="purple", back_color="white")
    
    # Save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="image/png")


@router.get("/{room_id}/languages")
async def get_available_languages(room_id: str):
    """Get list of supported languages for translation."""
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    return {
        "available": LANGUAGE_CODE_TO_NAME,
        "active_channels": list(room.channels.keys())
    }


# -------------------- WebSocket for Room Host --------------------

@router.websocket("/{room_id}/host")
async def room_host_websocket(websocket: WebSocket, room_id: str):
    """
    WebSocket for room host.
    
    Receives:
    - transcript: {type: "transcript", text: str, is_final: bool}
    - config: {type: "config", languages: [str], voices: {lang: voice}}
    
    Sends:
    - stats: {type: "stats", ...room_stats}
    """
    room = room_manager.get_room(room_id)
    if not room:
        await websocket.close(code=4004, reason="Room not found")
        return
    
    await websocket.accept()
    logger.info(f"Host connected to room: {room_id}")
    
    # Track active languages for this room
    active_languages: List[str] = []
    voices: dict = {}
    
    # TTS instances per language
    tts_services: dict[str, TTSService] = {}
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")
            
            if msg_type == "config":
                # Update active languages and voices
                active_languages = message.get("languages", active_languages)
                voices = message.get("voices", voices)
                
                # Ensure channels exist
                for lang in active_languages:
                    room.get_or_create_channel(lang, voices.get(lang, "alloy"))
                    if lang not in tts_services:
                        tts_services[lang] = TTSService()
                
                logger.info(f"Room {room_id} configured with languages: {active_languages}")
                
                # Send confirmation
                await websocket.send_text(json.dumps({
                    "type": "config_confirmed",
                    "languages": active_languages
                }))
            
            elif msg_type == "transcript":
                text = message.get("text", "")
                is_final = message.get("is_final", False)
                
                if is_final and text.strip():
                    # Broadcast original transcript to all channels
                    await room_manager.broadcast_transcript_to_room(room_id, text, is_final)
                    
                    # Translate to all active languages in parallel
                    if active_languages:
                        translations = await parallel_translation_service.translate_parallel(
                            text, 
                            active_languages,
                            voices
                        )
                        
                        # Generate TTS and broadcast for each language
                        async def process_language(lang: str, translated: str):
                            if not translated:
                                return
                            
                            # Broadcast translation text
                            await room_manager.broadcast_translation_to_channel(
                                room_id, lang, translated
                            )
                            
                            # Generate and broadcast TTS
                            tts = tts_services.get(lang)
                            if tts:
                                audio = await generate_audio_for_channel(
                                    tts, translated, voices.get(lang, "alloy")
                                )
                                if audio:
                                    await room_manager.broadcast_audio_to_channel(
                                        room_id, lang, audio
                                    )
                        
                        # Process all languages in parallel
                        await asyncio.gather(*[
                            process_language(lang, trans)
                            for lang, trans in translations.items()
                            if trans
                        ])
            
            elif msg_type == "stats_request":
                # Send room stats
                await websocket.send_text(json.dumps({
                    "type": "stats",
                    **room.get_stats()
                }))
                
    except WebSocketDisconnect:
        logger.info(f"Host disconnected from room: {room_id}")
    except Exception as e:
        logger.error(f"Host WebSocket error: {e}")


async def generate_audio_for_channel(tts: TTSService, text: str, voice: str) -> Optional[bytes]:
    """Generate TTS audio for a text."""
    if not text.strip():
        return None
    
    audio_buffer = bytearray()
    
    async def collect_audio(chunk: bytes):
        audio_buffer.extend(chunk)
    
    # Temporarily register callback
    original_callbacks = tts.callbacks
    tts.callbacks = [collect_audio]
    
    try:
        await tts.generate_audio(text, voice)
    finally:
        tts.callbacks = original_callbacks
    
    return bytes(audio_buffer) if audio_buffer else None


# -------------------- WebSocket for Listeners --------------------

@router.websocket("/{room_id}/listen/{language}")
async def listener_websocket(
    websocket: WebSocket, 
    room_id: str, 
    language: str,
    voice: str = Query(default="alloy")
):
    """
    WebSocket for listeners.
    
    Receives audio and text for their selected language.
    """
    room = room_manager.get_room(room_id)
    if not room:
        await websocket.close(code=4004, reason="Room not found")
        return
    
    if not room.is_active:
        await websocket.close(code=4005, reason="Room is closed")
        return
    
    await websocket.accept()
    
    # Add listener to channel
    success = await room_manager.add_listener(room_id, language, websocket, voice)
    if not success:
        await websocket.close(code=4006, reason="Failed to join channel")
        return
    
    logger.info(f"Listener joined room {room_id}, language: {language}")
    
    # Send welcome message
    await websocket.send_text(json.dumps({
        "type": "welcome",
        "room_id": room_id,
        "room_name": room.room_name,
        "language": language,
        "source_language": room.source_language
    }))
    
    try:
        # Keep connection alive and handle any client messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
            except asyncio.TimeoutError:
                # Send keepalive
                try:
                    await websocket.send_text(json.dumps({"type": "keepalive"}))
                except:
                    break
                    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Listener WebSocket error: {e}")
    finally:
        room_manager.remove_listener(room_id, language, websocket)
        logger.info(f"Listener left room {room_id}, language: {language}")
