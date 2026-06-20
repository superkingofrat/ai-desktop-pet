"""Stats dashboard API routes."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Query

from backend.services.stats_service import get_stats

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/stats/summary")
async def api_stats_summary(days: int = Query(7, ge=1, le=365)):
    """Return aggregated dashboard statistics for the last *days* days."""
    return get_stats(days=days)
