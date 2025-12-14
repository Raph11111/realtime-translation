"""
Room Manager Service for Multi-Channel Parallel Translations

Manages translation rooms/events where:
- One host broadcasts audio in a source language
- Multiple listeners can join and receive translations in their preferred language
- All translations happen in parallel using asyncio
"""

import os
import asyncio
import logging
import secrets
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Set, Callable, Optional, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class TranslationChannel:
    """Represents a single translation channel for a specific target language."""
    target_language: str
    voice: str = "alloy"
    listeners: Set[WebSocket] = field(default_factory=set)
    is_active: bool = True
    
    async def broadcast_audio(self, audio_data: bytes):
        """Send audio to all listeners on this channel."""
        if not self.listeners:
            return
        
        disconnected = set()
        for ws in self.listeners:
            try:
                await ws.send_bytes(audio_data)
            except Exception as e:
                logger.warning(f"Failed to send audio to listener: {e}")
                disconnected.add(ws)
        
        # Clean up disconnected listeners
        self.listeners -= disconnected
    
    async def broadcast_text(self, message: dict):
        """Send text message to all listeners on this channel."""
        import json
        if not self.listeners:
            return
        
        disconnected = set()
        text_data = json.dumps(message)
        for ws in self.listeners:
            try:
                await ws.send_text(text_data)
            except Exception as e:
                logger.warning(f"Failed to send text to listener: {e}")
                disconnected.add(ws)
        
        self.listeners -= disconnected


@dataclass  
class TranslationRoom:
    """
    Represents a translation room/event.
    
    One room has:
    - A unique room_id (for joining via link/QR)
    - A host who controls the audio source
    - Multiple channels (one per target language)
    - Listeners who subscribe to specific channels
    """
    room_id: str
    room_name: str
    host_id: str
    source_language: str = "auto"
    channels: Dict[str, TranslationChannel] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    max_listeners_per_channel: int = 1000
    
    # Callbacks for translation and TTS
    translation_callback: Optional[Callable] = None
    tts_callback: Optional[Callable] = None
    
    def get_or_create_channel(self, language: str, voice: str = "alloy") -> TranslationChannel:
        """Get existing channel or create new one for the language."""
        if language not in self.channels:
            self.channels[language] = TranslationChannel(
                target_language=language,
                voice=voice
            )
            logger.info(f"Created new channel for language: {language} in room: {self.room_id}")
        return self.channels[language]
    
    def get_active_languages(self) -> list:
        """Get list of languages with active listeners."""
        return [lang for lang, channel in self.channels.items() 
                if channel.listeners and channel.is_active]
    
    def get_total_listeners(self) -> int:
        """Get total number of listeners across all channels."""
        return sum(len(ch.listeners) for ch in self.channels.values())
    
    def get_stats(self) -> dict:
        """Get room statistics."""
        return {
            "room_id": self.room_id,
            "room_name": self.room_name,
            "source_language": self.source_language,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "total_listeners": self.get_total_listeners(),
            "channels": {
                lang: {
                    "listeners": len(ch.listeners),
                    "voice": ch.voice,
                    "is_active": ch.is_active
                }
                for lang, ch in self.channels.items()
            }
        }


