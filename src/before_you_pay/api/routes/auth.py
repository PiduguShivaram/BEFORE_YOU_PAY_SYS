"""Authentication endpoints for session creation and token issuance."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from before_you_pay.api.deps import (
    get_auth_service,
    get_authenticated_user_id,
    get_optional_authenticated_user_id,
)
from before_you_pay.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


class SessionRequest(BaseModel):
    """Request payload to initiate or resume an authenticated user tenant session."""

    user_id: UUID | None = Field(
        default=None,
        description="Optional existing tenant UUID to resume. Caller MUST present valid authentication for this identity.",
    )


class SessionResponse(BaseModel):
    """Cryptographic bearer token response for authenticating tenant API requests."""

    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    expires_in: int


class UserProfileResponse(BaseModel):
    """Authenticated tenant identity profile."""

    user_id: UUID
    authenticated: bool = True


@router.post(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or resume authenticated tenant session",
    description="Issues a cryptographically signed HMAC-SHA256 access token. Caller-supplied user IDs without ownership proof are strictly rejected.",
)
async def create_session(
    request: SessionRequest | None = None,
    authenticated_user_id: UUID | None = Depends(get_optional_authenticated_user_id),
    auth_service: AuthService = Depends(get_auth_service),
) -> SessionResponse:
    """Issue signed bearer token for authenticated tenant operations."""
    # Priority 0 Security Invariant: Never create a token for a caller-supplied existing identity without independent proof of ownership.
    if request and request.user_id is not None:
        if authenticated_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Identity ownership verification failed: cannot claim an existing identity without valid proof of ownership.",
            )
        if authenticated_user_id != request.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant access forbidden: authenticated credentials do not match requested identity.",
            )
        session = auth_service.resume_or_refresh_session(authenticated_user_id)
    elif authenticated_user_id is not None:
        # Re-authenticate / extend session for the verified identity
        session = auth_service.resume_or_refresh_session(authenticated_user_id)
    else:
        # Generate a new server-controlled guest identity
        session = auth_service.create_guest_session()

    return SessionResponse(
        access_token=session["access_token"],
        token_type=session["token_type"],
        user_id=UUID(session["user_id"]),
        expires_in=session["expires_in"],
    )


@router.post(
    "/refresh",
    response_model=SessionResponse,
    summary="Renew verified tenant session token",
    description="Re-issues a freshly signed access token for the authenticated caller.",
)
async def refresh_session(
    authenticated_user_id: UUID = Depends(get_authenticated_user_id),
    auth_service: AuthService = Depends(get_auth_service),
) -> SessionResponse:
    """Re-issue access token for verified caller."""
    session = auth_service.resume_or_refresh_session(authenticated_user_id)
    return SessionResponse(
        access_token=session["access_token"],
        token_type=session["token_type"],
        user_id=UUID(session["user_id"]),
        expires_in=session["expires_in"],
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get verified tenant identity",
    description="Returns the validated user ID decoded strictly from the cryptographic Bearer token.",
)
async def get_current_user_profile(
    user_id: UUID = Depends(get_authenticated_user_id),
) -> UserProfileResponse:
    """Return validated tenant identity from verified token."""
    return UserProfileResponse(user_id=user_id, authenticated=True)
