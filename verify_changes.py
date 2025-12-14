import sys
import os
import asyncio

# Add app to path
sys.path.append(os.getcwd())

from app.services.translation import LANGUAGE_CODE_TO_NAME
from app.services.tts import TTSService

async def test_languages():
    print("Testing Language Mapping...")
    expected_count = 50
    count = len(LANGUAGE_CODE_TO_NAME)
    print(f"Found {count} languages.")
    
    if count < expected_count:
        print("FAIL: Language list seems too short.")
    else:
        print("PASS: Language list looks comprehensive.")
        
    if "fr" in LANGUAGE_CODE_TO_NAME and "zu" in  LANGUAGE_CODE_TO_NAME: # check for some basic and extended
        pass
    
async def test_tts_init():
    print("\nTesting TTS Service Initialization...")
    try:
        tts = TTSService()
        print("TTSService initialized successfully.")
        
        if tts.openai_client:
            print("PASS: OpenAI Client is initialized.")
        else:
            print("WARNING: OpenAI Client is NOT initialized (Check API Key).")
            
        # Check mapping
        if "alloy" in tts.voice_mapping:
             print("PASS: Voice mapping present.")
        else:
             print("FAIL: Voice mapping missing.")
             
    except Exception as e:
        print(f"FAIL: TTS initialization failed: {e}")

async def main():
    await test_languages()
    await test_tts_init()

if __name__ == "__main__":
    asyncio.run(main())
