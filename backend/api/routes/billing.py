"""
Stripe billing — checkout sessions, webhook, credit top-ups.

Tiers:
  starter  → 5 comics  → $9
  creator  → 15 comics → $24
  pro      → 40 comics → $59
"""

import stripe
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from ..database import User, StripeOrder
from ..auth import get_current_user
from ..dependencies import get_db, get_settings

router = APIRouter(prefix="/billing", tags=["billing"])

CREDITS_COST = 1          # 1 credit = 1 comic

TIERS = {
    "starter": {"credits": 5,  "price_cents": 900,  "label": "Starter — 5 comics"},
    "creator": {"credits": 15, "price_cents": 2400, "label": "Creator — 15 comics"},
    "pro":     {"credits": 40, "price_cents": 5900, "label": "Pro — 40 comics"},
}


class CheckoutRequest(BaseModel):
    tier: str
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    req: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    tier = TIERS.get(req.tier)
    if not tier:
        raise HTTPException(400, f"Unknown tier. Choose from: {list(TIERS.keys())}")

    stripe.api_key = settings.stripe_secret_key

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": tier["label"]},
                "unit_amount": tier["price_cents"],
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=req.success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=req.cancel_url,
        metadata={
            "user_id": current_user.id,
            "tier": req.tier,
            "credits": tier["credits"],
        },
    )

    # Record pending order
    order = StripeOrder(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        stripe_session_id=session.id,
        credits=tier["credits"],
        amount_cents=tier["price_cents"],
        status="pending",
    )
    db.add(order)
    await db.commit()

    return CheckoutResponse(checkout_url=session.url, session_id=session.id)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    """Stripe calls this after successful payment. Credits are added here."""
    stripe.api_key = settings.stripe_secret_key
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        stripe_session_id = session_data["id"]
        credits = int(session_data["metadata"].get("credits", 0))
        user_id = session_data["metadata"].get("user_id")

        if not user_id or not credits:
            return {"status": "ignored"}

        # Find the pending order
        result = await db.execute(
            select(StripeOrder).where(StripeOrder.stripe_session_id == stripe_session_id)
        )
        order = result.scalar_one_or_none()

        if order and order.status == "pending":
            order.status = "paid"

            # Add credits to user
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.credits += credits

            await db.commit()

    return {"status": "ok"}


@router.get("/tiers")
async def get_tiers():
    return [
        {
            "id": key,
            "label": val["label"],
            "credits": val["credits"],
            "price_cents": val["price_cents"],
            "price_dollars": val["price_cents"] / 100,
        }
        for key, val in TIERS.items()
    ]


@router.get("/balance")
async def get_balance(current_user: User = Depends(get_current_user)):
    return {"credits": current_user.credits, "user_id": current_user.id}
