import os
import json
import hmac
import hashlib
import logging
from flask import Flask, request, jsonify

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

app = Flask(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your-secret-key")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")


def verify_yookassa_signature(request) -> bool:
    signature = request.headers.get("X-Signature")
    if not signature:
        log.warning("Missing X-Signature header in webhook")
        return False
    
    try:
        payload = request.data
        expected = hmac.new(
            YOOKASSA_SECRET_KEY.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        if hmac.compare_digest(signature, expected):
            return True
        else:
            log.warning("Invalid webhook signature. Expected: %s, Got: %s", expected[:16], signature[:16])
            return False
    except Exception as e:
        log.error("Error verifying webhook signature: %s", e)
        return False


@app.route("/webhook/yookassa", methods=["POST"])
def yookassa_webhook():
    try:
        if not verify_yookassa_signature(request):
            log.warning("Unauthorized webhook attempt from IP: %s", request.remote_addr)
            return jsonify({"error": "Invalid signature"}), 401
        
        data = request.json
        
        log.info("Received ЮKassa webhook: %s", json.dumps(data, indent=2))
        
        from payment import process_webhook
        result = process_webhook(data)
        
        if result.get("status") == "success":
            chat_id = result.get("chat_id")
            plan = result.get("plan")
            days = result.get("days")
            
            log.info("Subscription activated for user %s: %s for %d days", chat_id, plan, days)
            
            from telegram_bot import send_message, notify_admin
            plan_names = {"basic": "💼 Basic", "pro": "⭐ Pro"}
            send_message(
                int(chat_id),
                f"✅ <b>Подписка активирована!</b>\n\n"
                f"Тариф: {plan_names.get(plan, plan)}\n"
                f"Период: {days} дней\n\n"
                f"Спасибо за поддержку! 🙏",
            )
            
            notify_admin(f"💰 Оплата: {plan_names.get(plan, plan)} на {days} дней (user {chat_id})", "success")
        
        elif result.get("status") == "canceled":
            chat_id = data.get("object", {}).get("metadata", {}).get("chat_id")
            if chat_id:
                from telegram_bot import notify_admin
                notify_admin(f"❌ Платеж отменен: user {chat_id}", "warning")
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        log.error("Webhook error: %s", e, exc_info=True)
        from telegram_bot import notify_admin
        notify_admin(f"🚨 Webhook error: {e}", "error")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


def run_webhook_server(port=8080):
    log.info("Starting webhook server on port %d", port)
    app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run_webhook_server()
