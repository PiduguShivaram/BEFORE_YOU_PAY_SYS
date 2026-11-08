"""Clean API route aggregator exposing only the essential user endpoints."""

from fastapi import APIRouter

from before_you_pay.api.routes.analyze import router as analyze_router
from before_you_pay.api.routes.auth import router as auth_router
from before_you_pay.api.routes.compare import router as compare_router
from before_you_pay.api.routes.dealer_response import router as dealer_response_router
from before_you_pay.api.routes.documents import router as documents_router
from before_you_pay.api.routes.health import router as health_router

api_router = APIRouter()

# Register endpoints: /health, /auth, /analyze, /documents, /compare-quotes, /parse-dealer-response
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(analyze_router)
api_router.include_router(compare_router)
api_router.include_router(dealer_response_router)
api_router.include_router(documents_router)
