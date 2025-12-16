import os
import logging
import asyncio
from elevenlabs import AsyncElevenLabs

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        
        self.elevenlabs_client = None
        
        # Initialize ElevenLabs
        if self.elevenlabs_api_key:
            try:
                self.elevenlabs_client = AsyncElevenLabs(api_key=self.elevenlabs_api_key)
                logger.info("ElevenLabs client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize ElevenLabs client: {e}")
        else:
            logger.warning("ELEVENLABS_API_KEY not found. TTS will be disabled.")

        self.callbacks = []
        
        # ElevenLabs Flash v2.5 - lowest latency (~75ms)
        self.model_id = "eleven_flash_v2_5"
        
        # Default voice ID (Rachel - calm, professional)
        self.default_voice_id = "21m00Tcm4TlvDq8ikWAM"

    def register_callback(self, callback):
        """Register a callback to receive audio chunks."""
        self.callbacks.append(callback)

    async def get_voices(self):
        """Fetch all available ElevenLabs voices (premade + cloned)."""
        if not self.elevenlabs_client:
            return []
        
        try:
            response = await self.elevenlabs_client.voices.get_all()
            voices = []
            
            for voice in response.voices:
                voice_data = {
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "category": voice.category or "premade",
                    "labels": voice.labels if hasattr(voice, 'labels') and voice.labels else {},
                    "preview_url": voice.preview_url if hasattr(voice, 'preview_url') else None
                }
                voices.append(voice_data)
            
            # Sort: cloned voices first, then by name
            voices.sort(key=lambda v: (0 if v["category"] == "cloned" else 1, v["name"]))
            
            logger.info(f"Fetched {len(voices)} voices from ElevenLabs")
            return voices
            
        except Exception as e:
            logger.error(f"Error fetching voices: {e}")
            return []

    async def generate_audio(self, text: str, voice_id: str = None):
        """Generates audio from text using ElevenLabs TTS with streaming."""
        if not text.strip():
            return

        # Use provided voice_id or default
        voice = voice_id or self.default_voice_id

        if self.elevenlabs_client:
            try:
                logger.info(f"Generating TTS with ElevenLabs Flash v2.5, voice: {voice}")
                
                # Buffer complete audio for smooth playback
                audio_buffer = bytearray()
                
                # Use streaming for lowest latency
                audio_stream = self.elevenlabs_client.text_to_speech.convert(
                    voice_id=voice,
                    text=text,
                    model_id=self.model_id,
                    output_format="mp3_44100_64"  # Good quality, web-compatible
                )
                
                # Collect all chunks
                async for chunk in audio_stream:
                    if chunk:
                        audio_buffer.extend(chunk)
                
                # Send complete audio as one chunk
                if audio_buffer:
                    complete_audio = bytes(audio_buffer)
                    logger.info(f"Sending ElevenLabs audio: {len(complete_audio)} bytes")
                    for callback in self.callbacks:
                        await callback(complete_audio)
                return
                
            except Exception as e:
                logger.error(f"ElevenLabs TTS error: {e}")
        
        logger.error("TTS generation failed or no client available.")

    async def process_translation(self, text: str, voice_id: str = None):
        """Called when a new translation is received."""
        await self.generate_audio(text, voice_id)
