import os
import logging
import asyncio
from groq import AsyncGroq

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.target_lang = os.getenv("TARGET_LANGUAGE", "de")
        self.client = None
        
        if self.api_key:
            self.client = AsyncGroq(api_key=self.api_key)
        else:
            logger.warning("GROQ_API_KEY not found. Translation will be disabled.")

        self.callbacks = []
        
        # System prompt optimized for speed and theological accuracy
        self.system_prompt = f"""You are a professional simultaneous interpreter for a church service. 
Translate the following French text into {self.target_lang} immediately.
Rules:
1. Be concise but accurate.
2. Maintain the theological tone (solemn, respectful).
3. Do not explain, just translate.
4. Handle religious terms correctly (e.g., 'Salut' -> 'Heil'/'Salvation', not 'Hi').
"""

    def register_callback(self, callback):
        """Register a callback to receive translated text."""
        self.callbacks.append(callback)

    async def translate(self, text: str):
        """Translates text using Groq Llama 3."""
        if not self.client or not text.strip():
            return

        try:
            # Call Groq API
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": text,
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                max_tokens=1024,
                top_p=1,
                stop=None,
                stream=False,
            )

            translated_text = chat_completion.choices[0].message.content.strip()
            
            # Notify callbacks
            for callback in self.callbacks:
                await callback(translated_text)
                
        except Exception as e:
            logger.error(f"Translation error: {e}")

    async def process_transcript(self, text: str, is_final: bool):
        """
        Called when a new transcript is received.
        We only translate 'final' transcripts to save API calls and reduce jitter.
        """
        if is_final:
            await self.translate(text)
