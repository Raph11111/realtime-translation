import sounddevice as sd

def list_devices():
    print("Available Audio Devices:")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        print(f"{i}: {device['name']} (In: {device['max_input_channels']}, Out: {device['max_output_channels']})")

if __name__ == "__main__":
    list_devices()
