import os
import json
import asyncio
import logging
import re
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from kwork import Kwork

from telegram_bot import (
    send_project_to_user, add_sent_project, is_user_notified,
    get_all_active_users, get_user_categories,
    start_bot, get_interval, is_check_requested, clear_check_requested,
    ALL_SUBCATEGORIES, can_receive_notification, increment_notifications_count,
    get_user_plan, add_project_to_history, is_user_in_notification_hours,
    notify_admin,
)

from analytics import track_event

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    RETRY_AVAILABLE = True
except ImportError:
    RETRY_AVAILABLE = False

load_dotenv()

WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8080))

KWORK_EMAIL = os.getenv("KWORK_EMAIL")
KWORK_PASSWORD = os.getenv("KWORK_PASSWORD")

MOSCOW_TZ = timezone(timedelta(hours=3))
WORK_START = 7
WORK_END = 23

DATA_DIR = Path(__file__).parent / "data"
SEEN_FILE = DATA_DIR / "seen_projects.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

ALL_CATEGORY_IDS = [15, 11, 5, 17, 45, 7, 83]


def load_seen() -> set:
    if SEEN_FILE.exists():
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False)


def strip_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return ' '.join(text.split())


def detect_categories(title: str, description: str) -> list:
    combined = (title + " " + description).lower()
    detected = []
    
    for sub_id, sub_info in ALL_SUBCATEGORIES.items():
        sub_keywords = sub_info.get("keywords", [])
        sub_matched = any(kw in combined for kw in sub_keywords)
        
        if sub_matched:
            detected.append(sub_id)
            
            filters = sub_info.get("filters", {})
            for filter_id, filter_data in filters.items():
                filter_keywords = filter_data.get("keywords", [])
                filter_matched = any(kw in combined for kw in filter_keywords)
                
                if filter_matched:
                    full_filter_id = f"{sub_id}:{filter_id}"
                    detected.append(full_filter_id)
    
    return detected


if RETRY_AVAILABLE:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: log.warning(
            "Retrying fetch_and_notify (attempt %d)...", 
            retry_state.attempt_number
        )
    )
    async def fetch_and_notify(api: Kwork, seen: set) -> set:
        return await _fetch_and_notify_impl(api, seen)
else:
    async def fetch_and_notify(api: Kwork, seen: set) -> set:
        return await _fetch_and_notify_impl(api, seen)


