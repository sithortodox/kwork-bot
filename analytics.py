import os
import json
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
METRICS_FILE = os.path.join(DATA_DIR, "metrics.json")


def _load_metrics() -> dict:
    try:
        with open(METRICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "daily": {},
            "monthly": {},
            "events": [],
        }


def _save_metrics(data: dict):
    os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def track_event(event_type: str, chat_id: int, metadata: dict = None):
    metrics = _load_metrics()
    
    today = datetime.now().strftime("%Y-%m-%d")
    month = datetime.now().strftime("%Y-%m")
    
    if today not in metrics["daily"]:
        metrics["daily"][today] = {
            "registrations": 0,
            "payments": 0,
            "revenue": 0,
            "notifications_sent": 0,
            "users_active": 0,
            "subscriptions_basic": 0,
            "subscriptions_pro": 0,
            "referrals": 0,
            "promos_used": 0,
        }
    
    if month not in metrics["monthly"]:
        metrics["monthly"][month] = {
            "registrations": 0,
            "payments": 0,
            "revenue": 0,
            "notifications_sent": 0,
            "subscriptions_basic": 0,
            "subscriptions_pro": 0,
            "referrals": 0,
            "promos_used": 0,
        }
    
    if event_type == "registration":
        metrics["daily"][today]["registrations"] += 1
        metrics["monthly"][month]["registrations"] += 1
    
    elif event_type == "payment":
        amount = metadata.get("amount", 0) if metadata else 0
        metrics["daily"][today]["payments"] += 1
        metrics["daily"][today]["revenue"] += amount
        metrics["monthly"][month]["payments"] += 1
        metrics["monthly"][month]["revenue"] += amount
        
        if metadata and metadata.get("plan") == "basic":
            metrics["daily"][today]["subscriptions_basic"] += 1
            metrics["monthly"][month]["subscriptions_basic"] += 1
        elif metadata and metadata.get("plan") == "pro":
            metrics["daily"][today]["subscriptions_pro"] += 1
            metrics["monthly"][month]["subscriptions_pro"] += 1
    
    elif event_type == "notification":
        metrics["daily"][today]["notifications_sent"] += 1
        metrics["monthly"][month]["notifications_sent"] += 1
    
    elif event_type == "referral":
        metrics["daily"][today]["referrals"] += 1
        metrics["monthly"][month]["referrals"] += 1
    
    elif event_type == "promo_used":
        metrics["daily"][today]["promos_used"] += 1
        metrics["monthly"][month]["promos_used"] += 1
    
    metrics["events"].append({
        "type": event_type,
        "chat_id": chat_id,
        "timestamp": time.time(),
        "metadata": metadata or {},
    })
    
    if len(metrics["events"]) > 1000:
        metrics["events"] = metrics["events"][-1000:]
    
    _save_metrics(metrics)


def calculate_dau() -> int:
    from telegram_bot import load_users, load_subscriptions
    
    users = load_users()
    subs = load_subscriptions()
    today = datetime.now().strftime("%Y-%m-%d")
    
    active = 0
    for uid, sub in subs.items():
        if sub.get("notifications_date") == today:
            active += 1
    
    return active


def calculate_wau() -> int:
    from telegram_bot import load_subscriptions
    
    subs = load_subscriptions()
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    active = set()
    for uid, sub in subs.items():
        if sub.get("notifications_date", "2000-01-01") >= week_ago:
            active.add(uid)
    
    return len(active)


def calculate_mau() -> int:
    from telegram_bot import load_users
    
    users = load_users()
    month_ago = time.time() - (30 * 24 * 60 * 60)
    
    active = sum(
        1 for u in users.values()
        if u.get("registered_at", 0) > month_ago or u.get("enabled", True)
    )
    
    return active


def calculate_mrr() -> dict:
    from telegram_bot import load_subscriptions
    
    subs = load_subscriptions()
    
    mrr = {"basic": 0, "pro": 0, "total": 0}
    
    for uid, sub in subs.items():
        plan = sub.get("plan", "free")
        expires = sub.get("expires_at", 0)
        
        if expires > time.time():
            if plan == "basic":
                mrr["basic"] += 299
            elif plan == "pro":
                mrr["pro"] += 799
    
    mrr["total"] = mrr["basic"] + mrr["pro"]
    return mrr


def calculate_conversion_rates() -> dict:
    from telegram_bot import load_users, load_subscriptions
    
    users = load_users()
    subs = load_subscriptions()
    
    total_users = len(users)
    if total_users == 0:
        return {"free_to_paid": 0, "trial_to_paid": 0, "registration_to_active": 0}
    
    paid_users = sum(1 for s in subs.values() if s.get("plan") in ["basic", "pro"])
    trial_users = sum(1 for s in subs.values() if s.get("trial_ends_at", 0) > time.time())
    active_users = sum(1 for u in users.values() if u.get("enabled", True))
    
    return {
        "free_to_paid": (paid_users / total_users * 100) if total_users > 0 else 0,
        "trial_to_paid": (paid_users / (paid_users + trial_users) * 100) if (paid_users + trial_users) > 0 else 0,
        "registration_to_active": (active_users / total_users * 100) if total_users > 0 else 0,
    }


