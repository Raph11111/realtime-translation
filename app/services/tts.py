import os
import logging
import asyncio
from elevenlabs import ElevenLabs
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        self.elevenlabs_client = None
        self.openai_client = None
        
        # Initialize ElevenLabs
        if self.elevenlabs_api_key:
            try:
                self.elevenlabs_client = ElevenLabs(api_key=self.elevenlabs_api_key)
            except Exception as e:
                logger.error(f"Failed to initialize ElevenLabs client: {e}")
        
        # Initialize OpenAI
        if self.openai_api_key:
            try:
                self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")

        self.callbacks = []
        self.voice_id = "21m00Tcm4TlvDq8ikWAM" 
        self.model_id = "eleven_turbo_v2_5"
        
        # Voice Mapping for OpenAI
        self.voice_mapping = {
            "alloy": "alloy",       # Neutral
            "echo": "echo",         # Male
            "fable": "fable",       # British-ish
            "onyx": "onyx",         # Deep Male
            "nova": "nova",         # Female
            "shimmer": "shimmer"    # Female
        }
        self.default_voice = "alloy"

    def register_callback(self, callback):
        """Register a callback to receive audio chunks."""
        self.callbacks.append(callback)

    async def generate_audio(self, text: str, voice: str = None):
        """Generates audio stream from text, trying ElevenLabs first, then OpenAI."""
        if not text.strip():
            return

        # Map user voice to OpenAI voice ID
        openai_voice = self.voice_mapping.get(voice, self.default_voice)

        # Try ElevenLabs
        if self.elevenlabs_client:
            try:
                logger.info(f"Generating TTS with ElevenLabs for text: '{text[:20]}...'")
                # Use Turbo v2.5 for low latency
                audio_stream = self.elevenlabs_client.generate(
                    text=text,
                    voice=self.voice_id,
                    model="eleven_turbo_v2_5",
                    stream=True
                )
                
                # Stream chunks
                chunk_count = 0
                total_bytes = 0
                for chunk in audio_stream:
                    if chunk:
                        chunk_count += 1
                        total_bytes += len(chunk)
                        for callback in self.callbacks:
                            await callback(chunk)
                logger.info(f"ElevenLabs TTS complete. Sent {chunk_count} chunks, {total_bytes} bytes.")
                return # Success, skip fallback
                
            except Exception as e:
                logger.error(f"ElevenLabs TTS error: {e}. Falling back to OpenAI.")

        # Fallback to OpenAI
        if self.openai_client:
            try:
                response = await self.openai_client.audio.speech.create(
                    model="tts-1",
                    voice=openai_voice,
                    input=text,
                    response_format="mp3"
                )
                
                # OpenAI returns the full binary content (not a generator in the same way for async create?)
                # Actually response.content is bytes.
                # For streaming, we'd need stream=True, but let's just get the chunk for now.
                
                chunk = response.content
                for callback in self.callbacks:
                    await callback(chunk)
                    
            except Exception as e:
                logger.error(f"OpenAI TTS error: {e}")
        else:
            logger.error("No TTS clients available.")

    async def process_translation(self, text: str, voice: str = None):
        """Called when a new translation is received."""
        await self.generate_audio(text, voice)
