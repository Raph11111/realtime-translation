import os
import asyncio
from dotenv import load_dotenv
from deepgram import DeepgramClient, LiveOptions

load_dotenv()

async def test_connection():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("No API Key")
        return

    client = DeepgramClient(api_key)
    dg_connection = client.listen.asyncwebsocket.v("1")

    async def on_message(self, result, **kwargs):
        print("Message received")

    async def on_error(self, error, **kwargs):
        print(f"Error: {error}")

    dg_connection.on(1, on_message) # LiveTranscriptionEvents.Transcript
    dg_connection.on(3, on_error)   # LiveTranscriptionEvents.Error

    options = LiveOptions(
        model="nova-2",
        language="fr",
        smart_format=True,
        encoding="linear16",
        channels=1,
        sample_rate=16000,
        interim_results=True,
        utterance_end_ms=1000,
        vad_events=True,
    )

    print("Starting connection with options:", options)
    try:
        if await dg_connection.start(options) is False:
            print("Failed to start")
        else:
            print("Connected successfully!")
            await asyncio.sleep(2)
            await dg_connection.finish()
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
