import asyncio
import os
from dotenv import load_dotenv
from app.services.tts import TTSService

# Load environment variables
load_dotenv()

async def verify_tts_fix():
    print("Initializing TTSService...")
    tts = TTSService()
    
    print(f"Model ID: {tts.model_id}")
    
    # Callback to receive audio
    audio_received = False
    
    async def on_audio(chunk):
        nonlocal audio_received
        audio_received = True
        print(f"Received audio chunk of size: {len(chunk)} bytes")

    tts.register_callback(on_audio)
    
    # Test with a question that would normally trigger an answer from a chat model
    text = "What is the capital of France?"
    print(f"Generating audio for input: '{text}'")
    print("Expected: Audio of someone READING 'What is the capital of France?'")
    print("NOT expected: Audio of someone ANSWERING 'Paris'")
    
    await tts.generate_audio(text)
    
    if audio_received:
        print("\nSUCCESS: Audio was generated.")
        print("Since we're using tts-1, the audio will be a verbatim reading of the text.")
    else:
        print("\nFAILURE: No audio received.")

if __name__ == "__main__":
    asyncio.run(verify_tts_fix())
