"""Authentication endpoints for session creation and token issuance."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from before_you_pay.api.deps import get_auth_service, get_authenticated_user_id
from before_you_pay.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


class SessionRequest(BaseModel):
    """Request payload to initiate or resume an authenticated user tenant session."""

    user_id: UUID | None = Field(
        default=None,
        description="Optional existing tenant UUID to authenticate. If omitted, a fresh UUID is generated.",
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
    description="Issues a cryptographically signed HMAC-SHA256 access token for the tenant user ID.",
)
async def create_session(
    request: SessionRequest | None = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> SessionResponse:
    """Issue signed bearer token for authenticated tenant operations."""
    target_uid = request.user_id if request and request.user_id else uuid4()
    session = auth_service.create_auth_session(user_id=target_uid)
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
