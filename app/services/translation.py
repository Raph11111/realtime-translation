import os
import logging
import asyncio
from collections import deque
from groq import AsyncGroq

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.default_target_lang = os.getenv("TARGET_LANGUAGE", "de")
        self.default_target_voice = "alloy" # Default voice
        self.client = None
        
        if self.api_key:
            self.client = AsyncGroq(api_key=self.api_key)
        else:
            logger.warning("GROQ_API_KEY not found. Translation will be disabled.")

        self.callbacks = []
        
        # Context buffer: Stores tuples of (source_text, translated_text)
        # We keep the last 3 turns to provide context without blowing up the prompt.
        self.context_buffer = deque(maxlen=3)
        
        # Base system prompt
        self.base_system_prompt = """You are a professional simultaneous interpreter for a church service. 
Translate the following text into {target_lang} immediately.

Rules:
1. Be concise but accurate.
2. Maintain the theological tone (solemn, respectful).
3. Do not explain, just translate.
4. Handle religious terms correctly (e.g., 'Salut' -> 'Heil'/'Salvation', not 'Hi').
5. Use the provided context to resolve ambiguities (pronouns, references).
"""

    def register_callback(self, callback):
        """Register a callback to receive translated text."""
        self.callbacks.append(callback)

    def clear_context(self):
        """Clears the context buffer."""
        self.context_buffer.clear()

    def _get_context_str(self):
        """Formats the context buffer into a string for the prompt."""
        if not self.context_buffer:
            return ""
        
        context_str = "\nContext (previous conversation):\n"
        for source, target in self.context_buffer:
            context_str += f"Original: {source}\nTranslation: {target}\n"
        return context_str

    async def process_transcript(self, text: str, is_final: bool, target_lang: str = None, target_voice: str = None):
        """
        Called when a new transcript is received.
        We only translate 'final' transcripts to save API calls and reduce jitter.
        """
        # logger.info(f"Received transcript: '{text[:30]}...' (Final: {is_final})")
        if is_final:
            logger.info(f"Processing FINAL transcript: '{text}'")
            # Use defaults if not provided
            lang = target_lang or self.default_target_lang
            voice = target_voice or self.default_target_voice
            await self.translate(text, lang, voice)

    async def translate(self, text: str, target_lang: str = None, target_voice: str = None):
        """Translates text using Groq Llama 3 with context."""
        if not self.client or not text.strip():
            return

        target_lang_code = target_lang or self.default_target_lang
        
        # Map code to full name, default to the code itself if not found
        target_lang_name = LANGUAGE_CODE_TO_NAME.get(target_lang_code, target_lang_code)
        
        logger.info(f"Translating to: {target_lang_name} (code: {target_lang_code})")
        
        # Build the dynamic system prompt
        system_prompt = self.base_system_prompt.format(target_lang=target_lang_name)
        context_str = self._get_context_str()
        
        full_user_message = f"{context_str}\nOriginal: {text}"

        try:
            # Call Groq API
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": full_user_message,
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
            
            # Update context buffer
            self.context_buffer.append((text, translated_text))
            
            # Notify callbacks
            for callback in self.callbacks:
                await callback(translated_text, target_voice)
                
        except Exception as e:
            logger.error(f"Translation error: {e}")

# Language Code Mapping
LANGUAGE_CODE_TO_NAME = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "ko": "Korean",
    "hi": "Hindi",
    "ar": "Arabic",
    "uk": "Ukrainian",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "no": "Norwegian"
}
