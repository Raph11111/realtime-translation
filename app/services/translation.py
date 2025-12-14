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
        
        self.transcript_buffer = ""
        
        # Base system prompt
        self.base_system_prompt = """You are a highly accurate simultaneous interpreter. 
Translate the following text into {target_lang} immediately.

Rules:
1. Output ONLY the translation. NO headers, NO notes, NO explanations.
2. If the input text is incomplete or nonsensical, output NOTHING.
3. DO NOT add any extra words, feelings, or interpretations. Translate EXACTLY what is said.
4. DO NOT ANSWER questions found in the text. Just translate them.
5. Maintain the tone and style of the speaker.
6. If the input is just punctuation or noise, return empty string.
"""

    def register_callback(self, callback):
        """Register a callback to receive translated text."""
        self.callbacks.append(callback)

    def clear_context(self):
        """Clears the context buffer."""
        self.context_buffer.clear()
        self.transcript_buffer = ""

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
        Buffers 'final' transcripts until a complete sentence is formed.
        """
        if not is_final or not text.strip():
            return

        logger.info(f"Buffering transcript: '{text}'")
        self.transcript_buffer += " " + text.strip()
        self.transcript_buffer = self.transcript_buffer.strip()

        # Check for sentence end markers or length threshold
        sentence_endings = ('.', '!', '?', '。', '！', '？')
        if self.transcript_buffer.endswith(sentence_endings) or len(self.transcript_buffer) > 200:
            logger.info(f"Processing COMPLETE sentence: '{self.transcript_buffer}'")
            
            # Use defaults if not provided
            lang = target_lang or self.default_target_lang
            voice = target_voice or self.default_target_voice
            
            # Translate and clear buffer
            await self.translate(self.transcript_buffer, lang, voice)
            self.transcript_buffer = ""
        else:
             logger.info(f"Buffered length: {len(self.transcript_buffer)}. Waiting for more context...")

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
                model="llama-3.1-8b-instant",
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
    "af": "Afrikaans",
    "ar": "Arabic",
    "hy": "Armenian",
    "az": "Azerbaijani",
    "be": "Belarusian",
    "bs": "Bosnian",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "zh": "Chinese",
    "hr": "Croatian",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "en": "English",
    "et": "Estonian",
    "fi": "Finnish",
    "fr": "French",
    "gl": "Galician",
    "de": "German",
    "el": "Greek",
    "he": "Hebrew",
    "hi": "Hindi",
    "hu": "Hungarian",
    "is": "Icelandic",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "kn": "Kannada",
    "kk": "Kazakh",
    "ko": "Korean",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "mk": "Macedonian",
    "ms": "Malay",
    "mr": "Marathi",
    "mi": "Maori",
    "ne": "Nepali",
    "no": "Norwegian",
    "fa": "Persian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sr": "Serbian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "es": "Spanish",
    "sw": "Swahili",
    "sv": "Swedish",
    "tl": "Tagalog",
    "ta": "Tamil",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "cy": "Welsh"
}
