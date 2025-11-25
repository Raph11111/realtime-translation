import sounddevice as sd
import asyncio
import numpy as np
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioCaptureService:
    def __init__(self):
        # Use default device if not specified
        self.device_index = os.getenv("INPUT_DEVICE_INDEX")
        if self.device_index:
            self.device_index = int(self.device_index)
        else:
            self.device_index = None # Let sounddevice choose default
        self.samplerate = 16000
        self.channels = 1
        self.blocksize = 1024  # Adjust for latency vs stability
        self.stream = None
        self.is_running = False
        self.queue = asyncio.Queue()

    def _callback(self, indata, frames, time, status):
        """Callback for sounddevice to capture audio chunks."""
        if status:
            logger.warning(f"Audio status: {status}")
        
        # Convert to bytes and put in queue
        # indata is a numpy array of float32 by default
        # We might need int16 for some APIs, but float32 is standard for processing
        # Deepgram usually accepts linear16 (int16)
        
        # Calculate RMS (volume) for debugging
        rms = np.sqrt(np.mean(indata**2))
        if rms > 0.01: # Only log if there's some sound
            # logger.info(f"Audio Level (RMS): {rms:.4f}")
            pass
        
        # Convert float32 [-1, 1] to int16 [-32768, 32767]
        audio_data = (indata * 32767).astype(np.int16)
        
        # We need to use call_soon_threadsafe because this callback runs in a separate thread
        try:
            self.queue.put_nowait(audio_data.tobytes())
        except asyncio.QueueFull:
            logger.error("Audio queue full, dropping frame")

    async def start_stream(self):
        """Starts the audio stream."""
        if self.is_running:
            return

        logger.info(f"Starting audio stream on device {self.device_index}")
        try:
            self.stream = sd.InputStream(
                device=self.device_index,
                channels=self.channels,
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                callback=self._callback,
                dtype="float32" # Capture as float32 for quality, convert later
            )
            self.stream.start()
            self.is_running = True
            logger.info("Audio stream started successfully")
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            raise

    def stop_stream(self):
        """Stops the audio stream."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.is_running = False
        logger.info("Audio stream stopped")

    async def get_audio_chunk(self):
        """Retrieves the next audio chunk from the queue."""
        return await self.queue.get()
