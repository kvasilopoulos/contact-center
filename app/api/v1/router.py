"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints import classify, health

router = APIRouter(prefix="/api/v1")

# Include endpoint routers
router.include_router(health.router)
router.include_router(classify.router)
