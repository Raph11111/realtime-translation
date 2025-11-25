import elevenlabs
import pkgutil

print("ElevenLabs version:", getattr(elevenlabs, "__version__", "Unknown"))
print("\nTop level attributes:")
print(dir(elevenlabs))

try:
    from elevenlabs import ElevenLabs
    client = ElevenLabs(api_key="test")
    print("\nElevenLabs Client attributes:")
    print(dir(client))
except Exception as e:
    print(f"\nError instantiating client: {e}")
