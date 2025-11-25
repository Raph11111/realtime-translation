import os
from elevenlabs import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

try:
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    print("Client attributes:", dir(client))
    
    if hasattr(client, 'text_to_speech'):
        print("\nclient.text_to_speech attributes:", dir(client.text_to_speech))
    
    if hasattr(client, 'generate'):
        print("\nclient.generate exists!")
    else:
        print("\nclient.generate DOES NOT exist.")

except Exception as e:
    print(e)
