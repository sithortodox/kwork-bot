import os
import json
import time
import logging
import random
import string
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PROMOS_FILE = os.path.join(DATA_DIR, "promos.json")


def _load_promos() -> dict:
    try:
        with open(PROMOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_promos(data: dict):
    os.makedirs(os.path.dirname(PROMOS_FILE), exist_ok=True)
    with open(PROMOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_promo_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def create_promo(
    code: str = None,
    discount_percent: int = 0,
    discount_amount: int = 0,
    plan: str = None,
    period: str = None,
    max_uses: int = -1,
    expires_days: int = 30,
    description: str = "",
) -> dict:
    promos = _load_promos()
    
    if code is None:
        code = generate_promo_code()
    
    if code in promos:
        return {"error": "Промокод уже существует"}
    
    promo_data = {
        "code": code,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "plan": plan,
        "period": period,
        "max_uses": max_uses,
        "current_uses": 0,
        "created_at": time.time(),
        "expires_at": time.time() + (expires_days * 24 * 60 * 60),
        "description": description,
        "used_by": [],
    }
    
    promos[code] = promo_data
    _save_promos(promos)
    
    log.info("Created promo code: %s", code)
    return promo_data


def validate_promo(code: str, chat_id: int = None) -> dict:
    promos = _load_promos()
    
    code = code.upper()
    
    if code not in promos:
        return {"valid": False, "error": "Промокод не найден"}
    
    promo = promos[code]
    
    if time.time() > promo.get("expires_at", 0):
        return {"valid": False, "error": "Срок действия промокода истек"}
    
    if promo.get("max_uses", -1) > 0 and promo.get("current_uses", 0) >= promo.get("max_uses", -1):
        return {"valid": False, "error": "Промокод достиг лимита использований"}
    
    if chat_id and str(chat_id) in promo.get("used_by", []):
        return {"valid": False, "error": "Вы уже использовали этот промокод"}
    
    return {"valid": True, "promo": promo}


def apply_promo(code: str, chat_id: int, original_price: int, plan: str, period: str) -> dict:
    validation = validate_promo(code, chat_id)
    
    if not validation.get("valid"):
        return validation
    
    promo = validation["promo"]
    
    if promo.get("plan") and promo["plan"] != plan:
        return {"valid": False, "error": f"Промокод действителен только для тарифа {promo['plan']}"}
    
    if promo.get("period") and promo["period"] != period:
        return {"valid": False, "error": f"Промокод действителен только для периода {promo['period']}"}
    
    discount = 0
    
    if promo.get("discount_percent", 0) > 0:
        discount = int(original_price * promo["discount_percent"] / 100)
    elif promo.get("discount_amount", 0) > 0:
        discount = promo["discount_amount"]
    
    final_price = max(0, original_price - discount)
    
    promos = _load_promos()
    promos[code]["current_uses"] = promos[code].get("current_uses", 0) + 1
    if "used_by" not in promos[code]:
        promos[code]["used_by"] = []
    promos[code]["used_by"].append(str(chat_id))
    _save_promos(promos)
    
    log.info("Applied promo %s for user %d: %d₽ -> %d₽", code, chat_id, original_price, final_price)
    
    return {
        "valid": True,
        "original_price": original_price,
        "discount": discount,
        "final_price": final_price,
        "promo": promo,
    }


def list_promos(include_expired: bool = False) -> list:
    promos = _load_promos()
    promo_list = []
    
    for code, promo in promos.items():
        if not include_expired and time.time() > promo.get("expires_at", 0):
            continue
        promo_list.append(promo)
    
    promo_list.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return promo_list


def delete_promo(code: str) -> bool:
    promos = _load_promos()
    
    if code in promos:
        del promos[code]
        _save_promos(promos)
        log.info("Deleted promo code: %s", code)
        return True
    
    return False


def get_promo_stats() -> dict:
    promos = _load_promos()
    
    total = len(promos)
    active = sum(1 for p in promos.values() if time.time() <= p.get("expires_at", 0))
    total_uses = sum(p.get("current_uses", 0) for p in promos.values())
    total_discount = 0
    
    for promo in promos.values():
        uses = promo.get("current_uses", 0)
        if promo.get("discount_percent", 0) > 0:
            avg_price = 500
            total_discount += int(avg_price * uses * promo["discount_percent"] / 100)
        elif promo.get("discount_amount", 0) > 0:
            total_discount += promo["discount_amount"] * uses
    
    return {
        "total": total,
        "active": active,
        "total_uses": total_uses,
        "total_discount": total_discount,
    }


PREDEFINED_PROMOS = [
    {"code": "WELCOME20", "discount_percent": 20, "description": "Скидка 20% на первый месяц", "max_uses": 1000},
    {"code": "YEAR30", "discount_percent": 30, "period": "yearly", "description": "Скидка 30% на годовую подписку", "max_uses": 500},
    {"code": "PRO500", "discount_amount": 500, "plan": "pro", "description": "Скидка 500₽ на Pro тариф", "max_uses": 100},
    {"code": "BASIC199", "discount_amount": 100, "plan": "basic", "description": "Basic за 199₽ вместо 299₽", "max_uses": 200},
]


def init_predefined_promos():
    promos = _load_promos()
    
    for preset in PREDEFINED_PROMOS:
        if preset["code"] not in promos:
            create_promo(
                code=preset["code"],
                discount_percent=preset.get("discount_percent", 0),
                discount_amount=preset.get("discount_amount", 0),
                plan=preset.get("plan"),
                period=preset.get("period"),
                max_uses=preset.get("max_uses", -1),
                expires_days=365,
                description=preset.get("description", ""),
            )
    
    log.info("Initialized predefined promos")
