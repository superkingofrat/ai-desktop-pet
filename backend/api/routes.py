"""REST API routes — health check, session management, etc."""
from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger("assistant.api")
router = APIRouter()


@router.get("/health")
async def health():
    """Health check endpoint (delegated from main app)."""
    return {"status": "ok"}
