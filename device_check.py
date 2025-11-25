import sounddevice as sd

def list_devices():
    print("Available Audio Devices:")
    print(sd.query_devices())
    print("\n------------------------------------------------")
    print("Please find the index of your 'Microphone' or 'Line In' device.")
    print("Update INPUT_DEVICE_INDEX in your .env file with this number.")

if __name__ == "__main__":
    list_devices()
