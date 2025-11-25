import os
import asyncio
import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

from app.services.audio_capture import AudioCaptureService
from app.services.transcription import TranscriptionService
from app.services.translation import TranslationService
from app.services.tts import TTSService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service instances
audio_service = AudioCaptureService()
transcription_service = TranscriptionService()
translation_service = TranslationService()
tts_service = TTSService()

# Global list of connected transcript clients
transcript_clients = set()

async def broadcast_transcript(text: str, is_final: bool):
    """Callback to broadcast transcripts to connected clients."""
    # 1. Broadcast original transcript
    if transcript_clients:
        message = json.dumps({
            "type": "transcript",
            "text": text,
            "is_final": is_final
        })
        
        disconnected_clients = set()
        for client in transcript_clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected_clients.add(client)
        
        for client in disconnected_clients:
            transcript_clients.remove(client)

    # 2. Send to Translation Service
    await translation_service.process_transcript(text, is_final)

async def broadcast_translation(text: str, voice: str = None):
    """Callback to broadcast translations to connected clients."""
    logger.info(f"Broadcasting translation: '{text[:20]}...' with voice: {voice}")
    # 1. Broadcast text translation
    if transcript_clients:
        message = json.dumps({
            "type": "translation",
            "text": text
        })
        
        disconnected_clients = set()
        for client in transcript_clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected_clients.add(client)
                
        for client in disconnected_clients:
            transcript_clients.remove(client)

    # 2. Send to TTS Service
    await tts_service.process_translation(text, voice)

async def broadcast_audio(chunk: bytes):
    """Callback to broadcast TTS audio to connected clients."""
    if not transcript_clients:
        logger.warning(f"Audio generated ({len(chunk)} bytes) but no clients connected!")
        return

    logger.info(f"Broadcasting audio chunk ({len(chunk)} bytes) to {len(transcript_clients)} clients")
    disconnected_clients = set()
    for client in transcript_clients:
        try:
            await client.send_bytes(chunk)
        except Exception:
            disconnected_clients.add(client)
            
    for client in disconnected_clients:
        transcript_clients.remove(client)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("System starting up...")
    
    # Register callbacks
    transcription_service.register_callback(broadcast_transcript)
    translation_service.register_callback(broadcast_translation)
    tts_service.register_callback(broadcast_audio)
    
    try:
        # Start services
        await transcription_service.start(source_lang="fr")
        await audio_service.start_stream()
        
        # Start background task to feed audio to transcription
        asyncio.create_task(feed_audio_to_transcription())
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
    
    yield
    
    # Shutdown logic
    logger.info("System shutting down...")
    audio_service.stop_stream()
    await transcription_service.stop()

async def feed_audio_to_transcription():
    """Background task to pipe audio from capture to transcription."""
    logger.info("Starting audio feed to transcription engine")
    while True:
        try:
            chunk = await audio_service.get_audio_chunk()
            if chunk:
                await transcription_service.send_audio(chunk)
        except Exception as e:
            logger.error(f"Error feeding audio to transcription: {e}")
            await asyncio.sleep(0.01) # Short sleep to prevent tight loop on error

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Sermon Translator", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

from fastapi.responses import FileResponse

@app.get("/")
async def root():
    return FileResponse("app/static/index.html")

@app.websocket("/ws/audio")
async def audio_websocket(websocket: WebSocket):
    """
    WebSocket endpoint that streams audio from the server's microphone
    to the connected client (for monitoring/debugging).
    """
    await websocket.accept()
    logger.info("Client connected to audio stream")
    
    try:
        while True:
            # Get audio chunk from the capture service (this might steal from the transcription loop if not careful)
            # NOTE: audio_service.queue.get() removes the item. We need a way to fan-out.
            # For now, let's just say this endpoint is for DEBUG and might interfere if we don't fix the queue.
            # ACTUALLY: The feed_audio_to_transcription consumes the queue. 
            # This endpoint will hang if we don't change the architecture to multicast.
            # For simplicity in this step, I will disable the audio output here or just send a "ping".
            
            # TODO: Implement proper multicast queue if we want to listen AND transcribe.
            await asyncio.sleep(1) 
            
    except WebSocketDisconnect:
        logger.info("Client disconnected")

@app.websocket("/ws/transcripts")
async def transcript_websocket(websocket: WebSocket):
    """
    WebSocket endpoint that streams transcripts to the client.
    Also handles configuration messages from the client.
    """
    await websocket.accept()
    transcript_clients.add(websocket)
    logger.info("Client connected to transcripts")
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "config":
                    # Handle configuration changes
                    if "target_lang" in message:
                        new_lang = message["target_lang"]
                        logger.info(f"Client requested target language change to: {new_lang}")
                        translation_service.default_target_lang = new_lang
                    
                    if "target_voice" in message:
                        new_voice = message["target_voice"]
                        logger.info(f"Client requested target voice change to: {new_voice}")
                        # Store voice in translation service (or pass it dynamically)
                        # For simplicity, we'll add a default_voice attribute to TranslationService
                        translation_service.default_target_voice = new_voice
                        
            except json.JSONDecodeError:
                pass # Keep alive ping
                
    except WebSocketDisconnect:
        logger.info("Client disconnected from transcripts")
        transcript_clients.remove(websocket)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