def calculate_churn_rate() -> dict:
    from telegram_bot import load_subscriptions
    
    subs = load_subscriptions()
    
    month_ago = time.time() - (30 * 24 * 60 * 60)
    
    churned = 0
    total_expired = 0
    
    for uid, sub in subs.items():
        expires = sub.get("expires_at", 0)
        plan = sub.get("plan", "free")
        
        if plan in ["basic", "pro"] and expires > 0:
            if month_ago < expires <= time.time():
                churned += 1
            total_expired += 1
    
    return {
        "churned": churned,
        "total": total_expired,
        "rate": (churned / total_expired * 100) if total_expired > 0 else 0,
    }


def calculate_arpu() -> dict:
    from telegram_bot import load_users, load_subscriptions
    
    users = load_users()
    subs = load_subscriptions()
    
    total_users = len(users)
    if total_users == 0:
        return {"daily": 0, "monthly": 0}
    
    metrics = _load_metrics()
    today = datetime.now().strftime("%Y-%m-%d")
    month = datetime.now().strftime("%Y-%m")
    
    daily_revenue = metrics["daily"].get(today, {}).get("revenue", 0)
    monthly_revenue = metrics["monthly"].get(month, {}).get("revenue", 0)
    
    return {
        "daily": daily_revenue / total_users if total_users > 0 else 0,
        "monthly": monthly_revenue / total_users if total_users > 0 else 0,
    }


def calculate_ltv() -> dict:
    avg_subscription_months = 6
    
    ltv = {
        "basic": 299 * avg_subscription_months,
        "pro": 799 * avg_subscription_months,
    }
    
    return ltv


def get_daily_metrics(days: int = 30) -> list:
    metrics = _load_metrics()
    
    daily_data = []
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        if date in metrics["daily"]:
            daily_data.append({
                "date": date,
                **metrics["daily"][date]
            })
    
    daily_data.reverse()
    return daily_data


def get_growth_metrics() -> dict:
    metrics = _load_metrics()
    
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    today_data = metrics["daily"].get(today, {})
    yesterday_data = metrics["daily"].get(yesterday, {})
    week_data = metrics["daily"].get(week_ago, {})
    month_data = metrics["daily"].get(month_ago, {})
    
    def calc_growth(current, previous):
        if previous == 0:
            return 0 if current == 0 else 100
        return ((current - previous) / previous) * 100
    
    return {
        "registrations": {
            "today": today_data.get("registrations", 0),
            "yesterday": yesterday_data.get("registrations", 0),
            "growth": calc_growth(today_data.get("registrations", 0), yesterday_data.get("registrations", 0)),
        },
        "revenue": {
            "today": today_data.get("revenue", 0),
            "yesterday": yesterday_data.get("revenue", 0),
            "growth": calc_growth(today_data.get("revenue", 0), yesterday_data.get("revenue", 0)),
        },
        "payments": {
            "today": today_data.get("payments", 0),
            "yesterday": yesterday_data.get("payments", 0),
            "growth": calc_growth(today_data.get("payments", 0), yesterday_data.get("payments", 0)),
        },
        "notifications": {
            "today": today_data.get("notifications_sent", 0),
            "yesterday": yesterday_data.get("notifications_sent", 0),
            "growth": calc_growth(today_data.get("notifications_sent", 0), yesterday_data.get("notifications_sent", 0)),
        },
    }


def generate_analytics_report() -> str:
    from telegram_bot import load_users
    
    users = load_users()
    mrr = calculate_mrr()
    conversion = calculate_conversion_rates()
    churn = calculate_churn_rate()
    arpu = calculate_arpu()
    ltv = calculate_ltv()
    growth = get_growth_metrics()
    
    total_users = len(users)
    dau = calculate_dau()
    wau = calculate_wau()
    mau = calculate_mau()
    
    report = f"""
╔════════════════════════════════╗
║     📊 АНАЛИТИКА БОТА          ║
╚════════════════════════════════╝

<b>👥 Активность пользователей</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• DAU (сегодня): {dau}
• WAU (неделя): {wau}
• MAU (месяц): {mau}
• Всего пользователей: {total_users}

<b>💰 Доход (MRR)</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Basic: {mrr['basic']:,}₽
• Pro: {mrr['pro']:,}₽
• <b>Итого MRR: {mrr['total']:,}₽</b>

<b>📈 Конверсия</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Free → Paid: {conversion['free_to_paid']:.1f}%
• Trial → Paid: {conversion['trial_to_paid']:.1f}%
• Reg → Active: {conversion['registration_to_active']:.1f}%

<b>📉 Отток (Churn)</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Отвалилось: {churn['churned']}
• Rate: {churn['rate']:.1f}%

<b>💵 ARPU & LTV</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• ARPU (день): {arpu['daily']:.1f}₽
• ARPU (месяц): {arpu['monthly']:.1f}₽
• LTV Basic: {ltv['basic']:,}₽
• LTV Pro: {ltv['pro']:,}₽

<b>📊 Рост (сегодня vs вчера)</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Регистрации: {growth['registrations']['growth']:+.1f}%
• Доход: {growth['revenue']['growth']:+.1f}%
• Оплаты: {growth['payments']['growth']:+.1f}%
• Уведомления: {growth['notifications']['growth']:+.1f}%
"""
    
    return report.strip()
