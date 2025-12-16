"""
API Package Initialization
"""

from fastapi import APIRouter

# Create main API router
api_router = APIRouter()

# Import and include sub-routers
from app.api.rooms import router as rooms_router
from app.api.voices import router as voices_router

api_router.include_router(rooms_router)
api_router.include_router(voices_router)

