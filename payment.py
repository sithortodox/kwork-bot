import os
import json
import time
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
YOOKASSA_API_URL = "https://api.yookassa.ru/v3/payments"

PLANS_PRICES = {
    "basic_monthly": {"amount": "299.00", "description": "Basic тариф на 1 месяц"},
    "basic_yearly": {"amount": "2990.00", "description": "Basic тариф на 1 год (-17%)"},
    "pro_monthly": {"amount": "799.00", "description": "Pro тариф на 1 месяц"},
    "pro_yearly": {"amount": "6999.00", "description": "Pro тариф на 1 год (-27%)"},
}


def create_payment(chat_id: int, plan_type: str, return_url: str, promo_code: str = None) -> dict:
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        log.error("ЮKassa credentials not configured")
        return {"error": "Payment not configured. Contact support."}
    
    if plan_type not in PLANS_PRICES:
        return {"error": "Invalid plan type"}
    
    plan_info = PLANS_PRICES[plan_type]
    original_price = float(plan_info["amount"])
    
    final_price = original_price
    
    if promo_code:
        from promos import apply_promo
        result = apply_promo(promo_code, chat_id, int(original_price), plan_type.split("_")[0], plan_type.split("_")[1])
        if result.get("valid"):
            final_price = float(result["final_price"])
            log.info("Applied promo %s for user %d: %.0f -> %.0f", promo_code, chat_id, original_price, final_price)
    
    idempotence_key = f"{chat_id}_{int(time.time())}_{plan_type}"
    
    headers = {
        "Content-Type": "application/json",
        "Idempotence-Key": idempotence_key,
    }
    
    data = {
        "amount": {
            "value": f"{final_price:.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": return_url
        },
        "capture": True,
        "description": f"{plan_info['description']} (промокод: {promo_code})" if promo_code else plan_info["description"],
        "metadata": {
            "chat_id": str(chat_id),
            "plan_type": plan_type,
            "promo_code": promo_code or "",
            "original_price": str(original_price),
            "discount": str(original_price - final_price),
        },
        "receipt": {
            "customer": {
                "email": f"user_{chat_id}@kwork-bot.local",
            },
            "items": [
                {
                    "description": plan_info["description"],
                    "quantity": "1",
                    "amount": {
                        "value": f"{final_price:.2f}",
                        "currency": "RUB"
                    },
                    "vat_code": 1
                }
            ]
        }
    }
    
    try:
        resp = requests.post(
            YOOKASSA_API_URL,
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            headers=headers,
            json=data,
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()
            log.info("Payment created for user %d: %s", chat_id, result.get("id"))
            return {
                "payment_id": result.get("id"),
                "confirmation_url": result.get("confirmation", {}).get("confirmation_url"),
                "status": result.get("status")
            }
        else:
            log.error("ЮKassa error: %s %s", resp.status_code, resp.text)
            return {"error": f"Payment error: {resp.status_code}"}
            
    except Exception as e:
        log.error("Payment creation failed: %s", e)
        return {"error": "Payment service unavailable"}


def check_payment(payment_id: str) -> dict:
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        return {"error": "Payment not configured"}
    
    try:
        resp = requests.get(
            f"{YOOKASSA_API_URL}/{payment_id}",
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()
            return {
                "status": result.get("status"),
                "metadata": result.get("metadata", {}),
                "amount": result.get("amount", {}).get("value"),
                "paid": result.get("paid", False)
            }
        else:
            log.error("Payment check error: %s", resp.status_code)
            return {"error": "Payment not found"}
            
    except Exception as e:
        log.error("Payment check failed: %s", e)
        return {"error": "Payment service unavailable"}


def process_webhook(data: dict) -> dict:
    event = data.get("event")
    
    if event not in ["payment.succeeded", "payment.canceled", "payment.waiting_for_capture"]:
        log.warning("Unknown webhook event: %s", event)
        return {"status": "ignored"}
    
    payment = data.get("object", {})
    payment_id = payment.get("id")
    status = payment.get("status")
    metadata = payment.get("metadata", {})
    
    chat_id = metadata.get("chat_id")
    plan_type = metadata.get("plan_type")
    
    if not chat_id:
        log.error("No chat_id in payment metadata")
        return {"status": "error", "message": "No chat_id"}
    
    log.info("Webhook: payment %s %s for user %s", payment_id, status, chat_id)
    
    if status == "succeeded":
        from telegram_bot import activate_subscription
        
        days = 365 if "yearly" in plan_type else 30
        plan = "pro" if "pro" in plan_type else "basic"
        
        activate_subscription(int(chat_id), plan, days)
        
        return {
            "status": "success",
            "chat_id": chat_id,
            "plan": plan,
            "days": days
        }
    
    return {"status": status}
