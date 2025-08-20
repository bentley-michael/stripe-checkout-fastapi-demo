import os
import stripe
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/checkout", tags=["checkout"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
ENABLE_PAYWALL = str(os.getenv("ENABLE_PAYWALL", "false")).lower() in ("1","true","yes","on")

APP_URL = (os.getenv("APP_URL") or "http://127.0.0.1:8000").rstrip("/")
SUCCESS_URL = os.getenv("SUCCESS_URL") or f"{APP_URL}/success"
CANCEL_URL = os.getenv("CANCEL_URL") or f"{APP_URL}/cancel"

# Set in your env (e.g., price_12345...)
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")

@router.post("/create-session")
async def create_checkout_session():
    # Allow dev-bypass when paywall is off
    if not ENABLE_PAYWALL:
        return JSONResponse({"checkout_url": f"{SUCCESS_URL}?demo=true"})

    if not stripe.api_key or not STRIPE_PRICE_ID:
        raise HTTPException(status_code=400, detail="Stripe not configured (missing key or price id)")

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            success_url=SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=CANCEL_URL,
            automatic_tax={"enabled": False},
            billing_address_collection="auto",
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