async def _fetch_and_notify_impl(api: Kwork, seen: set) -> set:
    new_ids = set()
    
    try:
        projects = await api.get_projects(categories_ids=ALL_CATEGORY_IDS)
        log.info("Fetched %d projects", len(projects))
    except Exception as e:
        log.error("Failed to fetch projects from Kwork API: %s", e)
        notify_admin(f"⚠️ Kwork API error: {e}", "warning")
        return new_ids
    
    active_users = get_all_active_users()
    
    if not active_users:
        log.info("No active users registered")
        return new_ids
    
    for p in projects:
        if not p.id or str(p.id) in seen:
            continue
        
        title = p.title or ""
        description = strip_html(getattr(p, "description", "") or "")
        price = f"{p.price} руб." if p.price else "Цена не указана"
        url = f"https://kwork.ru/projects/{p.id}"
        
        detected_cats = detect_categories(title, description)
        if not detected_cats:
            seen.add(str(p.id))
            continue
        
        project_data = {
            "id": str(p.id),
            "title": title,
            "price": price,
            "description": description[:500],
            "url": url,
            "categories": detected_cats,
        }
        
        add_sent_project(str(p.id), project_data)
        
        notified_count = 0
        for chat_id_str, user_data in active_users.items():
            chat_id = int(chat_id_str)
            user_cats = user_data.get("categories", [])
            
            if not user_cats:
                continue
            
            if is_user_notified(str(p.id), chat_id):
                continue
            
            can_notify, reason = can_receive_notification(chat_id)
            if not can_notify:
                log.debug("User %d: %s", chat_id, reason)
                continue
            
            if not is_user_in_notification_hours(chat_id):
                log.debug("User %d: outside notification hours", chat_id)
                continue
            
            matched_cats = [c for c in detected_cats if c in user_cats]
            if not matched_cats:
                user_subcats = set()
                for uc in user_cats:
                    if ":" in uc:
                        user_subcats.add(uc.split(":")[0])
                    else:
                        user_subcats.add(uc)
                
                detected_subcats = set()
                for dc in detected_cats:
                    if ":" in dc:
                        detected_subcats.add(dc.split(":")[0])
                    else:
                        detected_subcats.add(dc)
                
                matched_subcats = user_subcats & detected_subcats
                if not matched_subcats:
                    continue
                matched_cats = list(matched_subcats)
            
            # Проверка лимита категорий
            plan = get_user_plan(chat_id)
            if plan["max_categories"] > 0:
                user_cats_count = len([c for c in user_cats if ":" not in c])
                if user_cats_count > plan["max_categories"]:
                    continue
            
            # Проверка доступа к фильтрам
            if not plan["filters_allowed"]:
                if any(":" in c for c in matched_cats):
                    matched_cats = [c for c in matched_cats if ":" not in c]
                    if not matched_cats:
                        continue
            
            first_cat = matched_cats[0]
            
            if ":" in first_cat:
                parts = first_cat.split(":")
                sub_id = parts[0]
                filter_id = parts[1] if len(parts) > 1 else None
                sub_info = ALL_SUBCATEGORIES.get(sub_id, {})
                cat_name = sub_info.get("name", sub_id)
                parent_name = sub_info.get("parent_name", "")
                
                if filter_id and sub_info.get("filters"):
                    filter_info = sub_info["filters"].get(filter_id, {})
                    filter_name = filter_info.get("name", filter_id)
                    cat_display = f"{parent_name} / {cat_name} / {filter_name}"
                else:
                    cat_display = f"{parent_name} / {cat_name}" if parent_name else cat_name
            else:
                cat_info = ALL_SUBCATEGORIES.get(first_cat, {})
                cat_name = cat_info.get("name", first_cat)
                parent_name = cat_info.get("parent_name", "")
                cat_display = f"{parent_name} / {cat_name}" if parent_name else cat_name
            
            # Добавляем водяной знак для Free
            watermark = "\n\n— <i>Free тариф</i> | /subscription" if plan.get("watermark") else ""
            
            text = (
                f"📂 <b>{cat_display}</b>\n\n"
                f"<b>{title}</b>\n\n"
                f"💰 {price}\n\n"
                f"📝 {description[:300]}"
                f"{watermark}"
            )
            
            if send_project_to_user(chat_id, text, url, first_cat, str(p.id)):
                increment_notifications_count(chat_id)
                track_event("notification", chat_id)
                add_project_to_history(chat_id, str(p.id), {
                    "title": title,
                    "price": price,
                    "description": description,
                    "url": url,
                    "category": cat_display,
                })
                notified_count += 1
        
        if notified_count > 0:
            new_ids.add(str(p.id))
            cat_names = []
            for c in detected_cats:
                if ":" in c:
                    parts = c.split(":")
                    sub_id = parts[0]
                    filter_id = parts[1] if len(parts) > 1 else None
                    sub_info = ALL_SUBCATEGORIES.get(sub_id, {})
                    sub_name = sub_info.get("name", sub_id)
                    if filter_id and sub_info.get("filters"):
                        filter_name = sub_info["filters"].get(filter_id, {}).get("name", filter_id)
                        cat_names.append(f"{sub_name}/{filter_name}")
                    else:
                        cat_names.append(sub_name)
                else:
                    cat_names.append(ALL_SUBCATEGORIES.get(c, {}).get("name", c))
            log.info("New: %s [%s] — %s → %d users", p.id, ", ".join(cat_names), title, notified_count)
        else:
            seen.add(str(p.id))
    
    return new_ids


async def main():
    seen = load_seen()
    log.info("Loaded %d seen projects", len(seen))
    
    start_bot()
    
    if SCHEDULER_AVAILABLE:
        from backup import backup_data
        scheduler = AsyncIOScheduler()
        scheduler.add_job(backup_data, 'cron', hour=3, minute=0)
        scheduler.start()
        log.info("Backup scheduler started (daily at 03:00)")
    
    async with Kwork(
        login=KWORK_EMAIL,
        password=KWORK_PASSWORD,
        timeout=30.0,
    ) as api:
        me = await api.get_me()
        log.info("Logged in as %s", me.username)
        
        while True:
            now_msk = datetime.now(MOSCOW_TZ)
            hour_msk = now_msk.hour
            
            should_check = False
            
            if is_check_requested():
                should_check = True
                clear_check_requested()
                log.info("On-demand check triggered")
            elif WORK_START <= hour_msk < WORK_END:
                should_check = True
            
            if should_check:
                try:
                    new_ids = await fetch_and_notify(api, seen)
                    if new_ids:
                        seen.update(new_ids)
                        save_seen(seen)
                        log.info("Added %d new projects", len(new_ids))
                    else:
                        log.info("No new projects")
                except Exception as e:
                    log.error("Error in check: %s", e)
            else:
                log.info("Outside work hours (07:00-23:00 MSK), current MSK time: %s", now_msk.strftime("%H:%M"))
            
            poll_interval = get_interval()
            log.info("Sleeping %d seconds ...", poll_interval)
            
            for _ in range(poll_interval // 5):
                await asyncio.sleep(5)
                if is_check_requested():
                    log.info("On-demand check detected during sleep")
                    break


def run_webhook_in_thread():
    from webhook import run_webhook_server
    run_webhook_server(port=WEBHOOK_PORT)


if __name__ == "__main__":
    webhook_thread = threading.Thread(target=run_webhook_in_thread, daemon=True)
    webhook_thread.start()
    log.info("Webhook server started on port %d", WEBHOOK_PORT)
    
    asyncio.run(main())
