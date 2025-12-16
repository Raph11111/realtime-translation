"""
Test script for ElevenLabs TTS integration.
Tests voice fetching and audio generation.
"""

import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_elevenlabs_integration():
    from app.services.tts import TTSService
    
    print("=" * 50)
    print("ElevenLabs TTS Integration Test")
    print("=" * 50)
    
    # Initialize service
    tts = TTSService()
    
    if not tts.elevenlabs_client:
        print("❌ ERROR: ElevenLabs client not initialized. Check ELEVENLABS_API_KEY in .env")
        return False
    
    print("✅ ElevenLabs client initialized")
    print(f"   Model: {tts.model_id}")
    
    # Test 1: Fetch voices
    print("\n📋 Test 1: Fetching voices...")
    try:
        voices = await tts.get_voices()
        print(f"✅ Fetched {len(voices)} voices")
        
        # Show first 5 voices
        print("   Sample voices:")
        for voice in voices[:5]:
            category = voice.get('category', 'premade')
            print(f"   - {voice['name']} ({category})")
        
        # Count cloned vs premade
        cloned = len([v for v in voices if v.get('category') == 'cloned'])
        premade = len(voices) - cloned
        print(f"   Cloned: {cloned}, Premade: {premade}")
        
    except Exception as e:
        print(f"❌ Error fetching voices: {e}")
        return False
    
    # Test 2: Generate audio (uses credits!)
    print("\n🔊 Test 2: Generating audio...")
    print("   Text: 'Hello, this is a test of ElevenLabs TTS.'")
    
    audio_received = []
    
    async def collect_audio(chunk: bytes):
        audio_received.append(chunk)
    
    tts.register_callback(collect_audio)
    
    try:
        await tts.generate_audio(
            "Hello, this is a test of ElevenLabs TTS.",
            voice_id=voices[0]['voice_id'] if voices else None
        )
        
        if audio_received:
            total_bytes = sum(len(c) for c in audio_received)
            print(f"✅ Audio generated: {total_bytes} bytes")
            
            # Save test audio
            test_audio_path = "test_elevenlabs_output.mp3"
            with open(test_audio_path, 'wb') as f:
                for chunk in audio_received:
                    f.write(chunk)
            print(f"   Saved to: {test_audio_path}")
        else:
            print("❌ No audio received")
            return False
            
    except Exception as e:
        print(f"❌ Error generating audio: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print("=" * 50)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_elevenlabs_integration())
    exit(0 if success else 1)
