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
        self.samplerate = 44100
        self.channels = 2
        self.blocksize = 1024  # Adjust for latency vs stability
        self.stream = None
        self.is_running = False
        # Bounded queue to avoid unbounded memory growth if downstream stalls
        self.queue = asyncio.Queue(maxsize=300)

    def _callback(self, indata, frames, time, status):
        """Callback for sounddevice to capture audio chunks."""
        if status:
            logger.warning(f"Audio status: {status}")
        
        # Convert to bytes and put in queue
        # indata is already int16 because we set dtype="int16" in start_stream
        
        # Calculate RMS (volume) for debugging
        # We need to convert to float for RMS calculation to avoid overflow
        rms = np.sqrt(np.mean(indata.astype(float)**2))
        if rms > 100: # Threshold for int16 (max 32767)
            logger.info(f"Audio Level (RMS): {rms:.2f}")
            pass
        
        audio_data = indata
        
        if self.loop:
            # Schedule queue operation on the main event loop
            self.loop.call_soon_threadsafe(self._enqueue_audio, audio_data.tobytes(), rms)

    def _enqueue_audio(self, data: bytes, rms: float):
        """Helper to safely put audio into queue from the event loop."""
        try:
            if self.queue.full():
                 # Drop the oldest item to make room
                try:
                    self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            self.queue.put_nowait(data)
        except asyncio.QueueFull:
            # Should hopefully not happen if we just made room, but possible in race conditions
            pass
            
        # Debug heartbeat
        if not hasattr(self, '_frame_count'):
            self._frame_count = 0
        if not hasattr(self, '_silence_count'):
            self._silence_count = 0
            
        self._frame_count += 1
        
        if rms < 5:
            self._silence_count += 1
        else:
            self._silence_count = 0
            
        if self._silence_count > 200 and self._silence_count % 200 == 0:
             logger.warning(f"WARNING: MICROPHONE IS SILENT (RMS: {rms:.2f}). Check your input device settings!")

        if self._frame_count % 200 == 0: # Approx every 4-5 seconds at 44.1kHz/1024
            logger.info(f"Audio stream active. Current RMS: {rms:.2f}")

    async def start_stream(self):
        """Starts the audio stream."""
        if self.is_running:
            return

        self.loop = asyncio.get_running_loop()

        devices_to_try = []
        if self.device_index is not None:
            devices_to_try.append(self.device_index)
        devices_to_try.append(None) # Default device

        # Add first valid input device as last resort
        try:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0:
                    if i not in devices_to_try:
                        devices_to_try.append(i)
                    break
        except Exception:
            pass

        for dev_idx in devices_to_try:
            logger.info(f"Attempting to start audio stream on device index: {dev_idx}")
            try:
                self.stream = sd.InputStream(
                    device=dev_idx,
                    channels=self.channels,
                    samplerate=self.samplerate,
                    blocksize=self.blocksize,
                    callback=self._callback,
                    dtype="int16"
                )
                self.stream.start()
                self.is_running = True
                device_name = sd.query_devices(dev_idx)['name']
                logger.info(f"Audio stream started successfully on device {dev_idx}: {device_name}")
                return # Success!
            except Exception as e:
                logger.warning(f"Failed to start on device {dev_idx}: {e}")
        
        # If we get here, all attempts failed
        logger.error("Failed to start audio stream on any device.")
        raise RuntimeError("Could not initialize audio input on any device.")

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

    def list_input_devices(self):
        """Lists all available audio input devices."""
        devices = []
        try:
            logger.info("Querying audio devices...")
            # host_api_info = sd.query_host_apis() # potentially problematic
            
            all_devices = sd.query_devices()
            logger.info(f"Found {len(all_devices)} total devices.")
            
            default_input = -1
            try:
                default_input = sd.default.device[0]
            except Exception as e:
                logger.warning(f"Could not determine default device: {e}")

            for i, d in enumerate(all_devices):
                if d['max_input_channels'] > 0:
                    devices.append({
                        "index": i,
                        "name": d['name'],
                        "host_api": d['hostapi'],
                        "is_default": (i == default_input)
                    })
            logger.info(f"Returning {len(devices)} input devices.")
        except Exception as e:
            logger.error(f"Error listing devices: {e}", exc_info=True)
        return devices

    async def set_device(self, device_index: int):
        """Switches the audio input device."""
        logger.info(f"Switching input device to index: {device_index}")
        
        # Validate index
        try:
            dev = sd.query_devices(device_index)
            if dev['max_input_channels'] <= 0:
                raise ValueError("Selected device has no input channels")
        except Exception as e:
            logger.error(f"Invalid device index {device_index}: {e}")
            raise ValueError(f"Invalid device index: {e}")

        self.device_index = device_index
        
        # Restart stream if running
        if self.is_running:
            self.stop_stream()
            # Small pause to ensure cleanup
            await asyncio.sleep(0.5) 
            await self.start_stream()

