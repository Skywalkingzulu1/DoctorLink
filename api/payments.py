#!/usr/bin/env python3
"""
FastAPI router for handling credit package purchases via Stripe.

Provides two endpoints:
1. POST /purchase – creates a Stripe Checkout Session for a selected credit package.
2. POST /webhook – Stripe webhook endpoint to listen for successful payments and credit the user.
"""

import os
from typing import Dict

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

# Project imports
try:
    from ..auth import get_current_user  # type: ignore
    from ..credits import add_credits  # type: ignore
except ImportError as e:
    raise ImportError(
        "Could not import required modules for payments. Ensure `auth.py` and `credits.py` exist."
    ) from e

router = APIRouter(
    prefix="",
    tags=["payments"],
    dependencies=[Depends(get_current_user)],
)

# Initialize Stripe with secret key from environment
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
if not stripe.api_key:
    # Log a warning but don't crash startup
    print("WARNING: STRIPE_SECRET_KEY not set. Payment endpoints will fail.")

# Define available credit packages (package_id -> (credits, price_in_cents))
CREDIT_PACKAGES: Dict[str, Dict[str, int]] = {
    "basic": {"credits": 100, "price_cents": 500},      # $5.00
    "standard": {"credits": 250, "price_cents": 1100},  # $11.00
    "premium": {"credits": 600, "price_cents": 2500},   # $25.00
}


@router.post("/purchase")
async def purchase_credits(
    package_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a Stripe Checkout Session for the requested credit package.

    The session includes metadata to identify the user and the package so
    that the webhook can credit the appropriate amount after payment.
    """
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    if package_id not in CREDIT_PACKAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid credit package selected.",
        )

    package = CREDIT_PACKAGES[package_id]

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"{package['credits']} Credits ({package_id.title()})",
                        },
                        "unit_amount": package["price_cents"],
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url="https://your-frontend.com/payment-success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://your-frontend.com/payment-cancelled",
            metadata={
                "user_id": str(current_user.get("sub")),  # Assuming JWT 'sub' claim holds user ID
                "package_id": package_id,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe checkout session creation failed: {str(exc)}",
        )

    return {"checkout_url": checkout_session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe webhook endpoint to handle asynchronous events.

    Listens for `checkout.session.completed` events, verifies the signature,
    extracts user and package information from metadata, and credits the user.
    """
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
         return JSONResponse(status_code=500, content={"error": "STRIPE_WEBHOOK_SECRET not set"})

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=sig_header, secret=webhook_secret
        )
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        user_id_str = metadata.get("user_id")
        package_id = metadata.get("package_id")

        if not user_id_str or not package_id:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing user_id or package_id in metadata"},
            )

        try:
            user_id = int(user_id_str)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid user_id format in metadata"},
            )

        package = CREDIT_PACKAGES.get(package_id)
        if not package:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown package_id: {package_id}"},
            )

        # Credit the user
        try:
            add_credits(user_id=user_id, amount=package["credits"])
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to credit user: {str(exc)}"},
            )

    return JSONResponse(status_code=200, content={"status": "success"})
