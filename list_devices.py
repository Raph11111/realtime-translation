import sounddevice as sd

def list_devices():
    with open("devices_list.txt", "w", encoding="utf-8") as f:
        f.write("\n=== Available Audio Devices ===\n\n")
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            # We are interested in input devices (max_input_channels > 0)
            if d['max_input_channels'] > 0:
                f.write(f"Index {i}: {d['name']}\n")
                f.write(f"   - Channels: {d['max_input_channels']}\n")
                f.write(f"   - Sample Rate: {d['default_samplerate']}\n")
                f.write("-" * 30 + "\n")
        f.write("\n===============================\n")
        f.write("To use a device, set INPUT_DEVICE_INDEX=<Index> in your .env file.\n")
    print("Devices listed to devices_list.txt")

if __name__ == "__main__":
    list_devices()
