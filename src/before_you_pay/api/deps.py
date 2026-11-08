"""FastAPI dependency injection providers."""

from functools import lru_cache
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from before_you_pay.services.auth import (
    AuthService,
    TokenExpiredError,
    TokenInvalidError,
    TokenMissingError,
)
from before_you_pay.services.dealer_response_parser import DealerResponseParserService
from before_you_pay.services.multi_quote_comparison import MultiQuoteComparisonService
from before_you_pay.services.pipeline import PipelineService

_bearer_security = HTTPBearer(auto_error=False)


@lru_cache
def get_auth_service() -> AuthService:
    """Singleton provider for cryptographic AuthService."""
    return AuthService()


@lru_cache
def get_pipeline_service() -> PipelineService:
    """Singleton provider for PipelineService and child engines."""
    return PipelineService()


@lru_cache
def get_multi_quote_comparison_service() -> MultiQuoteComparisonService:
    """Singleton provider for MultiQuoteComparisonService."""
    return MultiQuoteComparisonService()


@lru_cache
def get_dealer_response_parser_service() -> DealerResponseParserService:
    """Singleton provider for DealerResponseParserService."""
    return DealerResponseParserService()


async def get_authenticated_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_security),
    auth_service: AuthService = Depends(get_auth_service),
) -> UUID:
    """Derive authenticated user tenant identity strictly from verified Bearer token.

    Rejects missing, forged, expired, or malformed tokens with HTTP 401.
    Never trusts client-supplied headers or form data for tenant authentication.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Bearer token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return auth_service.verify_access_token(credentials.credentials)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication token has expired: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (TokenInvalidError, TokenMissingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_optional_authenticated_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_security),
    auth_service: AuthService = Depends(get_auth_service),
) -> UUID | None:
    """Validate Bearer token if provided. Raises 401 on invalid/expired token."""
    if not credentials or not credentials.credentials:
        return None

    try:
        return auth_service.verify_access_token(credentials.credentials)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication token has expired: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (TokenInvalidError, TokenMissingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def verify_tenant_boundary(
    authenticated_user_id: UUID | None,
    requested_user_id: UUID | None = None,
) -> UUID:
    """Ensure client cannot specify a user_id different from the authenticated token.

    Security invariants:
    1. Authenticated user ID is MANDATORY. Never falls back to caller-supplied unauthenticated UUID.
    2. If caller provides a requested_user_id, it MUST match authenticated_user_id exactly.
    3. Cross-tenant access attempts are rejected with HTTP 403 Forbidden.
    4. Unauthenticated access attempts are rejected with HTTP 401 Unauthorized.
    """
    if authenticated_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: verified Bearer session token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if requested_user_id is not None and requested_user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant access forbidden: provided user ID does not match authenticated token.",
        )

    return authenticated_user_id
