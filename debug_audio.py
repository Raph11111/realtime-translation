import sounddevice as sd
import numpy as np

DEVICE_INDEX = 37
SAMPLERATE = 44100
CHANNELS = 2

print(f"Attempting to open stream on device {DEVICE_INDEX}...")
try:
    with sd.InputStream(device=DEVICE_INDEX, channels=CHANNELS, samplerate=SAMPLERATE, blocksize=1024, dtype='int16') as stream:
        print("Stream started. Attempting to read...")
        while True:
            data, overflow = stream.read(1024)
            rms = np.sqrt(np.mean(data**2))
            print(f"Read {len(data)} frames. RMS: {rms:.4f}")
except Exception as e:
    print(f"Error: {e}")
