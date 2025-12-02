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
        self.last_source_lang = source_lang # Save for reconnection
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
                # Attempt reconnect on error
                self.is_connected = False
                # We don't await here to avoid blocking the error handler, 
                # but in a real app we might want a background task for reconnection.

            # Register handlers
            self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)
            # self.dg_connection.on(LiveTranscriptionEvents.Close, on_close) # Deepgram SDK might not expose Close event easily in this version

            # Configure options
            logger.info(f"Connecting to Deepgram with language={source_lang}")
            options = LiveOptions(
                model="nova-2",
                language=source_lang, 
                smart_format=True,
                encoding="linear16",
                channels=2,
                sample_rate=44100,
                interim_results=True,
                utterance_end_ms=1000, 
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
            self.is_connected = False
            # Don't raise, just log, so the app doesn't crash loop

    async def stop(self):
        """Stops the Deepgram connection."""
        if self.dg_connection:
            await self.dg_connection.finish()
            self.dg_connection = None
        self.is_connected = False
        logger.info("Disconnected from Deepgram")

    async def send_audio(self, audio_data: bytes):
        """Sends audio data to Deepgram. Auto-reconnects if needed."""
        if not self.is_connected:
            # Try to reconnect if we have a saved language
            if hasattr(self, 'last_source_lang') and self.last_source_lang:
                logger.warning("Connection lost. Attempting to reconnect...")
                await self.start(self.last_source_lang)
                if not self.is_connected:
                    return # Failed to reconnect

        if self.is_connected and self.dg_connection:
            try:
                await self.dg_connection.send(audio_data)
            except Exception as e:
                logger.error(f"Error sending audio: {e}")
                self.is_connected = False # Mark as disconnected so next chunk triggers reconnect

    async def send_keep_alive(self):
        """Sends a KeepAlive message to Deepgram (Silent Audio)."""
        if self.is_connected and self.dg_connection:
            try:
                # logger.debug("Sending KeepAlive (Silence) to Deepgram")
                # Send 1 second of silence (16-bit mono 44.1kHz = 88200 bytes, stereo = 176400 bytes)
                # We are using linear16, 2 channels, 44100Hz
                silence = b'\x00' * 4096 # Send a small chunk of silence
                await self.dg_connection.send(silence)
            except Exception as e:
                logger.error(f"Error sending KeepAlive: {e}")
                self.is_connected = False
