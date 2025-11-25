import os
import asyncio
import logging
import json
from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
)

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self):
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            logger.error("DEEPGRAM_API_KEY not found in .env")
            raise ValueError("DEEPGRAM_API_KEY not found")

        self.dg_client = DeepgramClient(self.api_key)
        self.dg_connection = None
        self.is_connected = False
        self.callbacks = []

    def register_callback(self, callback):
        """Register a callback function to receive transcripts."""
        self.callbacks.append(callback)

    async def start(self, source_lang="fr"):
        """Starts the Deepgram Live Transcription connection."""
        if self.is_connected:
            return

        try:
            # Create a websocket connection to Deepgram
            self.dg_connection = self.dg_client.listen.asyncwebsocket.v("1")

            # Define event handlers
            async def on_message(self_handler, result, **kwargs):
                sentence = result.channel.alternatives[0].transcript
                if len(sentence) == 0:
                    return
                
                is_final = result.is_final
                
                # Notify all registered callbacks
                for callback in self.callbacks:
                    await callback(sentence, is_final)

            async def on_error(self_handler, error, **kwargs):
                logger.error(f"Deepgram Error: {error}")

            # Register handlers
            self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)

            # Configure options
            logger.info(f"Connecting to Deepgram with language={source_lang}")
            options = LiveOptions(
                model="nova-2",
                language=source_lang, 
                smart_format=True,
                encoding="linear16",
                channels=1,
                sample_rate=16000,
                interim_results=True,
                utterance_end_ms=1000, # Revert to 1000 to fix HTTP 400
                vad_events=True,
            )

            # Start the connection
            if await self.dg_connection.start(options) is False:
                logger.error("Failed to connect to Deepgram")
                return

            self.is_connected = True
            logger.info("Connected to Deepgram STT")

        except Exception as e:
            logger.error(f"Failed to initialize Deepgram: {e}")
            raise

    async def stop(self):
        """Stops the Deepgram connection."""
        if self.dg_connection:
            await self.dg_connection.finish()
            self.dg_connection = None
        self.is_connected = False
        logger.info("Disconnected from Deepgram")

    async def send_audio(self, audio_data: bytes):
        """Sends audio data to Deepgram."""
        if self.is_connected and self.dg_connection:
            await self.dg_connection.send(audio_data)
