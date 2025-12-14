"""
Parallel Translation Service

Handles translating a single source text to multiple target languages simultaneously
using asyncio.gather() for parallel processing.
"""

import os
import asyncio
import logging
from typing import Dict, List, Callable, Optional
from collections import deque
from groq import AsyncGroq

logger = logging.getLogger(__name__)


# Extended Language Code Mapping (50+ languages)
LANGUAGE_CODE_TO_NAME = {
    "af": "Afrikaans",
    "ar": "Arabic",
    "hy": "Armenian",
    "az": "Azerbaijani",
    "be": "Belarusian",
    "bn": "Bengali",
    "bs": "Bosnian",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "zh": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "hr": "Croatian",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "en": "English",
    "et": "Estonian",
    "fi": "Finnish",
    "fr": "French",
    "gl": "Galician",
    "ka": "Georgian",
    "de": "German",
    "de-CH": "Swiss German",
    "el": "Greek",
    "gu": "Gujarati",
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
    "ml": "Malayalam",
    "mr": "Marathi",
    "mi": "Maori",
    "mn": "Mongolian",
    "ne": "Nepali",
    "no": "Norwegian",
    "fa": "Persian",
    "pl": "Polish",
    "pt": "Portuguese",
    "pt-BR": "Brazilian Portuguese",
    "pa": "Punjabi",
    "ro": "Romanian",
    "ru": "Russian",
    "sr": "Serbian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "es": "Spanish",
    "es-MX": "Mexican Spanish",
    "sw": "Swahili",
    "sv": "Swedish",
    "tl": "Tagalog",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "cy": "Welsh",
    "yo": "Yoruba",
    "zu": "Zulu",
}

# Context-specific translation modes
TRANSLATION_CONTEXTS = {
    "general": "",
    "church": """You are translating religious/spiritual content. 
Use appropriate theological terminology. Maintain reverence in tone.
Common terms: sermon, prayer, blessing, congregation, scripture, faith.""",
    
    "business": """You are translating professional/business content.
Use formal business vocabulary. Maintain professional tone.
Common terms: meeting, proposal, stakeholders, deliverables, KPIs.""",
    
    "casual": """You are translating informal conversation.
Use natural, everyday language. Match the casual tone.
Feel free to use colloquialisms appropriate to the target language.""",
    
    "medical": """You are translating medical/healthcare content.
Use precise medical terminology. Clarity is critical.
Be accurate with drug names, procedures, and symptoms.""",
    
    "legal": """You are translating legal content.
Use precise legal terminology. Maintain formal tone.
Be accurate with legal terms and procedural language."""
}


