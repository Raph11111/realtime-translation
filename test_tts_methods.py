
import os
import asyncio
from elevenlabs import AsyncElevenLabs
from dotenv import load_dotenv

load_dotenv()

async def main():
    try:
        client = AsyncElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        print("AsyncClient created successfully.")
        
        if hasattr(client, 'text_to_speech'):
            stream_method = getattr(client.text_to_speech, 'stream', None)
            if stream_method:
                print("Stream method found on client.text_to_speech.")
                # Uncomment to test actual generation (costs credits)
                # print("Testing stream generation...")
                # stream = stream_method(
                #     text="Hello execution",
                #     voice_id="21m00Tcm4TlvDq8ikWAM",
                #     model_id="eleven_turbo_v2_5"
                # )
                # async for chunk in stream:
                #     print(f"Received chunk of size: {len(chunk)}")
                #     break
            else:
                print("Stream method NOT found.")
        else:
             print("text_to_speech attribute NOT found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
