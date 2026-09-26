"""Clean API route aggregator exposing only the essential user endpoints."""

from fastapi import APIRouter

from before_you_pay.api.routes.analyze import router as analyze_router
from before_you_pay.api.routes.documents import router as documents_router
from before_you_pay.api.routes.health import router as health_router

api_router = APIRouter()

# Register the essential endpoints: /health, /analyze, /documents
api_router.include_router(health_router)
api_router.include_router(analyze_router)
api_router.include_router(documents_router)