class ParallelTranslationService:
    """
    Service for translating text to multiple languages in parallel.
    
    Key features:
    - Single STT input, multiple translation outputs
    - asyncio.gather() for parallel API calls
    - Context-aware translations
    - Per-language callbacks for TTS
    """
    
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.client = None
        
        if self.api_key:
            self.client = AsyncGroq(api_key=self.api_key)
        else:
            logger.warning("GROQ_API_KEY not found. Translation will be disabled.")
        
        # Context buffer for coherent translations
        self.context_buffer: deque = deque(maxlen=3)
        self.transcript_buffer = ""
        
        # Translation context mode
        self.context_mode = "general"
        
        # Callbacks: Dict[language_code, callback_function]
        self.translation_callbacks: Dict[str, List[Callable]] = {}
        self.tts_callbacks: Dict[str, List[Callable]] = {}
        
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
{context_rules}"""

    def set_context_mode(self, mode: str):
        """Set the translation context mode."""
        if mode in TRANSLATION_CONTEXTS:
            self.context_mode = mode
            logger.info(f"Translation context set to: {mode}")
    
    def register_translation_callback(self, language: str, callback: Callable):
        """Register a callback for when translation to a specific language is complete."""
        if language not in self.translation_callbacks:
            self.translation_callbacks[language] = []
        self.translation_callbacks[language].append(callback)
    
    def register_tts_callback(self, language: str, callback: Callable):
        """Register a callback for TTS generation for a specific language."""
        if language not in self.tts_callbacks:
            self.tts_callbacks[language] = []
        self.tts_callbacks[language].append(callback)
    
    def clear_context(self):
        """Clear translation context buffer."""
        self.context_buffer.clear()
        self.transcript_buffer = ""
    
    def _get_context_str(self) -> str:
        """Format context buffer for prompt."""
        if not self.context_buffer:
            return ""
        
        context_str = "\nContext (previous conversation):\n"
        for source, target in self.context_buffer:
            context_str += f"Original: {source}\nTranslation: {target}\n"
        return context_str
    
    async def translate_single(
        self, 
        text: str, 
        target_lang: str,
        voice: str = "alloy"
    ) -> Optional[str]:
        """Translate text to a single target language."""
        if not self.client or not text.strip():
            return None
        
        target_lang_name = LANGUAGE_CODE_TO_NAME.get(target_lang, target_lang)
        context_rules = TRANSLATION_CONTEXTS.get(self.context_mode, "")
        
        system_prompt = self.base_system_prompt.format(
            target_lang=target_lang_name,
            context_rules=context_rules
        )
        
        context_str = self._get_context_str()
        full_user_message = f"{context_str}\nOriginal: {text}"
        
        try:
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_user_message}
                ],
                model="llama-3.1-8b-instant",
                temperature=0.3,
                max_tokens=1024,
                top_p=1,
                stream=False,
            )
            
            translated_text = chat_completion.choices[0].message.content.strip()
            
            # Notify translation callbacks
            if target_lang in self.translation_callbacks:
                for callback in self.translation_callbacks[target_lang]:
                    try:
                        await callback(translated_text, target_lang, voice)
                    except Exception as e:
                        logger.error(f"Translation callback error: {e}")
            
            return translated_text
            
        except Exception as e:
            logger.error(f"Translation error for {target_lang}: {e}")
            return None
    
    async def translate_parallel(
        self, 
        text: str, 
        target_languages: List[str],
        voices: Dict[str, str] = None
    ) -> Dict[str, str]:
        """
        Translate text to multiple languages simultaneously.
        
        Args:
            text: Source text to translate
            target_languages: List of language codes to translate to
            voices: Optional mapping of language -> voice
            
        Returns:
            Dict of language_code -> translated_text
        """
        if not self.client or not text.strip() or not target_languages:
            return {}
        
        voices = voices or {}
        
        # Create translation tasks for all languages
        tasks = [
            self.translate_single(text, lang, voices.get(lang, "alloy"))
            for lang in target_languages
        ]
        
        # Execute all translations in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build results dict
        translations = {}
        for lang, result in zip(target_languages, results):
            if isinstance(result, Exception):
                logger.error(f"Translation to {lang} failed: {result}")
                translations[lang] = None
            else:
                translations[lang] = result
        
        # Update context buffer with first successful translation
        for lang, translated in translations.items():
            if translated:
                self.context_buffer.append((text, translated))
                break
        
        return translations
    
    async def process_transcript(
        self, 
        text: str, 
        is_final: bool,
        target_languages: List[str],
        voices: Dict[str, str] = None
    ) -> Dict[str, str]:
        """
        Process incoming transcript and trigger parallel translations.
        
        Buffers transcripts until complete sentences are formed.
        """
        if not is_final or not text.strip():
            return {}
        
        logger.info(f"Buffering transcript: '{text}'")
        self.transcript_buffer += " " + text.strip()
        self.transcript_buffer = self.transcript_buffer.strip()
        
        # Check for sentence end
        sentence_endings = ('.', '!', '?', '。', '！', '？', '،', '؟')
        if self.transcript_buffer.endswith(sentence_endings) or len(self.transcript_buffer) > 200:
            logger.info(f"Processing complete sentence to {len(target_languages)} languages: '{self.transcript_buffer}'")
            
            translations = await self.translate_parallel(
                self.transcript_buffer, 
                target_languages,
                voices
            )
            
            self.transcript_buffer = ""
            return translations
        
        return {}


# Singleton instance
parallel_translation_service = ParallelTranslationService()
