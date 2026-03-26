"""Auth routes — register, login, me, refresh."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import User
from ..auth import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
    hash_password, verify_password, create_token, get_current_user,
)
from ..dependencies import get_db, get_settings
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    req.validate_password()

    # Check duplicate
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=req.email,
        hashed_password=hash_password(req.password),
        credits=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_token(user.id, settings.secret_key)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        credits=user.credits,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")

    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    token = create_token(user.id, settings.secret_key)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        credits=user.credits,
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        credits=current_user.credits,
        created_at=current_user.created_at,
    )
