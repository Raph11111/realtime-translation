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

    def register_callback(self, callback):
        """Register a callback to receive audio chunks."""
        self.callbacks.append(callback)

    async def generate_audio(self, text: str):
        """Generates audio stream from text, trying ElevenLabs first, then OpenAI."""
        if not text.strip():
            return

        # Try ElevenLabs
        if self.elevenlabs_client:
            try:
                loop = asyncio.get_running_loop()
                def _stream_generator():
                    return self.elevenlabs_client.text_to_speech.convert(
                        text=text,
                        voice_id=self.voice_id,
                        model_id=self.model_id,
                        output_format="mp3_44100_128"
                    )
                
                audio_stream = await loop.run_in_executor(None, _stream_generator)
                for chunk in audio_stream:
                    if chunk:
                        for callback in self.callbacks:
                            await callback(chunk)
                return # Success
            except Exception as e:
                logger.error(f"ElevenLabs TTS error: {e}. Falling back to OpenAI.")

        # Fallback to OpenAI
        if self.openai_client:
            try:
                response = await self.openai_client.audio.speech.create(
                    model="tts-1",
                    voice="alloy",
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

    async def process_translation(self, text: str):
        """Called when a new translation is received."""
        await self.generate_audio(text)
