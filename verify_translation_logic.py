import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock
from app.services.translation import TranslationService

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_buffering():
    print("Initializing TranslationService...")
    service = TranslationService()
    
    # Mock the translate method to avoid actual API calls
    service.translate = AsyncMock()
    
    print("\nTest 1: Partial Sentence")
    # Simulate receiving "Hello" (final=True but no punctuation)
    await service.process_transcript("Hello", is_final=True)
    
    # Assert translate was NOT called
    if service.translate.called:
        print("FAILURE: Translate was called prematurely.")
    else:
        print("SUCCESS: Translate was NOT called for partial sentence.")
        print(f"Buffer content: '{service.transcript_buffer}'")

    print("\nTest 2: Complete Sentence")
    # Simulate receiving " world." (final=True with punctuation)
    await service.process_transcript("world.", is_final=True)
    
    # Assert translate WAS called
    if service.translate.called:
        print("SUCCESS: Translate WAS called after punctuation.")
        # Verify the argument was the full sentence
        args, _ = service.translate.call_args
        print(f"Translated text: '{args[0]}'")
        if args[0] == "Hello world.":
            print("SUCCESS: Full sentence matched.")
        else:
            print(f"FAILURE: Expected 'Hello world.', got '{args[0]}'")
    else:
        print("FAILURE: Translate was NOT called after punctuation.")

if __name__ == "__main__":
    asyncio.run(test_buffering())