class RoomManager:
    """
    Manages all translation rooms.
    
    Singleton-style manager that handles:
    - Room creation/deletion
    - Listener management
    - Parallel translation broadcasting
    """
    
    def __init__(self):
        self.rooms: Dict[str, TranslationRoom] = {}
        self.host_to_room: Dict[str, str] = {}  # host_id -> room_id mapping
        
    def generate_room_id(self) -> str:
        """Generate a unique, short room ID."""
        return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].upper()
    
    def create_room(
        self, 
        room_name: str, 
        host_id: str, 
        source_language: str = "auto"
    ) -> TranslationRoom:
        """Create a new translation room."""
        room_id = self.generate_room_id()
        
        # Ensure unique room ID
        while room_id in self.rooms:
            room_id = self.generate_room_id()
        
        room = TranslationRoom(
            room_id=room_id,
            room_name=room_name,
            host_id=host_id,
            source_language=source_language
        )
        
        self.rooms[room_id] = room
        self.host_to_room[host_id] = room_id
        
        logger.info(f"Created room: {room_id} - '{room_name}' by host: {host_id}")
        return room
    
    def get_room(self, room_id: str) -> Optional[TranslationRoom]:
        """Get a room by ID."""
        return self.rooms.get(room_id.upper())
    
    def get_room_by_host(self, host_id: str) -> Optional[TranslationRoom]:
        """Get room by host ID."""
        room_id = self.host_to_room.get(host_id)
        if room_id:
            return self.rooms.get(room_id)
        return None
    
    def close_room(self, room_id: str) -> bool:
        """Close a room and disconnect all listeners."""
        room = self.rooms.get(room_id.upper())
        if not room:
            return False
        
        room.is_active = False
        
        # Clean up
        if room.host_id in self.host_to_room:
            del self.host_to_room[room.host_id]
        del self.rooms[room_id.upper()]
        
        logger.info(f"Closed room: {room_id}")
        return True
    
    async def add_listener(
        self, 
        room_id: str, 
        language: str, 
        websocket: WebSocket,
        voice: str = "alloy"
    ) -> bool:
        """Add a listener to a room's language channel."""
        room = self.get_room(room_id)
        if not room or not room.is_active:
            return False
        
        channel = room.get_or_create_channel(language, voice)
        
        if len(channel.listeners) >= room.max_listeners_per_channel:
            logger.warning(f"Channel {language} in room {room_id} is full")
            return False
        
        channel.listeners.add(websocket)
        logger.info(f"Listener joined room {room_id}, channel: {language}. Total: {len(channel.listeners)}")
        return True
    
    def remove_listener(self, room_id: str, language: str, websocket: WebSocket):
        """Remove a listener from a channel."""
        room = self.get_room(room_id)
        if not room:
            return
        
        channel = room.channels.get(language)
        if channel and websocket in channel.listeners:
            channel.listeners.discard(websocket)
            logger.info(f"Listener left room {room_id}, channel: {language}. Remaining: {len(channel.listeners)}")
    
    async def broadcast_transcript_to_room(
        self, 
        room_id: str, 
        text: str, 
        is_final: bool
    ):
        """Broadcast transcript to all listeners in a room (original text)."""
        room = self.get_room(room_id)
        if not room:
            return
        
        message = {
            "type": "transcript",
            "text": text,
            "is_final": is_final,
            "source_language": room.source_language
        }
        
        # Send to all channels
        tasks = [
            channel.broadcast_text(message) 
            for channel in room.channels.values()
        ]
        if tasks:
            await asyncio.gather(*tasks)
    
    async def broadcast_translation_to_channel(
        self, 
        room_id: str, 
        language: str, 
        translated_text: str
    ):
        """Broadcast translation to a specific language channel."""
        room = self.get_room(room_id)
        if not room:
            return
        
        channel = room.channels.get(language)
        if not channel:
            return
        
        message = {
            "type": "translation",
            "text": translated_text,
            "language": language
        }
        await channel.broadcast_text(message)
    
    async def broadcast_audio_to_channel(
        self, 
        room_id: str, 
        language: str, 
        audio_data: bytes
    ):
        """Broadcast TTS audio to a specific language channel."""
        room = self.get_room(room_id)
        if not room:
            return
        
        channel = room.channels.get(language)
        if channel:
            await channel.broadcast_audio(audio_data)
    
    def list_rooms(self, active_only: bool = True) -> list:
        """List all rooms."""
        rooms = self.rooms.values()
        if active_only:
            rooms = [r for r in rooms if r.is_active]
        return [r.get_stats() for r in rooms]
    
    def get_join_url(self, room_id: str, base_url: str) -> str:
        """Generate join URL for a room."""
        return f"{base_url}/join/{room_id}"


# Singleton instance
room_manager = RoomManager()
