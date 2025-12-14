import os
import logging
import asyncio
from elevenlabs import AsyncElevenLabs
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
                self.elevenlabs_client = AsyncElevenLabs(api_key=self.elevenlabs_api_key)
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
        self.model_id = "tts-1-hd"
        
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
        """Generates audio from text using OpenAI TTS-1-HD."""
        if not text.strip():
            return

        # Map user voice to OpenAI voice ID
        openai_voice = self.voice_mapping.get(voice, self.default_voice)

        if self.openai_client:
            try:
                # Buffer complete audio before sending to avoid choppy playback
                audio_buffer = bytearray()
                
                async with self.openai_client.audio.speech.with_streaming_response.create(
                    model=self.model_id,  # tts-1-hd
                    voice=openai_voice,
                    input=text,
                    response_format="mp3"
                ) as response:
                    async for chunk in response.iter_bytes():
                        if chunk:
                            audio_buffer.extend(chunk)
                
                # Send complete audio as one chunk
                if audio_buffer:
                    complete_audio = bytes(audio_buffer)
                    logger.info(f"Sending complete audio: {len(complete_audio)} bytes")
                    for callback in self.callbacks:
                        await callback(complete_audio)
                return
            except Exception as e:
                logger.error(f"OpenAI TTS error: {e}")
        
        logger.error("TTS generation failed or no client available.")

    async def process_translation(self, text: str, voice: str = None):
        """Called when a new translation is received."""
        await self.generate_audio(text, voice)
