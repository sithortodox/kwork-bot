import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", 0))

log = logging.getLogger(__name__)

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
SEND_URL = f"{BASE_URL}/sendMessage"
ANSWER_URL = f"{BASE_URL}/answerCallbackQuery"
EDIT_URL = f"{BASE_URL}/editMessageReplyMarkup"
SET_CMDS_URL = f"{BASE_URL}/setMyCommands"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
DEFERRED_FILE = os.path.join(DATA_DIR, "deferred_projects.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
SENT_PROJECTS_FILE = os.path.join(DATA_DIR, "sent_projects.json")
SUBSCRIPTIONS_FILE = os.path.join(DATA_DIR, "subscriptions.json")
HISTORY_FILE = os.path.join(DATA_DIR, "user_history.json")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")
HIDDEN_FILE = os.path.join(DATA_DIR, "hidden_projects.json")
CONTACTS_FILE = os.path.join(DATA_DIR, "contacts.json")
FAQ_CUSTOM_FILE = os.path.join(DATA_DIR, "faq_custom.json")

PLANS = {
    "free": {
        "name": "Free",
        "emoji": "🆓",
        "price": 0,
        "notifications_per_day": 5,
        "max_categories": 3,
        "filters_allowed": False,
        "check_interval": 1800,
        "history_days": 3,
        "priority": 0,
        "watermark": True,
    },
    "basic": {
        "name": "Basic",
        "emoji": "💼",
        "price": 299,
        "price_yearly": 2990,
        "notifications_per_day": 30,
        "max_categories": 10,
        "filters_allowed": True,
        "check_interval": 900,
        "history_days": 7,
        "priority": 1,
        "watermark": False,
    },
    "pro": {
        "name": "Pro",
        "emoji": "⭐",
        "price": 799,
        "price_yearly": 6999,
        "notifications_per_day": -1,
        "max_categories": -1,
        "filters_allowed": True,
        "check_interval": 60,
        "history_days": 30,
        "priority": 2,
        "watermark": False,
    },
    "admin": {
        "name": "Admin",
        "emoji": "🔐",
        "price": 0,
        "notifications_per_day": -1,
        "max_categories": -1,
        "filters_allowed": True,
        "check_interval": 60,
        "history_days": 999,
        "priority": 99,
        "watermark": False,
    },
}

_lock = threading.Lock()
_update_offset = 0
_admin_states = {}
_user_states = {}

CHECK_FLAG_FILE = os.path.join(DATA_DIR, ".check_requested")


def _set_check_requested():
    with open(CHECK_FLAG_FILE, "w") as f:
        f.write("1")


def _clear_check_requested():
    if os.path.exists(CHECK_FLAG_FILE):
        os.remove(CHECK_FLAG_FILE)


def is_check_requested() -> bool:
    return os.path.exists(CHECK_FLAG_FILE)


def clear_check_requested():
    _clear_check_requested()


def _set_admin_state(chat_id: int, state: str):
    _admin_states[chat_id] = state


def _get_admin_state(chat_id: int) -> str:
    return _admin_states.get(chat_id, "")


def _clear_admin_state(chat_id: int):
    _admin_states.pop(chat_id, None)


def _set_user_state(chat_id: int, state: str):
    _user_states[chat_id] = state


def _get_user_state(chat_id: int) -> str:
    return _user_states.get(chat_id, "")


def _clear_user_state(chat_id: int):
    _user_states.pop(chat_id, None)


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

CATEGORIES_TREE = {
    "15": {
        "name": "Дизайн",
        "subcategories": {
            "25": {
                "name": "Логотип и брендинг",
                "keywords": ["логотип", "брендинг", "фирменный стиль", "лого", "айдентика"],
                "filters": {
                    "logo": {"name": "Логотип", "keywords": ["логотип", "лого", "logo"]},
                    "brandbook": {"name": "Брендбук", "keywords": ["брендбук", "brandbook", "гайдлайн"]},
                    "identity": {"name": "Фирменный стиль", "keywords": ["фирменный стиль", "айдентика", "identity"]},
                    "packaging": {"name": "Упаковка", "keywords": ["упаковк", "этикетк", "дизайн упаковк"]},
                },
            },
            "24": {"name": "Веб и мобильный дизайн", "keywords": ["веб дизайн", "дизайн сайта", "мобильный дизайн", "ui дизайн", "ux дизайн"]},
            "28": {"name": "Арт и иллюстрации", "keywords": ["арт", "иллюстраци", "рисунок", "рисовани", "график"]},
            "27": {"name": "Полиграфия", "keywords": ["полиграфи", "печать", "визитк", "буклет", "листовк"]},
            "90": {"name": "Интерьер и экстерьер", "keywords": ["интерьер", "экстерьер", "дизайн помещения", "3d визуализация"]},
            "250": {"name": "Промышленный дизайн", "keywords": ["промышленный дизайн", "3d модель", "прототип"]},
            "306": {"name": "ИИ-генерация изображений", "keywords": ["midjourney", "stable diffusion", "dalle", "нейросет", "генерац"]},
            "270": {"name": "Презентации и инфографика", "keywords": ["презентац", "инфографик", "слайд"]},
            "68": {"name": "Обработка и редактирование", "keywords": ["обработк", "ретушь", "фотошоп", "редактировани"]},
            "272": {"name": "Наружная реклама", "keywords": ["наружн", "баннер", "билборд"]},
            "286": {"name": "Маркетплейсы и соцсети", "keywords": ["маркетплейс", "карточк", "wb", "ozon", "wildberries"]},
        },
    },
    "11": {
        "name": "Разработка и IT",
        "subcategories": {
            "38": {"name": "Доработка и настройка сайта", "keywords": ["доработк", "настройк", "исправлен", "баг", "багфикс"]},
            "37": {
                "name": "Создание сайта",
                "keywords": ["создание сайта", "разработка сайта", "сделать сайт", "сайт под ключ"],
                "filters": {
                    "landing": {"name": "Landing page", "keywords": ["landing", "лендинг", "посадочн"]},
                    "corporate": {"name": "Корпоративный сайт", "keywords": ["корпоративн", "компании", "бизнес"]},
                    "ecommerce": {"name": "Интернет-магазин", "keywords": ["интернет-магазин", "ecommerce", "магазин", "ishop"]},
                    "bitrix": {"name": "Bitrix", "keywords": ["bitrix", "битрикс"]},
                    "wordpress": {"name": "WordPress", "keywords": ["wordpress", "wp", "вордпресс"]},
                    "tilda": {"name": "Tilda", "keywords": ["tilda", "тильда"]},
                    "react": {"name": "React", "keywords": ["react", "react.js", "next.js", "nextjs"]},
                    "vue": {"name": "Vue.js", "keywords": ["vue", "vue.js", "vuejs", "nuxt"]},
                },
            },
            "41": {
                "name": "Скрипты, боты и mini apps", 
                "keywords": ["скрипт", "бот", "telegram", "телеграм", "автоматизац", "парсер"],
                "filters": {
                    "tg_bot": {"name": "Telegram боты", "keywords": ["telegram бот", "tg бот", "телеграм бот", "telegram bot"]},
                    "whatsapp_bot": {"name": "WhatsApp боты", "keywords": ["whatsapp бот", "вацап бот", "ватсап"]},
                    "vk_bot": {"name": "VK боты", "keywords": ["vk бот", "вк бот", "вконтакте бот"]},
                    "discord_bot": {"name": "Discord боты", "keywords": ["discord бот", "дискорд бот"]},
                    "parser": {"name": "Парсеры", "keywords": ["парсер", "парсинг", "скрапинг", "scraping", "спарсить"]},
                    "automation": {"name": "Автоматизация", "keywords": ["автоматизац", "макрос", "расширени", "плагин"]},
                    "mini_app": {"name": "Mini Apps", "keywords": ["mini app", "mini-app", "tma", "web app"]},
                    "python": {"name": "Python", "keywords": ["python", "питон", "django", "flask", "fastapi"]},
                    "nodejs": {"name": "Node.js", "keywords": ["nodejs", "node.js", "node", "javascript", "js"]},
                    "php": {"name": "PHP", "keywords": ["php", "laravel", "symfony", "wordpress"]},
                },
            },
            "79": {"name": "Верстка", "keywords": ["верстк", "html", "css", "адаптив", "landing"]},
            "80": {"name": "Десктоп программирование", "keywords": ["десктоп", "desktop", "приложение windows", "приложение mac"]},
            "39": {
                "name": "Мобильные приложения",
                "keywords": ["мобильн", "android", "ios", "apk", "app", "приложение"],
                "filters": {
                    "ios": {"name": "iOS", "keywords": ["ios", "iphone", "ipad", "swift", "objective-c", "xcode"]},
                    "android": {"name": "Android", "keywords": ["android", "apk", "kotlin", "java android", "android studio"]},
                    "flutter": {"name": "Flutter", "keywords": ["flutter", "dart"]},
                    "react_native": {"name": "React Native", "keywords": ["react native", "react-native"]},
                    "crossplatform": {"name": "Кроссплатформа", "keywords": ["кроссплатформ", "xamarin", "ionic"]},
                },
            },
            "40": {"name": "Игры", "keywords": ["игр", "game", "unity", "unreal", "гейм"]},
            "255": {"name": "Сервера и хостинг", "keywords": ["сервер", "хостинг", "vps", "vds", "деплой", "nginx"]},
            "81": {"name": "Юзабилити, тесты и помощь", "keywords": ["тестирован", "qa", "юзабилити", "аудит"]},
        },
    },
    "5": {
        "name": "Тексты и переводы",
        "subcategories": {
            "235": {"name": "Резюме и вакансии", "keywords": ["резюме", "cv", "ваканси", "поиск работы"]},
            "75": {"name": "Набор текста", "keywords": ["набор текст", "перепечатк", "сканирован"]},
            "74": {"name": "Продающие и бизнес-тексты", "keywords": ["продающ", "коммерческ", "рекламн", "копирайтинг"]},
            "73": {"name": "Тексты и наполнение сайта", "keywords": ["контент", "наполнени", "статья", "пост", "блог"]},
            "35": {"name": "Переводы", "keywords": ["перевод", "translate", "английск", "немецк", "французск"]},
            "303": {"name": "ИИ-тексты", "keywords": ["chatgpt", "gpt", "нейросет", "генерация текст"]},
        },
    },
    "17": {
        "name": "SEO и трафик",
        "subcategories": {
            "72": {"name": "Трафик", "keywords": ["трафик", "посетител", "клиент"]},
            "71": {"name": "Семантическое ядро", "keywords": ["семантическ", "ключев", "keywords", "ядро"]},
            "59": {"name": "Ссылки", "keywords": ["ссылк", "backlink", "донор"]},
            "56": {"name": "Статистика и аналитика", "keywords": ["аналитик", "статистик", "метрик", "google analytics"]},
            "44": {"name": "SEO аудиты, консультации", "keywords": ["seo аудит", "консультац", "анализ сайта"]},
            "43": {"name": "Внутренняя оптимизация", "keywords": ["оптимизац", "seo", "продвижен"]},
            "273": {"name": "Продвижение сайта в топ", "keywords": ["топ", "продвижен", "ранжирован"]},
        },
    },
    "45": {
        "name": "Соцсети и маркетинг",
        "subcategories": {
            "113": {"name": "Базы данных и клиентов", "keywords": ["баз", "клиент", "данных"]},
            "112": {"name": "Маркетплейсы и доски объявлений", "keywords": ["маркетплейс", "объявлен", "авито", "доска"]},
            "108": {"name": "E-mail маркетинг и рассылки", "keywords": ["email", "e-mail", "рассылк", "почт"]},
            "49": {"name": "Контекстная реклама", "keywords": ["яндекс директ", "google ads", "контекст", "реклам"]},
            "47": {"name": "Маркетинг и PR", "keywords": ["маркетинг", "pr", "пиар", "продвижен"]},
            "46": {"name": "Соцсети и SMM", "keywords": ["smm", "соцсет", "инстаграм", "вконтакте", "tiktok"]},
        },
    },
    "7": {
        "name": "Аудио, видео, съемка",
        "subcategories": {
            "106": {"name": "Редактирование аудио", "keywords": ["аудио", "звук", "монтаж аудио", "саунд"]},
            "78": {"name": "Видеосъемка и монтаж", "keywords": ["видеосъемк", "съемк", "оператор"]},
            "77": {"name": "Интро и анимация логотипа", "keywords": ["интро", "анимац", "заставк"]},
            "76": {"name": "Видеоролики", "keywords": ["видеоролик", "ролик", "видео"]},
            "23": {"name": "Музыка и песни", "keywords": ["музык", "песн", "трек", "аранжировк"]},
            "20": {"name": "Аудиозапись и озвучка", "keywords": ["озвучк", "диктор", "голос", "запис"]},
            "300": {"name": "ИИ-генерация видео", "keywords": ["sora", "генерац видео", "нейросет"]},
        },
    },
    "83": {
        "name": "Бизнес и жизнь",
        "subcategories": {
            "114": {"name": "Продажа сайтов и групп", "keywords": ["продаж", "куплю", "готовый сайт"]},
            "84": {"name": "Персональный помощник", "keywords": ["помощник", "ассистент", "личный"]},
            "64": {"name": "Бухгалтерия и налоги", "keywords": ["бухгалтер", "налог", "отчетност"]},
            "63": {"name": "Юридическая помощь", "keywords": ["юридическ", "юрист", "договор", "иск"]},
            "55": {"name": "Обучение и консалтинг", "keywords": ["обучен", "консалтинг", "курс", "тренинг"]},
            "262": {"name": "Обзвоны и продажи", "keywords": ["обзвон", "телефон", "продаж", "холодн"]},
            "265": {"name": "Подбор персонала", "keywords": ["персонал", "кадр", "hr", "рекрутинг"]},
            "65": {"name": "Стройка и ремонт", "keywords": ["стройк", "ремонт", "дизайн проект"]},
        },
    },
}

ALL_SUBCATEGORIES = {}
for parent_id, parent_data in CATEGORIES_TREE.items():
    for sub_id, sub_data in parent_data["subcategories"].items():
        ALL_SUBCATEGORIES[sub_id] = {
            "name": sub_data["name"],
            "keywords": sub_data.get("keywords", []),
            "parent": parent_id,
            "parent_name": parent_data["name"],
            "filters": sub_data.get("filters", {}),
        }


def load_subscriptions() -> dict:
    return _load_json(SUBSCRIPTIONS_FILE, {})


def save_subscriptions(data: dict):
    _save_json(SUBSCRIPTIONS_FILE, data)


def get_user_plan(chat_id: int) -> dict:
    if chat_id == ADMIN_CHAT_ID:
        return PLANS["admin"]
    
    subs = load_subscriptions()
    user_sub = subs.get(str(chat_id), {})
    
    plan_name = user_sub.get("plan", "free")
    
    if user_sub.get("trial_ends_at"):
        trial_ends = user_sub["trial_ends_at"]
        if time.time() < trial_ends:
            plan_name = "pro"
        elif plan_name == "trial":
            plan_name = "free"
    
    if user_sub.get("expires_at"):
        if time.time() > user_sub["expires_at"]:
            plan_name = "free"
    
    return PLANS.get(plan_name, PLANS["free"])


def get_user_notifications_count(chat_id: int) -> int:
    subs = load_subscriptions()
    user_sub = subs.get(str(chat_id), {})
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user_sub.get("notifications_date") != today:
        return 0
    
    return user_sub.get("notifications_count", 0)


def get_user_weekly_stats(chat_id: int) -> dict:
    """Возвращает статистику активности за неделю"""
    from collections import defaultdict
    import json
    
    history_file = HISTORY_FILE
    if not os.path.exists(history_file):
        return {"daily": {}, "total": 0, "avg": 0, "top_categories": {}, "budget_stats": {}}
    
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return {"daily": {}, "total": 0, "avg": 0, "top_categories": {}, "budget_stats": {}}
    
    user_history = data.get(str(chat_id), [])
    
    # Считаем статистику за последние 7 дней
    from datetime import datetime, timedelta
    week_ago = datetime.now() - timedelta(days=7)
    week_ago_ts = week_ago.timestamp()
    
    daily_counts = defaultdict(int)
    category_counts = defaultdict(int)
    budgets = []
    
    for item in user_history:
        timestamp = item.get("timestamp", 0)
        if timestamp < week_ago_ts:
            continue
        
        # Подсчет по дням
        day = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        daily_counts[day] += 1
        
        # Подсчет по категориям
        category = item.get("data", {}).get("category", "Другое")
        category_counts[category] += 1
        
        # Подсчет бюджетов
        price_str = item.get("data", {}).get("price", "")
        if price_str:
            try:
                price = float(price_str.replace(" ", "").replace("руб.", "").replace("₽", ""))
                budgets.append(price)
            except:
                pass
    
    total = sum(daily_counts.values())
    avg = total / 7 if total > 0 else 0
    
    # Топ 5 категорий
    top_cats = dict(sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5])
    
    # Статистика бюджетов
    budget_stats = {}
    if budgets:
        budget_stats = {
            "min": min(budgets),
            "max": max(budgets),
            "avg": sum(budgets) / len(budgets),
            "total": sum(budgets),
        }
    
    return {
        "daily": dict(daily_counts),
        "total": total,
        "avg": avg,
        "top_categories": top_cats,
        "budget_stats": budget_stats,
    }


def _create_ascii_bar(value: int, max_value: int, width: int = 10) -> str:
    """Создает ASCII прогресс-бар"""
    if max_value == 0:
        return "░" * width
    
    filled = int((value / max_value) * width)
    return "█" * filled + "░" * (width - filled)


def _send_user_dashboard(chat_id: int):
    """Отправляет визуальный дашборд статистики пользователя"""
    user_cats = get_user_categories(chat_id)
    plan = get_user_plan(chat_id)
    notifications_today = get_user_notifications_count(chat_id)
    min_budget = get_user_min_budget(chat_id)
    weekly_stats = get_user_weekly_stats(chat_id)
    
    # === Основная информация ===
    cat_count = len([c for c in user_cats if ":" not in c])
    filter_count = len([c for c in user_cats if ":" in c])
    
    # === Лимиты ===
    max_notifications = plan["notifications_per_day"]
    if max_notifications == -1:
        limit_text = "∞ Безлимит"
        limit_bar = "██████████"
    else:
        remaining = max(0, max_notifications - notifications_today)
        limit_text = f"{notifications_today}/{max_notifications}"
        limit_bar = _create_ascii_bar(notifications_today, max_notifications, 10)
    
    # === Активность за неделю ===
    from datetime import datetime, timedelta
    
    daily_text = ""
    if weekly_stats["daily"]:
        max_daily = max(weekly_stats["daily"].values()) if weekly_stats["daily"] else 1
        
        # Последние 7 дней в обратном порядке
        for i in range(6, -1, -1):
            day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            day_name = (datetime.now() - timedelta(days=i)).strftime("%a")
            day_ru = {"Mon": "Пн", "Tue": "Вт", "Wed": "Ср", "Thu": "Чт", "Fri": "Пт", "Sat": "Сб", "Sun": "Вс"}.get(day_name, day_name)
            
            count = weekly_stats["daily"].get(day, 0)
            bar = _create_ascii_bar(count, max_daily, 8)
            daily_text += f"{day_ru} {bar} {count}\n"
    
    # === Топ категории ===
    top_cats_text = ""
    if weekly_stats["top_categories"]:
        for cat, count in list(weekly_stats["top_categories"].items())[:3]:
            cat_short = cat.split(" / ")[-1] if " / " in cat else cat
            top_cats_text += f"• {cat_short}: {count}\n"
    
    # === Бюджеты ===
    budget_text = ""
    if weekly_stats["budget_stats"]:
        stats = weekly_stats["budget_stats"]
        budget_text = (
            f"💰 <b>Бюджеты за неделю:</b>\n"
            f"Min: {stats['min']:.0f}₽ | Max: {stats['max']:.0f}₽\n"
            f"Средний: {stats['avg']:.0f}₽\n\n"
        )
    
    # === Фильтр бюджета ===
    budget_filter_text = f"от {min_budget}₽" if min_budget > 0 else "Любой"
    
    # === Формируем сообщение ===
    message = (
        f"📊 <b>Ваш дашборд</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>👤 Профиль</b>\n"
        f"Тариф: {plan['emoji']} {plan['name']}\n"
        f"📂 Категорий: {cat_count} | ⚙️ Фильтров: {filter_count}\n"
        f"💰 Мин. бюджет: {budget_filter_text}\n\n"
        f"<b>📬 Сегодня</b>\n"
        f"Уведомлений: {limit_text}\n"
        f"{limit_bar}\n\n"
    )
    
    if weekly_stats["total"] > 0:
        message += (
            f"<b>📈 Активность за неделю</b>\n"
            f"Всего: {weekly_stats['total']} проектов\n"
            f"В среднем: {weekly_stats['avg']:.1f}/день\n\n"
            f"{daily_text}\n"
        )
        
        if top_cats_text:
            message += f"<b>🔥 Топ категории:</b>\n{top_cats_text}\n"
        
        if budget_text:
            message += budget_text
    else:
        message += (
            f"<b>📈 Активность</b>\n"
            f"📭 Пока нет данных за неделю\n\n"
        )
    
    # Добавляем советы
    if notifications_today == 0 and cat_count > 0:
        message += "💡 <i>Сегодня нет уведомлений. Возможно, стоит проверить категории?</i>\n"
    elif max_notifications != -1 and notifications_today >= max_notifications * 0.8:
        message += "💡 <i>Лимит почти исчерпан. Продлите подписку для безлимита!</i>\n"
    
    message += "\n💳 /subscription | 📂 /categories"
    
    buttons = [
        [{"text": "📊 Обновить", "callback_data": "refresh_stats"}],
        [{"text": "📂 Категории", "callback_data": "back_to_main"}, {"text": "💳 Подписка", "callback_data": "subscription_menu"}],
    ]
    
    send_message(chat_id, message, reply_markup={"inline_keyboard": buttons})


def increment_notifications_count(chat_id: int):
    with _lock:
        subs = load_subscriptions()
        if str(chat_id) not in subs:
            subs[str(chat_id)] = {}
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        if subs[str(chat_id)].get("notifications_date") != today:
            subs[str(chat_id)]["notifications_date"] = today
            subs[str(chat_id)]["notifications_count"] = 0
        
        subs[str(chat_id)]["notifications_count"] = subs[str(chat_id)].get("notifications_count", 0) + 1
        save_subscriptions(subs)


def can_receive_notification(chat_id: int) -> tuple:
    if chat_id == ADMIN_CHAT_ID:
        return True, "admin"
    
    plan = get_user_plan(chat_id)
    notifications_today = get_user_notifications_count(chat_id)
    
    if plan["notifications_per_day"] == -1:
        return True, "unlimited"
    
    if notifications_today >= plan["notifications_per_day"]:
        return False, f"Достигнут лимит {plan['notifications_per_day']} уведомлений/день"
    
    return True, "ok"


def start_trial(chat_id: int, days: int = 7):
    with _lock:
        subs = load_subscriptions()
        if str(chat_id) not in subs:
            subs[str(chat_id)] = {}
        
        subs[str(chat_id)]["trial_ends_at"] = time.time() + (days * 24 * 60 * 60)
        subs[str(chat_id)]["trial_started_at"] = time.time()
        save_subscriptions(subs)


def add_referral_bonus(chat_id: int, days: int = 7):
    with _lock:
        subs = load_subscriptions()
        if str(chat_id) not in subs:
            subs[str(chat_id)] = {}
        
        current_trial = subs[str(chat_id)].get("trial_ends_at", 0)
        current_plan = subs[str(chat_id)].get("plan", "free")
        
        if current_plan in ["pro", "admin"]:
            subs[str(chat_id)]["expires_at"] = subs[str(chat_id)].get("expires_at", time.time()) + (days * 24 * 60 * 60)
        elif current_trial > time.time():
            subs[str(chat_id)]["trial_ends_at"] = current_trial + (days * 24 * 60 * 60)
        else:
            subs[str(chat_id)]["trial_ends_at"] = time.time() + (days * 24 * 60 * 60)
        
        subs[str(chat_id)]["referral_bonus_at"] = time.time()
        save_subscriptions(subs)


def get_referral_link(chat_id: int) -> str:
    return f"https://t.me/kwork_projects_bot?start=ref_{chat_id}"


def count_referrals(chat_id: int) -> int:
    users = load_users()
    count = 0
    for uid, data in users.items():
        if data.get("referrer_id") == chat_id:
            count += 1
    return count


def activate_subscription(chat_id: int, plan: str, days: int):
    with _lock:
        subs = load_subscriptions()
        if str(chat_id) not in subs:
            subs[str(chat_id)] = {}
        
        subs[str(chat_id)]["plan"] = plan
        subs[str(chat_id)]["expires_at"] = time.time() + (days * 24 * 60 * 60)
        subs[str(chat_id)]["activated_at"] = time.time()
        save_subscriptions(subs)


def load_users() -> dict:
    return _load_json(USERS_FILE, {})


def save_users(users: dict):
    _save_json(USERS_FILE, users)


def load_contacts() -> dict:
    default_contacts = {
        "support_username": "@kwork_bot_support",
        "support_email": "support@kwork-bot.ru",
        "work_hours": "Пн-Пт: 09:00-18:00 МСК",
        "weekend": "Сб-Вс: выходные",
        "response_time_free": "до 24 часов",
        "response_time_basic": "до 12 часов",
        "response_time_pro": "до 4 часов",
    }
    return _load_json(CONTACTS_FILE, default_contacts)


def save_contacts(contacts: dict):
    _save_json(CONTACTS_FILE, contacts)


def load_faq_custom() -> dict:
    return _load_json(FAQ_CUSTOM_FILE, {})


def save_faq_custom(faq: dict):
    _save_json(FAQ_CUSTOM_FILE, faq)


def register_user(chat_id: int, referrer_id: int = None) -> bool:
    with _lock:
        users = load_users()
        if str(chat_id) not in users:
            users[str(chat_id)] = {
                "categories": [],
                "enabled": True,
                "registered_at": time.time(),
                "referrer_id": referrer_id,
                "referrals_count": 0,
                "onboarding_step": 1,  # Начинаем онбординг
            }
            
            if referrer_id and str(referrer_id) in users:
                users[str(referrer_id)]["referrals_count"] = users[str(referrer_id)].get("referrals_count", 0) + 1
            
            save_users(users)
            
            from analytics import track_event
            track_event("registration", chat_id)
            if referrer_id:
                track_event("referral", referrer_id)
            
            return True
        return False


def get_user_categories(chat_id: int) -> list:
    users = load_users()
    return users.get(str(chat_id), {}).get("categories", [])


def set_user_categories(chat_id: int, categories: list):
    with _lock:
        users = load_users()
        if str(chat_id) in users:
            users[str(chat_id)]["categories"] = categories
            save_users(users)


def get_onboarding_step(chat_id: int) -> int:
    """Возвращает текущий шаг онбординга (0 = завершен, 1-3 = в процессе)"""
    users = load_users()
    return users.get(str(chat_id), {}).get("onboarding_step", 0)


def set_onboarding_step(chat_id: int, step: int):
    """Устанавливает шаг онбординга"""
    with _lock:
        users = load_users()
        if str(chat_id) in users:
            users[str(chat_id)]["onboarding_step"] = step
            save_users(users)


def _send_onboarding_step_1(chat_id: int):
    """Шаг 1/3: Выбор сферы деятельности"""
    from category_stats import get_parent_category_activity, get_total_projects_24h
    
    total_24h = get_total_projects_24h()
    
    buttons = []
    for parent_id, parent_data in CATEGORIES_TREE.items():
        sub_ids = list(parent_data.get("subcategories", {}).keys())
        activity = get_parent_category_activity(parent_id, sub_ids)
        activity_text = f" 🔥{activity}" if activity > 0 else ""
        buttons.append([{
            "text": f"{parent_data['name']}{activity_text}",
            "callback_data": f"onboard_cat:{parent_id}"
        }])
    
    buttons.append([{"text": "⏭️ Пропустить", "callback_data": "onboard_skip"}])
    
    send_message(
        chat_id,
        f"👋 <b>Добро пожаловать!</b>\n\n"
        f"Давайте настроим бот за 3 шага\n\n"
        f"<b>[Шаг 1/3] 📂 Выберите вашу сферу</b>\n"
        f"Какие проекты вам интересны?\n\n"
        f"📊 Сегодня активных проектов: {total_24h}\n\n"
        f"<i>💡 Можно выбрать несколько категорий</i>",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_onboarding_step_2(chat_id: int):
    """Шаг 2/3: Настройка уведомлений"""
    buttons = [
        [{"text": "⚡ Всегда (24/7)", "callback_data": "onboard_time:always"}],
        [{"text": "🕘 Рабочее время (09:00-18:00)", "callback_data": "onboard_time:work"}],
        [{"text": "🌙 Вечер (18:00-23:00)", "callback_data": "onboard_time:evening"}],
        [{"text": "⏭️ Настроить позже", "callback_data": "onboard_time:skip"}],
    ]
    
    send_message(
        chat_id,
        f"<b>[Шаг 2/3] ⏰ Настройте уведомления</b>\n\n"
        f"Когда вам удобно получать уведомления о проектах?\n\n"
        f"<i>💡 Вы можете изменить это позже в Настройках</i>",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_onboarding_step_3(chat_id: int):
    """Шаг 3/3: Завершение"""
    user_cats = get_user_categories(chat_id)
    hours = get_user_notification_hours(chat_id)
    
    # Подсчитаем количество выбранных категорий
    cat_count = len([c for c in user_cats if ":" not in c])
    filter_count = len([c for c in user_cats if ":" in c])
    
    # Определим время уведомлений
    if hours.get("enabled"):
        time_text = f"{hours['start']:02d}:00-{hours['end']:02d}:00"
    else:
        time_text = "24/7 (всегда)"
    
    # Подсчитаем ожидаемое количество уведомлений
    from category_stats import get_activity_for_categories
    activity = get_activity_for_categories(user_cats) if user_cats else {}
    expected_daily = sum(activity.values())
    
    buttons = [
        [{"text": "✅ Начать работу", "callback_data": "onboard_finish"}],
        [{"text": "⚙️ Настроить точнее", "callback_data": "onboard_customize"}],
    ]
    
    send_message(
        chat_id,
        f"<b>[Шаг 3/3] ✅ Почти готово!</b>\n\n"
        f"<b>Ваши настройки:</b>\n"
        f"📂 Категорий: {cat_count}\n"
        f"⚙️ Фильтров: {filter_count}\n"
        f"⏰ Уведомления: {time_text}\n\n"
        f"<b>Ожидаемая активность:</b>\n"
        f"📊 ~{expected_daily} проектов в день\n\n"
        f"<i>🎯 Бот будет присылать вам уведомления о проектах в выбранных категориях</i>",
        reply_markup={"inline_keyboard": buttons},
    )


def _complete_onboarding(chat_id: int):
    """Завершает онбординг и переводит в главное меню"""
    set_onboarding_step(chat_id, 0)
    
    # Активируем PRO триал на 7 дней
    start_trial(chat_id, days=7)
    
    # Если пользователь пришел по реферальной ссылке, добавляем бонус
    users = load_users()
    referrer_id = users.get(str(chat_id), {}).get("referrer_id")
    if referrer_id:
        add_referral_bonus(referrer_id, days=7)
        send_message(
            referrer_id,
            "🎉 <b>У вас новый реферал!</b>\n\n"
            "🎁 Вы получили +7 дней подписки!\n"
            "💵 Приглашайте друзей и получайте бонусы!",
        )
    
    send_message(
        chat_id,
        f"🎉 <b>Настройка завершена!</b>\n\n"
        f"🎁 Вам активирован <b>PRO на 7 дней</b> бесплатно!\n\n"
        f"<b>Возможности PRO:</b>\n"
        f"• ∞ Безлимит уведомлений\n"
        f"• ∞ Все категории и фильтры\n"
        f"• 📜 История за 30 дней\n"
        f"• ⚡ Приоритетная доставка\n\n"
        f"После окончания триала перейдете на Free тариф.\n"
        f"💳 Продлить: /subscription",
    )
    
    _send_main_menu(chat_id)


def get_all_active_users() -> dict:
    users = load_users()
    return {k: v for k, v in users.items() if v.get("enabled", True)}


def get_user_notification_hours(chat_id: int) -> dict:
    users = load_users()
    user = users.get(str(chat_id), {})
    
    return {
        "enabled": user.get("notification_hours_enabled", False),
        "start": user.get("notification_hours_start", 9),
        "end": user.get("notification_hours_end", 21),
        "timezone": user.get("timezone", "Europe/Moscow"),
    }


def get_user_min_budget(chat_id: int) -> int:
    """Возвращает минимальный бюджет для уведомлений (0 = без ограничений)"""
    users = load_users()
    return users.get(str(chat_id), {}).get("min_budget", 0)


def set_user_min_budget(chat_id: int, min_budget: int):
    """Устанавливает минимальный бюджет для уведомлений"""
    with _lock:
        users = load_users()
        if str(chat_id) not in users:
            users[str(chat_id)] = {
                "categories": [],
                "enabled": True,
                "registered_at": time.time(),
            }
        users[str(chat_id)]["min_budget"] = min_budget
        save_users(users)


def set_user_notification_hours(chat_id: int, enabled: bool = None, start: int = None, end: int = None, timezone: str = None):
    with _lock:
        users = load_users()
        if str(chat_id) not in users:
            users[str(chat_id)] = {
                "categories": [],
                "enabled": True,
                "registered_at": time.time(),
            }
        
        if enabled is not None:
            users[str(chat_id)]["notification_hours_enabled"] = enabled
        if start is not None:
            users[str(chat_id)]["notification_hours_start"] = start
        if end is not None:
            users[str(chat_id)]["notification_hours_end"] = end
        if timezone is not None:
            users[str(chat_id)]["timezone"] = timezone
        
        save_users(users)


def is_user_in_notification_hours(chat_id: int) -> bool:
    hours = get_user_notification_hours(chat_id)
    
    if not hours.get("enabled", False):
        return True
    
    from datetime import datetime
    import pytz
    
    try:
        tz = pytz.timezone(hours.get("timezone", "Europe/Moscow"))
        now = datetime.now(tz)
        current_hour = now.hour
        
        start_hour = hours.get("start", 9)
        end_hour = hours.get("end", 21)
        
        if start_hour <= end_hour:
            return start_hour <= current_hour < end_hour
        else:
            return current_hour >= start_hour or current_hour < end_hour
    except Exception:
        return True


def get_available_timezones() -> list:
    return [
        "Europe/Moscow",
        "Europe/Kaliningrad",
        "Europe/Samara",
        "Asia/Yekaterinburg",
        "Asia/Omsk",
        "Asia/Krasnoyarsk",
        "Asia/Irkutsk",
        "Asia/Yakutsk",
        "Asia/Vladivostok",
        "Asia/Magadan",
        "Asia/Kamchatka",
    ]


def load_deferred() -> dict:
    return _load_json(DEFERRED_FILE, {})


def save_deferred(data: dict):
    _save_json(DEFERRED_FILE, data)


def add_deferred(chat_id: int, project_id: str, project: dict):
    with _lock:
        data = load_deferred()
        if str(chat_id) not in data:
            data[str(chat_id)] = {}
        data[str(chat_id)][project_id] = project
        save_deferred(data)


def remove_deferred(chat_id: int, project_id: str):
    with _lock:
        data = load_deferred()
        if str(chat_id) in data and project_id in data[str(chat_id)]:
            del data[str(chat_id)][project_id]
            save_deferred(data)


def load_sent_projects() -> dict:
    return _load_json(SENT_PROJECTS_FILE, {})


def save_sent_projects(data: dict):
    _save_json(SENT_PROJECTS_FILE, data)


def add_sent_project(project_id: str, project: dict):
    with _lock:
        data = load_sent_projects()
        data[project_id] = {
            "title": project.get("title", ""),
            "price": project.get("price", ""),
            "description": project.get("description", ""),
            "url": project.get("url", ""),
            "category": project.get("category", ""),
            "notified_users": [],
        }
        save_sent_projects(data)


def mark_user_notified(project_id: str, chat_id: int):
    with _lock:
        data = load_sent_projects()
        if project_id in data:
            if "notified_users" not in data[project_id]:
                data[project_id]["notified_users"] = []
            data[project_id]["notified_users"].append(str(chat_id))
            save_sent_projects(data)


def is_user_notified(project_id: str, chat_id: int) -> bool:
    data = load_sent_projects()
    return str(chat_id) in data.get(project_id, {}).get("notified_users", [])


def export_user_data(chat_id: int) -> dict:
    from datetime import datetime
    
    users = load_users()
    subs = load_subscriptions()
    history = load_user_history()
    favorites = load_favorites()
    
    return {
        "exported_at": datetime.now().isoformat(),
        "user": users.get(str(chat_id), {}),
        "subscriptions": subs.get(str(chat_id), {}),
        "history": history.get(str(chat_id), []),
        "favorites": favorites.get(str(chat_id), {}),
    }


def delete_user_data(chat_id: int) -> bool:
    with _lock:
        uid = str(chat_id)
        
        users = load_users()
        subs = load_subscriptions()
        history = load_user_history()
        favorites = load_favorites()
        
        users.pop(uid, None)
        subs.pop(uid, None)
        history.pop(uid, None)
        favorites.pop(uid, None)
        
        save_users(users)
        save_subscriptions(subs)
        save_user_history(history)
        save_favorites(favorites)
        
        log.info("User %d data deleted (GDPR request)", chat_id)
        return True


def load_user_history() -> dict:
    return _load_json(HISTORY_FILE, {})


def save_user_history(data: dict):
    _save_json(HISTORY_FILE, data)


def add_project_to_history(chat_id: int, project_id: str, project: dict):
    plan = get_user_plan(chat_id)
    history_days = plan.get("history_days", 0)
    
    if history_days == 0:
        return
    
    with _lock:
        history = load_user_history()
        if str(chat_id) not in history:
            history[str(chat_id)] = []
        
        cutoff_time = time.time() - (history_days * 24 * 60 * 60)
        
        history[str(chat_id)] = [
            p for p in history[str(chat_id)]
            if p.get("timestamp", 0) > cutoff_time
        ]
        
        history[str(chat_id)].append({
            "project_id": project_id,
            "timestamp": time.time(),
            "data": {
                "title": project.get("title", ""),
                "price": project.get("price", ""),
                "description": project.get("description", "")[:300],
                "url": project.get("url", ""),
                "category": project.get("category", ""),
            },
        })
        
        max_projects = 100
        if len(history[str(chat_id)]) > max_projects:
            history[str(chat_id)] = history[str(chat_id)][-max_projects:]
        
        save_user_history(history)


def get_user_history(chat_id: int, page: int = 0, search: str = "") -> list:
    plan = get_user_plan(chat_id)
    history_days = plan.get("history_days", 0)
    
    if history_days == 0:
        return []
    
    history = load_user_history()
    user_projects = history.get(str(chat_id), [])
    
    cutoff_time = time.time() - (history_days * 24 * 60 * 60)
    user_projects = [
        p for p in user_projects
        if p.get("timestamp", 0) > cutoff_time
    ]
    
    if search:
        search_lower = search.lower()
        user_projects = [
            p for p in user_projects
            if search_lower in (p.get("data", {}).get("title", "") or p.get("title", "")).lower()
            or search_lower in (p.get("data", {}).get("description", "") or p.get("description", "")).lower()
        ]
    
    user_projects.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    per_page = 10
    start = page * per_page
    end = start + per_page
    
    return user_projects[start:end]


def count_user_history(chat_id: int, search: str = "") -> int:
    plan = get_user_plan(chat_id)
    history_days = plan.get("history_days", 0)
    
    if history_days == 0:
        return 0
    
    history = load_user_history()
    user_projects = history.get(str(chat_id), [])
    
    cutoff_time = time.time() - (history_days * 24 * 60 * 60)
    user_projects = [
        p for p in user_projects
        if p.get("timestamp", 0) > cutoff_time
    ]
    
    if search:
        search_lower = search.lower()
        user_projects = [
            p for p in user_projects
            if search_lower in (p.get("data", {}).get("title", "") or p.get("title", "")).lower()
            or search_lower in (p.get("data", {}).get("description", "") or p.get("description", "")).lower()
        ]
    
    return len(user_projects)


def export_user_history(chat_id: int, format: str = "json") -> str:
    plan = get_user_plan(chat_id)
    history_days = plan.get("history_days", 0)
    
    if history_days == 0:
        return ""
    
    history = load_user_history()
    user_projects = history.get(str(chat_id), [])
    
    cutoff_time = time.time() - (history_days * 24 * 60 * 60)
    user_projects = [
        p for p in user_projects
        if p.get("timestamp", 0) > cutoff_time
    ]
    
    user_projects.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    if format == "json":
        import json
        return json.dumps(user_projects, ensure_ascii=False, indent=2)
    elif format == "csv":
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Title", "Price", "Category", "URL", "Date"])
        for p in user_projects:
            p_data = p.get("data", {})
            writer.writerow([
                p.get("project_id", ""),
                p_data.get("title") or p.get("title", ""),
                p_data.get("price") or p.get("price", ""),
                p_data.get("category") or p.get("category", ""),
                p_data.get("url") or p.get("url", ""),
                datetime.fromtimestamp(p.get("timestamp", 0)).strftime("%d.%m.%Y %H:%M"),
            ])
        return output.getvalue()
    
    return ""


def load_favorites() -> dict:
    return _load_json(FAVORITES_FILE, {})


def save_favorites(favs: dict):
    _save_json(FAVORITES_FILE, favs)


def add_to_favorites(chat_id: int, project_id: str, project: dict):
    with _lock:
        favs = load_favorites()
        if str(chat_id) not in favs:
            favs[str(chat_id)] = {}
        
        favs[str(chat_id)][project_id] = {
            "title": project.get("title", ""),
            "price": project.get("price", ""),
            "description": project.get("description", "")[:300],
            "url": project.get("url", ""),
            "category": project.get("category", ""),
            "timestamp": time.time(),
        }
        
        max_favorites = 50
        if len(favs[str(chat_id)]) > max_favorites:
            oldest = sorted(
                favs[str(chat_id)].items(),
                key=lambda x: x[1].get("timestamp", 0)
            )[0][0]
            del favs[str(chat_id)][oldest]
        
        save_favorites(favs)


def remove_from_favorites(chat_id: int, project_id: str):
    with _lock:
        favs = load_favorites()
        if str(chat_id) in favs and project_id in favs[str(chat_id)]:
            del favs[str(chat_id)][project_id]
            save_favorites(favs)


def is_in_favorites(chat_id: int, project_id: str) -> bool:
    favs = load_favorites()
    return str(chat_id) in favs and project_id in favs[str(chat_id)]


def get_user_favorites(chat_id: int, page: int = 0) -> list:
    favs = load_favorites()
    user_favs = favs.get(str(chat_id), {})
    
    projects = [
        {"project_id": pid, **pdata}
        for pid, pdata in user_favs.items()
    ]
    
    projects.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    per_page = 10
    start = page * per_page
    end = start + per_page
    
    return projects[start:end]


def count_user_favorites(chat_id: int) -> int:
    favs = load_favorites()
    return len(favs.get(str(chat_id), {}))


def load_hidden_projects() -> dict:
    return _load_json(HIDDEN_FILE, {})


def save_hidden_projects(hidden: dict):
    _save_json(HIDDEN_FILE, hidden)


def hide_project_for_user(chat_id: int, project_id: str):
    """Скрывает проект для конкретного пользователя"""
    with _lock:
        hidden = load_hidden_projects()
        if str(chat_id) not in hidden:
            hidden[str(chat_id)] = []
        
        if project_id not in hidden[str(chat_id)]:
            hidden[str(chat_id)].append(project_id)
        
        # Ограничиваем список скрытых проектов (последние 1000)
        if len(hidden[str(chat_id)]) > 1000:
            hidden[str(chat_id)] = hidden[str(chat_id)][-1000:]
        
        save_hidden_projects(hidden)


def is_project_hidden(chat_id: int, project_id: str) -> bool:
    """Проверяет, скрыт ли проект для пользователя"""
    hidden = load_hidden_projects()
    return project_id in hidden.get(str(chat_id), [])


def load_config() -> dict:
    return _load_json(CONFIG_FILE, {"interval": 900})


def save_config(cfg: dict):
    _save_json(CONFIG_FILE, cfg)


def get_interval() -> int:
    return load_config().get("interval", 900)


def set_interval(minutes: int):
    with _lock:
        cfg = load_config()
        cfg["interval"] = minutes * 60
        save_config(cfg)


def _api_post(url, data):
    from rate_limiter import TELEGRAM_LIMITER
    import time
    
    if not TELEGRAM_LIMITER.allow("telegram"):
        wait = TELEGRAM_LIMITER.wait_time("telegram")
        log.warning("Telegram rate limit hit, waiting %.1fs", wait)
        time.sleep(wait)
    
    try:
        resp = requests.post(url, data=data, timeout=30)
        if resp.status_code == 429:
            log.error("Telegram API rate limited (429)")
            return None
        if resp.status_code != 200:
            log.error("TG API error: %s %s", resp.status_code, resp.text[:200])
            return None
        return resp.json()
    except Exception as e:
        log.error("TG API post failed: %s", e)
        return None


def send_message(chat_id: int, text: str, parse_mode: str = "HTML", reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    result = _api_post(SEND_URL, data)
    return result is not None and result.get("ok", False)


def notify_admin(message: str, level: str = "info"):
    emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "🚨",
        "success": "✅",
    }
    
    text = f"{emoji.get(level, '')} {message}"
    
    try:
        send_message(ADMIN_CHAT_ID, text)
    except Exception as e:
        log.error("Failed to notify admin: %s", e)


def get_project_by_id(project_id: str) -> dict:
    data = load_sent_projects()
    return data.get(project_id, {})


def format_project_message(project: dict, plan: dict, cat_display: str = "") -> str:
    title = project.get("title", "Без названия")
    price = project.get("price", "Цена не указана")
    description = project.get("description", "")[:300]
    category = cat_display or project.get("category", "Категория")
    
    watermark = "\n\n— <i>Free тариф</i> | /subscription" if plan.get("watermark") else ""
    
    text = (
        f"💼 <b>Новый проект</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>{title}</b>\n\n"
        f"💰 {price}\n"
        f"📂 {category}\n\n"
        f"📝 {description}{watermark}"
    )
    
    return text


def send_project_to_user(chat_id: int, text: str, project_url: str, sub_id: str, project_id: str):
    plan = get_user_plan(chat_id)
    is_fav = is_in_favorites(chat_id, project_id)
    fav_text = "⭐ В избранном" if is_fav else "☆ В избранное"
    fav_cb = f"uf:{project_id}" if is_fav else f"af:{project_id}"
    
    # Строим кнопки в зависимости от тарифа
    buttons = []
    
    # Первый ряд: описание + избранное
    row1 = [{"text": "📋 Подробнее", "callback_data": f"pd:{project_id}"}]
    row1.append({"text": fav_text, "callback_data": fav_cb})
    buttons.append(row1)
    
    # Второй ряд: отложить + скрыть
    row2 = [{"text": "📌 Отложить", "callback_data": f"vl:{project_id}"}]
    row2.append({"text": "🚫 Скрыть", "callback_data": f"ni:{project_id}"})
    buttons.append(row2)
    
    # Третий ряд: открыть на Kwork
    buttons.append([{"text": "🔗 Открыть на Kwork", "url": project_url}])
    
    # Четвертый ряд: отписаться (только для Pro/Basic)
    if plan["filters_allowed"]:
        buttons.append([{"text": "📉 Отписаться от категории", "callback_data": f"uc:{sub_id}"}])
    
    reply_markup = {"inline_keyboard": buttons}
    
    result = _api_post(SEND_URL, {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": json.dumps(reply_markup),
    })
    
    if result and result.get("ok"):
        mark_user_notified(project_id, chat_id)
        return True
    return False


def _answer_callback(cb_id: str, text: str = ""):
    _api_post(ANSWER_URL, {"callback_query_id": cb_id, "text": text})


def _edit_message_reply_markup(chat_id: int, message_id: int, reply_markup=None):
    if reply_markup is None:
        reply_markup = {"inline_keyboard": []}
    _api_post(EDIT_URL, {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": json.dumps(reply_markup),
    })


def _send_subscription_menu(chat_id: int):
    plan = get_user_plan(chat_id)
    subs = load_subscriptions()
    user_sub = subs.get(str(chat_id), {})
    
    notifications_today = get_user_notifications_count(chat_id)
    notifications_limit = plan["notifications_per_day"]
    user_cats = get_user_categories(chat_id)
    categories_count = len([c for c in user_cats if ':' not in c])
    favorites_count = count_user_favorites(chat_id)
    
    trial_days_left = 0
    if user_sub.get("trial_ends_at"):
        trial_ends = user_sub["trial_ends_at"]
        if time.time() < trial_ends:
            trial_days_left = int((trial_ends - time.time()) / (24 * 60 * 60))
    
    subscription_days_left = 0
    expires_date = ""
    if user_sub.get("expires_at"):
        expires = user_sub["expires_at"]
        if time.time() < expires:
            subscription_days_left = int((expires - time.time()) / (24 * 60 * 60))
            expires_date = datetime.fromtimestamp(expires).strftime("%d.%m.%Y")
    
    total_days = 30
    if trial_days_left > 0:
        days_left = trial_days_left
        total_days = 7
        progress = int((total_days - days_left) / total_days * 100)
    elif subscription_days_left > 0:
        days_left = subscription_days_left
        progress = int((total_days - days_left) / total_days * 100)
    else:
        days_left = 0
        progress = 0
    
    progress_bars = 20
    filled = int(progress / 100 * progress_bars)
    empty = progress_bars - filled
    progress_bar = "█" * filled + "░" * empty
    
    if notifications_limit > 0:
        notif_progress = min(100, int(notifications_today / notifications_limit * 100))
        notif_filled = int(notif_progress / 100 * progress_bars)
        notif_empty = progress_bars - notif_filled
        notif_bar = "█" * notif_filled + "░" * notif_empty
        notif_text = f"{notifications_today}/{notifications_limit}"
    else:
        notif_bar = "█" * progress_bars
        notif_text = f"{notifications_today} ∞"
    
    status_line = ""
    if trial_days_left > 0:
        status_line = f"🎁 Пробный период: {trial_days_left} дн."
    elif subscription_days_left > 0:
        status_line = f"💎 Подписка активна: {subscription_days_left} дн."
    elif plan["name"] == "free":
        status_line = "🆓 Бесплатный тариф"
    
    text = (
        f"💎 <b>Ваша подписка</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>{plan['emoji']} {plan['name']}</b>\n"
        f"{status_line}\n\n"
    )
    
    if days_left > 0:
        text += (
            f"⏰ Осталось: {days_left} дней\n"
            f"[{progress_bar}] {100-progress}%\n\n"
        )
    
    text += (
        f"📊 <b>Использование сегодня:</b>\n"
        f"📬 Уведомления: {notif_text}\n"
        f"[{notif_bar}]\n\n"
        f"📂 <b>Активность:</b>\n"
        f"• Категорий: {categories_count}/{plan['max_categories'] if plan['max_categories'] > 0 else '∞'}\n"
        f"• Фильтров: {len([c for c in user_cats if ':' in c])}\n"
        f"• Избранное: {favorites_count}\n"
    )
    
    if expires_date:
        text += f"\n💳 Следующее списание: {expires_date}\n"
    
    buttons = [[{"text": f"📋 Текущий тариф: {plan['emoji']} {plan['name']}", "callback_data": "plan_info"}]]
    
    if plan["name"] == "free":
        buttons.append([{"text": "⭐ Оформить Pro (799₽/мес)", "callback_data": "buy_pro"}])
        buttons.append([{"text": "💼 Оформить Basic (299₽/мес)", "callback_data": "buy_basic"}])
    elif plan["name"] == "basic":
        buttons.append([{"text": "⭐ Улучшить до Pro", "callback_data": "upgrade_pro"}])
    
    if trial_days_left > 0 and plan["name"] == "free":
        buttons.append([{"text": "💳 Оформить подписку", "callback_data": "plan_info"}])
    
    buttons.append([{"text": "⭐ Избранное", "callback_data": "favorites_menu"}])
    buttons.append([{"text": "📊 Моя статистика", "callback_data": "my_stats"}])
    buttons.append([{"text": "⬅️ Назад", "callback_data": "back_to_main"}])
    
    send_message(
        chat_id,
        text,
        reply_markup={"inline_keyboard": buttons},
    )


def _send_plans_info(chat_id: int):
    buttons = [
        [{"text": "⭐ Pro — 799₽/мес (безлимит)", "callback_data": "buy_pro"}],
        [{"text": "💼 Basic — 299₽/мес (30/день)", "callback_data": "buy_basic"}],
        [{"text": "💡 Сравнить тарифы", "callback_data": "compare_plans"}],
        [{"text": "⬅️ Назад", "callback_data": "subscription_menu"}],
    ]
    
    send_message(
        chat_id,
        "💎 <b>Выберите тариф</b>\n\n"
        "🆓 <b>Free</b> — бесплатно\n"
        "• 5 уведомлений/день\n"
        "• До 3 категорий\n"
        "• Без фильтров\n\n"
        "💼 <b>Basic</b> — 299₽/мес\n"
        "• 30 уведомлений/день\n"
        "• До 10 категорий\n"
        "• Все фильтры\n\n"
        "⭐ <b>Pro</b> — 799₽/мес\n"
        "• Безлимит уведомлений\n"
        "• Все категории и фильтры\n"
        "• Приоритетная доставка",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_plans_comparison(chat_id: int):
    send_message(
        chat_id,
        "📊 <b>Сравнение тарифов</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "                Free | Basic | Pro\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Уведомлений      5   |  30   | ∞\n"
        "Категорий        3   |  10   | ∞\n"
        "Фильтры         ❌   |  ✅   | ✅\n"
        "Приоритет       ❌   |  ✅   | ✅\n"
        "История         3д   |  7д   | 30д\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Цена/мес        0₽  | 299₽ | 799₽\n"
        "Цена/год        —   | 2990₽| 6999₽\n\n"
        "🎁 <b>Бонусы:</b>\n"
        "• 7 дней Pro бесплатно при регистрации\n"
        "• Скидка 27% при оплате за год\n"
        "• Реферальная программа: +7 дней за друга",
        reply_markup={"inline_keyboard": [[
            {"text": "⬅️ Назад", "callback_data": "plan_info"}
        ]]},
    )
    user_cats = get_user_categories(chat_id)
    
    buttons = []
    for parent_id, parent_data in CATEGORIES_TREE.items():
        subcats = list(parent_data["subcategories"].keys())
        selected = 0
        for s in subcats:
            if s in user_cats:
                selected += 1
            for f in user_cats:
                if f.startswith(f"{s}:"):
                    selected += 0.5
        
        total = len(subcats)
        
        if selected >= total:
            marker = "✅"
        elif selected > 0:
            marker = f"☑️"
        else:
            marker = "○"
        
        buttons.append([{
            "text": f"{marker} {parent_data['name']}",
            "callback_data": f"parent:{parent_id}"
        }])
    
    total_selected = len([c for c in user_cats if ":" not in c])
    filter_selected = len([c for c in user_cats if ":" in c])
    
    buttons.append([{"text": "📊 Мой выбор", "callback_data": "show_selection"}])
    buttons.append([{"text": "💎 Подписка", "callback_data": "subscription_menu"}])
    buttons.append([{"text": "🗑 Очистить выбор", "callback_data": "clear_all"}])
    buttons.append([{"text": "❌ Закрыть", "callback_data": "close_menu"}])
    
    stats_text = ""
    if total_selected > 0:
        stats_text = f"\n\n✨ <b>Выбрано:</b> {total_selected} подкатегорий"
        if filter_selected > 0:
            stats_text += f", {filter_selected} фильтров"
    
    send_message(
        chat_id,
        "🎯 <b>Выберите категории для отслеживания</b>\n\n"
        "Нажмите на категорию, чтобы выбрать подкатегории.\n"
        "○ — не выбрано | ☑️ — частично | ✅ — полностью"
        f"{stats_text}",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_subcategories_menu(chat_id: int, parent_id: str):
    from category_stats import get_category_activity_24h
    
    if parent_id not in CATEGORIES_TREE:
        return
    
    user_cats = get_user_categories(chat_id)
    parent_data = CATEGORIES_TREE[parent_id]
    
    activity_24h = get_category_activity_24h()
    
    buttons = []
    for sub_id, sub_data in parent_data["subcategories"].items():
        has_filters = "filters" in sub_data and sub_data["filters"]
        
        selected = sub_id in user_cats
        filter_count = sum(1 for f in user_cats if f.startswith(f"{sub_id}:"))
        
        if selected:
            marker = "✅"
        elif filter_count > 0:
            marker = f"☑️{filter_count}"
        else:
            marker = "○"
        
        # Показываем активность для подкатегории
        sub_activity = activity_24h.get(sub_id, 0)
        activity_text = f" 🔥{sub_activity}" if sub_activity > 0 else ""
        
        icon = "⚙️" if has_filters else ""
        buttons.append([{
            "text": f"{marker} {sub_data['name']}{activity_text} {icon}",
            "callback_data": f"sub:{sub_id}"
        }])
    
    buttons.append([{"text": "✅ Выбрать все", "callback_data": f"selectall:{parent_id}"}])
    buttons.append([
        {"text": "⬅️ Назад", "callback_data": "back_to_main"},
        {"text": "✅ Готово", "callback_data": "save_cats"}
    ])
    
    send_message(
        chat_id,
        f"📁 <b>{parent_data['name']}</b>\n\n"
        "⚙️ — доступны фильтры для уточнения\n"
        "🔥 — проектов за 24 часа\n"
        "○ — не выбрано | ☑️ — выбраны фильтры | ✅ — выбрано полностью",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_filters_menu(chat_id: int, sub_id: str):
    if sub_id not in ALL_SUBCATEGORIES:
        return
    
    user_cats = get_user_categories(chat_id)
    sub_data = ALL_SUBCATEGORIES[sub_id]
    filters = sub_data.get("filters", {})
    
    if not filters:
        return
    
    buttons = []
    for filter_id, filter_data in filters.items():
        full_filter_id = f"{sub_id}:{filter_id}"
        marker = "✅" if full_filter_id in user_cats else "○"
        buttons.append([{
            "text": f"{marker} {filter_data['name']}",
            "callback_data": f"filter:{full_filter_id}"
        }])
    
    buttons.append([{"text": "✅ Выбрать все", "callback_data": f"selectfilters:{sub_id}"}])
    buttons.append([{"text": "📦 Вся категория без фильтров", "callback_data": f"selectwhole:{sub_id}"}])
    buttons.append([
        {"text": "⬅️ Назад", "callback_data": f"back_to_sub:{sub_data['parent']}"},
        {"text": "✅ Готово", "callback_data": "save_cats"}
    ])
    
    send_message(
        chat_id,
        f"⚙️ <b>{sub_data['parent_name']} → {sub_data['name']}</b>\n\n"
        "💡 <b>Совет:</b> Выберите конкретные фильтры для точного поиска,\n"
        "или нажмите «Вся категория» для получения всех проектов.\n\n"
        "○ — не выбрано | ✅ — выбрано",
        reply_markup={"inline_keyboard": buttons},
    )


def _show_current_selection(chat_id: int):
    user_cats = get_user_categories(chat_id)
    
    if not user_cats:
        send_message(chat_id, "📭 Вы пока ничего не выбрали.\n\nИспользуйте /categories для выбора.")
        return
    
    grouped = {}
    for cat_id in user_cats:
        if ":" in cat_id:
            parts = cat_id.split(":")
            sub_id = parts[0]
            filter_id = parts[1] if len(parts) > 1 else None
            
            if sub_id in ALL_SUBCATEGORIES:
                sub_info = ALL_SUBCATEGORIES[sub_id]
                parent_name = sub_info.get("parent_name", "")
                sub_name = sub_info.get("name", "")
                
                if parent_name not in grouped:
                    grouped[parent_name] = {}
                if sub_name not in grouped[parent_name]:
                    grouped[parent_name][sub_name] = []
                
                if filter_id and sub_info.get("filters"):
                    filter_name = sub_info["filters"].get(filter_id, {}).get("name", filter_id)
                    grouped[parent_name][sub_name].append(filter_name)
        else:
            if cat_id in ALL_SUBCATEGORIES:
                sub_info = ALL_SUBCATEGORIES[cat_id]
                parent_name = sub_info.get("parent_name", "")
                sub_name = sub_info.get("name", "")
                
                if parent_name not in grouped:
                    grouped[parent_name] = {}
                if sub_name not in grouped[parent_name]:
                    grouped[parent_name][sub_name] = []
    
    text = "📋 <b>Ваш выбор:</b>\n\n"
    for parent_name, subcats in grouped.items():
        text += f"📂 <b>{parent_name}</b>\n"
        for sub_name, filters in subcats.items():
            if filters:
                text += f"  ├─ {sub_name}\n"
                for f in filters:
                    text += f"  │   └─ 🔹 {f}\n"
            else:
                text += f"  └─ ✅ {sub_name}\n"
        text += "\n"
    
    buttons = [
        [{"text": "✏️ Изменить", "callback_data": "back_to_main"}],
        [{"text": "🗑 Очистить", "callback_data": "clear_all"}],
        [{"text": "❌ Закрыть", "callback_data": "close_menu"}],
    ]
    
    send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})


def _send_settings_menu(chat_id: int):
    users = load_users()
    user_data = users.get(str(chat_id), {})
    user_email = user_data.get("email", "")
    
    hours = get_user_notification_hours(chat_id)
    min_budget = get_user_min_budget(chat_id)
    
    current = get_interval() // 60
    buttons = []
    row = []
    for m in [15, 30, 60, 90, 120, 180]:
        label = f"{'✅ ' if m == current else ''}{m} мин"
        row.append({"text": label, "callback_data": f"iv:{m}"})
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    # Бюджет
    budget_text = f"✅ от {min_budget} ₽" if min_budget > 0 else "❌ Любой"
    buttons.append([{"text": f"💰 Мин. бюджет: {budget_text}", "callback_data": "min_budget_menu"}])
    
    buttons.append([{"text": "📧 Указать email", "callback_data": "set_email"}])
    
    hours_status = f"✅ {hours['start']:02d}:00 - {hours['end']:02d}:00" if hours["enabled"] else "❌ Выключено"
    buttons.append([{"text": f"⏰ Время уведомлений: {hours_status}", "callback_data": "notification_hours_menu"}])
    
    email_status = f"✅ {user_email}" if user_email else "❌ Не указан"
    
    tz_name = hours.get("timezone", "Europe/Moscow")
    tz_short = tz_name.split("/")[-1]
    
    send_message(
        chat_id,
        f"⚙️ <b>Настройки</b>\n\n"
        f"⏱ Период проверки: <b>{current} мин</b>\n"
        f"💰 Мин. бюджет: {budget_text}\n"
        f"📧 Email: {email_status}\n"
        f"⏰ Время уведомлений: {hours_status}\n"
        f"🌍 Часовой пояс: {tz_short}\n\n"
        f"Выберите настройки:",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_min_budget_menu(chat_id: int):
    """Меню настройки минимального бюджета"""
    min_budget = get_user_min_budget(chat_id)
    
    buttons = []
    
    # Варианты бюджета
    options = [
        (0, "❌ Без ограничений"),
        (500, "от 500 ₽"),
        (1000, "от 1 000 ₽"),
        (3000, "от 3 000 ₽"),
        (5000, "от 5 000 ₽"),
        (10000, "от 10 000 ₽"),
        (20000, "от 20 000 ₽"),
        (50000, "от 50 000 ₽"),
    ]
    
    for budget, label in options:
        marker = "✅ " if budget == min_budget else ""
        buttons.append([{
            "text": f"{marker}{label}",
            "callback_data": f"set_budget:{budget}"
        }])
    
    # Кастомный ввод
    buttons.append([{"text": "✏️ Свое значение", "callback_data": "set_budget_custom"}])
    buttons.append([{"text": "⬅️ Назад", "callback_data": "back_to_settings"}])
    
    current_text = f"{min_budget} ₽" if min_budget > 0 else "Любой"
    
    send_message(
        chat_id,
        f"💰 <b>Минимальный бюджет</b>\n\n"
        f"Текущее значение: <b>{current_text}</b>\n\n"
        f"<i>💡 Вы будете получать уведомления только о проектах с бюджетом не менее указанного</i>\n\n"
        f"<b>Важно:</b>\n"
        f"• Фильтр применяется ко всем категориям\n"
        f"• Проекты без указания бюджета проходят фильтр\n"
        f"• Можно изменить в любой момент",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_notification_hours_menu(chat_id: int):
    hours = get_user_notification_hours(chat_id)
    
    enabled_text = "✅ Включено" if hours["enabled"] else "❌ Выключено"
    status_emoji = "🟢" if hours["enabled"] else "🔴"
    
    text = (
        f"⏰ <b>Время уведомлений</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{status_emoji} Статус: {enabled_text}\n\n"
    )
    
    if hours["enabled"]:
        text += (
            f"📅 Активные часы:\n"
            f"🕐 Начало: {hours['start']:02d}:00\n"
            f"🕐 Конец: {hours['end']:02d}:00\n\n"
            f"🌍 Часовой пояс: {hours.get('timezone', 'Europe/Moscow')}\n\n"
            f"📊 Уведомления будут приходить только в указанное время."
        )
    else:
        text += "📊 Уведомления приходят круглосуточно."
    
    buttons = [
        [
            {"text": "✅ Включить" if not hours["enabled"] else "❌ Выключить", 
             "callback_data": f"toggle_hours_{0 if hours['enabled'] else 1}"},
        ],
    ]
    
    if hours["enabled"]:
        buttons.append([{"text": f"🕐 Начало: {hours['start']:02d}:00", "callback_data": "select_start_hour"}])
        buttons.append([{"text": f"🕐 Конец: {hours['end']:02d}:00", "callback_data": "select_end_hour"}])
        buttons.append([{"text": f"🌍 Часовой пояс", "callback_data": "select_timezone"}])
    
    buttons.append([{"text": "⬅️ Назад", "callback_data": "back_to_settings"}])
    
    send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})


def _send_start_hour_selection(chat_id: int):
    hours = get_user_notification_hours(chat_id)
    current_start = hours.get("start", 9)
    
    buttons = []
    row = []
    for h in range(0, 24):
        label = f"{'✅ ' if h == current_start else ''}{h:02d}:00"
        row.append({"text": label, "callback_data": f"set_start_{h}"})
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    buttons.append([{"text": "⬅️ Назад", "callback_data": "notification_hours_menu"}])
    
    send_message(
        chat_id,
        "🕐 <b>Выберите час начала</b>\n\n"
        f"Текущее время: {current_start:02d}:00\n\n"
        "Уведомления будут приходить с этого времени:",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_end_hour_selection(chat_id: int):
    hours = get_user_notification_hours(chat_id)
    current_end = hours.get("end", 21)
    
    buttons = []
    row = []
    for h in range(0, 24):
        label = f"{'✅ ' if h == current_end else ''}{h:02d}:00"
        row.append({"text": label, "callback_data": f"set_end_{h}"})
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    buttons.append([{"text": "⬅️ Назад", "callback_data": "notification_hours_menu"}])
    
    send_message(
        chat_id,
        "🕐 <b>Выберите час окончания</b>\n\n"
        f"Текущее время: {current_end:02d}:00\n\n"
        "Уведомления будут приходить до этого времени:",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_timezone_selection(chat_id: int):
    hours = get_user_notification_hours(chat_id)
    current_tz = hours.get("timezone", "Europe/Moscow")
    
    timezones = get_available_timezones()
    
    buttons = []
    for tz in timezones:
        label = f"{'✅ ' if tz == current_tz else ''}{tz.split('/')[-1]}"
        buttons.append([{"text": label, "callback_data": f"set_tz_{tz.replace('/', '_')}"}])
    
    buttons.append([{"text": "⬅️ Назад", "callback_data": "notification_hours_menu"}])
    
    send_message(
        chat_id,
        "🌍 <b>Выберите часовой пояс</b>\n\n"
        f"Текущий: {current_tz}\n\n"
        "Время уведомлений будет рассчитываться по выбранному часовому поясу:",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_deferred_list(chat_id: int):
    deferred = load_deferred().get(str(chat_id), {})
    if not deferred:
        send_message(chat_id, "📭 Нет отложенных объявлений")
        return
    
    text = "📋 <b>Отложенные объявления:</b>\n\n"
    buttons = []
    for pid, proj in list(deferred.items())[:10]:
        title = proj.get("title", "Без названия")[:50]
        url = proj.get("url", "")
        text += f"📂 {proj.get('category', '')}\n<b>{title}</b>\n\n"
        buttons.append([
            {"text": title[:30], "url": url},
            {"text": "Удалить", "callback_data": f"dd:{pid}"},
        ])
    
    send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})


def _send_faq_menu(chat_id: int):
    from faq import FAQ, FAQ_ORDER
    
    buttons = []
    
    for key in FAQ_ORDER:
        q = FAQ[key]
        buttons.append([{"text": q["question"], "callback_data": f"faq_{key}"}])
    
    custom_faq = load_faq_custom()
    if custom_faq:
        for key in sorted(custom_faq.keys(), key=lambda x: custom_faq[x].get("order", 999)):
            q = custom_faq[key]
            buttons.append([{"text": f"📌 {q['question']}", "callback_data": f"faq_custom_{key}"}])
    
    if chat_id == ADMIN_CHAT_ID:
        buttons.append([{"text": "⚙️ Управление FAQ", "callback_data": "admin_faq_menu"}])
    
    buttons.append([{"text": "🏠 Главное меню", "callback_data": "back_to_main_menu"}])
    
    send_message(
        chat_id,
        "❓ <b>Часто задаваемые вопросы</b>\n\n"
        "Выберите вопрос для получения ответа:",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_faq_answer(chat_id: int, faq_key: str, is_custom: bool = False):
    from faq import FAQ, get_support_answer
    
    if is_custom:
        custom_faq = load_faq_custom()
        if faq_key not in custom_faq:
            return
        answer = custom_faq[faq_key]["answer"]
    else:
        if faq_key not in FAQ:
            return
        
        if faq_key == "support":
            answer = get_support_answer()
        else:
            answer = FAQ[faq_key]["answer"]
    
    buttons = [
        [{"text": "← Назад к FAQ", "callback_data": "faq_menu"}],
        [{"text": "🏠 Главное меню", "callback_data": "back_to_main_menu"}],
    ]
    
    send_message(
        chat_id,
        answer,
        reply_markup={"inline_keyboard": buttons},
    )


def _send_help(chat_id: int):
    contacts = load_contacts()
    
    send_message(
        chat_id,
        "📖 <b>Инструкция по использованию</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "<b>🤖 Что делает бот?</b>\n"
        "Мониторит новые проекты на kwork.ru и отправляет уведомления о тех, что подходят под ваши критерии.\n\n"
        "<b>📋 Быстрый старт:</b>\n"
        "1. Нажмите <b>📂 Категории</b> и выберите интересующие направления\n"
        "2. При необходимости настройте фильтры\n"
        "3. Ждите уведомления о новых проектах!\n\n"
        "<b>⚡ Основные команды:</b>\n"
        "• /start — Регистрация и главное меню\n"
        "• /menu — Главное меню\n"
        "• /categories — Выбор категорий\n"
        "• /subscription — Управление подпиской\n"
        "• /referral — Реферальная программа\n"
        "• /stats — Ваша статистика\n"
        "• /history — История полученных проектов\n"
        "• /settings — Настройки\n"
        "• /stop — Отключить уведомления\n\n"
        "<b>🎁 Бонусы:</b>\n"
        "• 7 дней PRO бесплатно при регистрации\n"
        "• +7 дней за каждого приглашенного друга\n"
        "• Скидка 27% при оплате за год\n\n"
        "<b>📊 Тарифы:</b>\n"
        "• Free: 5 уведомлений/день, 3 категории, нет истории\n"
        "• Basic: 30 уведомлений/день, 10 категорий, 7 дней истории — 299₽/мес\n"
        "• Pro: Безлимит, 30 дней истории — 799₽/мес\n\n"
        "<b>⏰ Работа бота:</b>\n"
        "Бот проверяет проекты 24/7\n\n"
        f"<b>💬 Поддержка:</b>\n"
        f"• Telegram: {contacts['support_username']}\n"
        f"• Email: {contacts['support_email']}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ Бот готов к работе!",
    )


def _send_history_menu(chat_id: int, page: int = 0, search: str = ""):
    plan = get_user_plan(chat_id)
    history_days = plan.get("history_days", 0)
    
    if history_days == 0:
        send_message(
            chat_id,
            "📜 <b>История проектов</b>\n\n"
            "❌ История недоступна на Free тарифе.\n\n"
            "💼 Basic: 7 дней истории\n"
            "⭐ Pro: 30 дней истории\n\n"
            "💳 Оформите подписку: /subscription",
        )
        return
    
    projects = get_user_history(chat_id, page, search)
    total = count_user_history(chat_id, search)
    
    if not projects:
        if search:
            send_message(
                chat_id,
                f"🔍 <b>Поиск:</b> {search}\n\n"
                f"❌ Проекты не найдены.\n\n"
                "Попробуйте изменить запрос или сбросить поиск.",
                reply_markup={"inline_keyboard": [
                    [{"text": "📜 Вся история", "callback_data": "history_0"}],
                ]},
            )
        else:
            send_message(
                chat_id,
                "📜 <b>История проектов</b>\n\n"
                f"📭 История пуста за последние {history_days} дней.\n\n"
                "Проекты будут добавляться сюда по мере получения уведомлений.",
            )
        return
    
    per_page = 10
    pages = (total - 1) // per_page + 1
    
    text = f"📜 <b>История проектов</b>\n"
    if search:
        text += f"🔍 Поиск: {search}\n"
    text += f"Всего: {total} | Страница {page + 1}/{pages}\n"
    text += f"История: {history_days} дней\n\n"
    
    buttons = []
    for i, p in enumerate(projects):
        # Совместимость со старым и новым форматом
        p_data = p.get("data", {})
        title = (p_data.get("title") or p.get("title", "Без названия"))[:40]
        price = p_data.get("price") or p.get("price", "")
        url = p_data.get("url") or p.get("url", "")
        date = datetime.fromtimestamp(p.get("timestamp", 0)).strftime("%d.%m")
        
        text += f"<b>{page * 10 + i + 1}.</b> {title}\n"
        text += f"💰 {price} | 📅 {date}\n\n"
        
        buttons.append([
            {"text": f"{title[:25]}...", "url": url},
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append({"text": "←", "callback_data": f"history_{page-1}"})
    nav_buttons.append({"text": f"{page+1}/{pages}", "callback_data": "history_info"})
    if page < pages - 1:
        nav_buttons.append({"text": "→", "callback_data": f"history_{page+1}"})
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([{"text": "🔍 Поиск", "callback_data": "history_search"}])
    buttons.append([{"text": "📥 Экспорт JSON", "callback_data": "history_export_json"}])
    
    send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})


def _send_promo_menu(chat_id: int):
    if chat_id != ADMIN_CHAT_ID:
        return
    
    from promos import get_promo_stats, init_predefined_promos
    
    init_predefined_promos()
    stats = get_promo_stats()
    
    buttons = [
        [{"text": "📋 Список промокодов", "callback_data": "promo_list"}],
        [{"text": "➕ Создать промокод", "callback_data": "promo_create"}],
        [{"text": "🏠 Главное меню", "callback_data": "back_to_main_menu"}],
    ]
    
    send_message(
        chat_id,
        f"🎫 <b>Управление промокодами</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Всего: {stats['total']}\n"
        f"✅ Активных: {stats['active']}\n"
        f"👥 Использований: {stats['total_uses']}\n"
        f"💰 Скидок выдано: {stats['total_discount']}₽\n\n"
        f"━━━━━━━━━━━━━━━━━━━",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_promo_list(chat_id: int, page: int = 0):
    if chat_id != ADMIN_CHAT_ID:
        return
    
    from promos import list_promos
    
    promos = list_promos(include_expired=False)
    
    if not promos:
        send_message(chat_id, "🎫 <b>Промокоды</b>\n\n❌ Нет активных промокодов")
        return
    
    per_page = 5
    start = page * per_page
    end = start + per_page
    pages = (len(promos) - 1) // per_page + 1
    
    text = f"🎫 <b>Список промокодов</b> (страница {page + 1}/{pages})\n\n"
    
    buttons = []
    for promo in promos[start:end]:
        code = promo.get("code", "")
        uses = promo.get("current_uses", 0)
        max_uses = promo.get("max_uses", -1)
        uses_text = f"{uses}/{max_uses}" if max_uses > 0 else f"{uses}/∞"
        
        discount = ""
        if promo.get("discount_percent", 0) > 0:
            discount = f"-{promo['discount_percent']}%"
        elif promo.get("discount_amount", 0) > 0:
            discount = f"-{promo['discount_amount']}₽"
        
        expires = datetime.fromtimestamp(promo.get("expires_at", 0)).strftime("%d.%m.%Y")
        
        text += f"🎫 <b>{code}</b>\n"
        text += f"💰 {discount} | 👥 {uses_text}\n"
        text += f"📅 До {expires}\n"
        text += f"📝 {promo.get('description', '-')}\n\n"
        
        buttons.append([
            {"text": f"🗑 {code}", "callback_data": f"promo_delete_{code}"},
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append({"text": "←", "callback_data": f"promo_list_{page-1}"})
    if page < pages - 1:
        nav_buttons.append({"text": "→", "callback_data": f"promo_list_{page+1}"})
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([{"text": "← Назад", "callback_data": "admin_promos"}])
    
    send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})


def _setup_bot_commands():
    commands = [
        {"command": "start", "description": "Регистрация и главное меню"},
        {"command": "menu", "description": "Главное меню"},
        {"command": "categories", "description": "Изменить категории"},
        {"command": "subscription", "description": "Управление подпиской"},
        {"command": "referral", "description": "Реферальная программа"},
        {"command": "stats", "description": "Моя статистика"},
        {"command": "settings", "description": "Настройки"},
        {"command": "faq", "description": "Частые вопросы"},
        {"command": "help", "description": "Инструкция"},
        {"command": "deferred", "description": "Отложенные объявления"},
        {"command": "stop", "description": "Отписаться от уведомлений"},
    ]
    _api_post(SET_CMDS_URL, {"commands": json.dumps(commands)})


def _send_main_menu(chat_id: int):
    user_cats = get_user_categories(chat_id)
    plan = get_user_plan(chat_id)
    notifications_today = get_user_notifications_count(chat_id)
    notifications_limit = plan["notifications_per_day"]
    
    if notifications_limit > 0:
        notifications_text = f"📬 Уведомлений: {notifications_today}/{notifications_limit}"
        progress = int((notifications_today / notifications_limit) * 100)
        bar = "░" * (10 - progress // 10) + "▓" * (progress // 10)
    else:
        notifications_text = f"📬 Уведомлений: {notifications_today} ∞"
        bar = "▓" * 10
    
    trial_text = ""
    subs = load_subscriptions()
    user_sub = subs.get(str(chat_id), {})
    if user_sub.get("trial_ends_at") and time.time() < user_sub["trial_ends_at"]:
        days_left = int((user_sub["trial_ends_at"] - time.time()) / (24 * 60 * 60))
        trial_text = f"\n🎁 Пробный период: {days_left} дн."
    
    keyboard = {
        "keyboard": [
            [{"text": "📂 Категории"}, {"text": "💎 Подписка"}],
            [{"text": "📊 Статистика"}, {"text": "📜 История"}],
            [{"text": "⚙️ Настройки"}, {"text": "⚡ Быстрые действия"}],
            [{"text": "🎁 Пригласить друга"}, {"text": "❓ Помощь"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }
    
    send_message(
        chat_id,
        f"╔══════════════════╗\n"
        f"║    🤖 Kwork Bot    ║\n"
        f"╚══════════════════╝\n\n"
        f"👤 <b>Ваш профиль</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Тариф: {plan['emoji']} {plan['name']}{trial_text}\n"
        f"📂 Категорий: {len([c for c in user_cats if ':' not in c])}\n"
        f"⚙️ Фильтров: {len([c for c in user_cats if ':' in c])}\n\n"
        f"{notifications_text}\n"
        f"[{bar}]\n\n"
        f"━━━━━━━━━━━━━━━━━━",
        reply_markup=keyboard,
    )


def _send_main_categories_menu(chat_id: int):
    from category_stats import get_parent_category_activity, get_total_projects_24h, get_top_active_categories
    
    user_cats = get_user_categories(chat_id)
    buttons = []
    
    for parent_id, parent_data in CATEGORIES_TREE.items():
        selected = sum(1 for c in user_cats if c == parent_id or c.startswith(f"{parent_id}:"))
        sub_count = len(parent_data.get("subcategories", {}))
        icon = "✅" if selected > 0 else "○"
        count_text = f" ({selected}/{sub_count})" if selected > 0 else ""
        
        # Получаем активность для этой категории
        sub_ids = list(parent_data.get("subcategories", {}).keys())
        activity = get_parent_category_activity(parent_id, sub_ids)
        activity_text = f" 🔥{activity}" if activity > 0 else ""
        
        buttons.append([{
            "text": f"{icon} {parent_data['name']}{count_text}{activity_text}",
            "callback_data": f"parent:{parent_id}"
        }])
    
    total_24h = get_total_projects_24h()
    top_active = get_top_active_categories(3)
    
    # Формируем текст топа активных
    top_text = ""
    if top_active:
        top_names = []
        for item in top_active:
            cat_id = item["id"]
            if cat_id in ALL_SUBCATEGORIES:
                cat_name = ALL_SUBCATEGORIES[cat_id]["name"]
            else:
                # Пробуем найти в parent категориях
                for pid, pdata in CATEGORIES_TREE.items():
                    if pid == cat_id:
                        cat_name = pdata["name"]
                        break
                else:
                    cat_name = cat_id
            top_names.append(f"• {cat_name}: {item['count']}")
        
        top_text = "\n\n🔥 <b>Топ активных сегодня:</b>\n" + "\n".join(top_names)
    
    buttons.append([{"text": "📋 Показать мой выбор", "callback_data": "show_selection"}])
    buttons.append([{"text": "🗑 Очистить всё", "callback_data": "clear_all"}])
    buttons.append([{"text": "← Назад", "callback_data": "back_to_main_menu"}])
    
    send_message(
        chat_id,
        f"📂 <b>Выберите категории</b>\n\n"
        f"○ — не выбрано\n"
        f"✅ — выбрано\n"
        f"🔥 — проектов за 24 часа\n\n"
        f"📊 Всего за 24ч: {total_24h} проектов{top_text}",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_admin_menu(chat_id: int):
    if chat_id != ADMIN_CHAT_ID:
        return
    
    users = load_users()
    subs = load_subscriptions()
    
    active_users = sum(1 for u in users.values() if u.get("enabled", True))
    total_users = len(users)
    
    by_plan = {"free": 0, "basic": 0, "pro": 0, "trial": 0}
    for uid, sub in subs.items():
        plan = sub.get("plan", "free")
        if sub.get("trial_ends_at") and time.time() < sub["trial_ends_at"]:
            by_plan["trial"] += 1
        elif plan in by_plan:
            by_plan[plan] += 1
    
    by_plan["free"] = total_users - by_plan["basic"] - by_plan["pro"] - by_plan["trial"]
    
    plan_revenue = {
        "basic": by_plan["basic"] * 299,
        "pro": by_plan["pro"] * 799,
    }
    total_revenue = sum(plan_revenue.values())
    
    keyboard = {
        "keyboard": [
            [{"text": "📊 Статистика"}, {"text": "📈 Аналитика"}],
            [{"text": "👥 Пользователи"}, {"text": "📨 Рассылка"}],
            [{"text": "🎫 Промокоды"}, {"text": "🎁 Выдать подписку"}],
            [{"text": "❓ FAQ"}, {"text": "📞 Контакты"}],
            [{"text": "🔍 Проверить проекты"}, {"text": "🏠 Главное меню"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }
    
    send_message(
        chat_id,
        f"╔══════════════════════╗\n"
        f"║   🔐 Админ-панель    ║\n"
        f"╚══════════════════════╝\n\n"
        f"👥 <b>Пользователи</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Всего: {total_users} | Активных: {active_users}\n"
        f"🆓 Free: {by_plan['free']}\n"
        f"🎁 Trial: {by_plan['trial']}\n"
        f"💼 Basic: {by_plan['basic']}\n"
        f"⭐ Pro: {by_plan['pro']}\n\n"
        f"💰 <b>Доход</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💼 Basic: {plan_revenue['basic']}₽\n"
        f"⭐ Pro: {plan_revenue['pro']}₽\n"
        f"💵 <b>Итого: {total_revenue}₽</b>",
        reply_markup=keyboard,
    )


def _send_admin_faq_menu(chat_id: int):
    if chat_id != ADMIN_CHAT_ID:
        return
    
    custom_faq = load_faq_custom()
    
    buttons = []
    buttons.append([{"text": "➕ Добавить вопрос", "callback_data": "admin_faq_add"}])
    
    if custom_faq:
        for key, item in custom_faq.items():
            buttons.append([{
                "text": f"✏️ {item['question'][:30]}...",
                "callback_data": f"admin_faq_edit_{key}"
            }])
    
    buttons.append([{"text": "← Назад", "callback_data": "faq_menu"}])
    
    count = len(custom_faq)
    send_message(
        chat_id,
        f"⚙️ <b>Управление FAQ</b>\n\n"
        f"📝 Добавлено вопросов: {count}\n\n"
        "Для редактирования нажмите на вопрос:",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_admin_contacts_menu(chat_id: int):
    if chat_id != ADMIN_CHAT_ID:
        return
    
    contacts = load_contacts()
    
    buttons = [
        [{"text": "✏️ Редактировать контакты", "callback_data": "admin_contacts_edit"}],
        [{"text": "← Назад в FAQ", "callback_data": "faq_menu"}],
    ]
    
    send_message(
        chat_id,
        f"📞 <b>Контакты поддержки</b>\n\n"
        f"💬 Telegram: {contacts['support_username']}\n"
        f"📧 Email: {contacts['support_email']}\n"
        f"🕐 Время работы: {contacts['work_hours']}\n"
        f"🛑 Выходные: {contacts['weekend']}\n\n"
        f"<b>Время ответа:</b>\n"
        f"🆓 Free: {contacts['response_time_free']}\n"
        f"💼 Basic: {contacts['response_time_basic']}\n"
        f"⭐ Pro: {contacts['response_time_pro']}",
        reply_markup={"inline_keyboard": buttons},
    )


def _send_admin_faq_edit(chat_id: int, faq_key: str):
    if chat_id != ADMIN_CHAT_ID:
        return
    
    custom_faq = load_faq_custom()
    
    if faq_key not in custom_faq:
        send_message(chat_id, "❌ Вопрос не найден")
        return
    
    item = custom_faq[faq_key]
    
    buttons = [
        [{"text": "✏️ Изменить ответ", "callback_data": f"admin_faq_edit_answer_{faq_key}"}],
        [{"text": "🗑 Удалить вопрос", "callback_data": f"admin_faq_delete_{faq_key}"}],
        [{"text": "← Назад", "callback_data": "admin_faq_menu"}],
    ]
    
    send_message(
        chat_id,
        f"✏️ <b>Редактирование вопроса</b>\n\n"
        f"<b>Вопрос:</b>\n{item['question']}\n\n"
        f"<b>Ответ:</b>\n{item['answer'][:500]}{'...' if len(item['answer']) > 500 else ''}",
        reply_markup={"inline_keyboard": buttons},
    )


def _delete_faq_item(chat_id: int, faq_key: str):
    if chat_id != ADMIN_CHAT_ID:
        return
    
    custom_faq = load_faq_custom()
    
    if faq_key in custom_faq:
        del custom_faq[faq_key]
        save_faq_custom(custom_faq)
        _send_admin_faq_menu(chat_id)


def _send_admin_stats(chat_id: int):
    if chat_id != ADMIN_CHAT_ID:
        return
    
    users = load_users()
    subs = load_subscriptions()
    
    total_users = len(users)
    active_users = sum(1 for u in users.values() if u.get("enabled", True))
    inactive_users = total_users - active_users
    
    today = datetime.now().strftime("%Y-%m-%d")
    notifications_today = 0
    for sub in subs.values():
        if sub.get("notifications_date") == today:
            notifications_today += sub.get("notifications_count", 0)
    
    total_cats_selected = sum(len(u.get("categories", [])) for u in users.values())
    avg_cats = total_cats_selected / total_users if total_users > 0 else 0
    
    plan_revenue = {
        "basic": sum(1 for s in subs.values() if s.get("plan") == "basic") * 299,
        "pro": sum(1 for s in subs.values() if s.get("plan") == "pro") * 799,
    }
    total_revenue = sum(plan_revenue.values())
    
    total_referrals = sum(u.get("referrals_count", 0) for u in users.values())
    users_with_referrals = sum(1 for u in users.values() if u.get("referrals_count", 0) > 0)
    avg_referrals = total_referrals / total_users if total_users > 0 else 0
    
    send_message(
        chat_id,
        "📊 <b>Статистика бота</b>\n\n"
        f"<b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n"
        f"• Активных: {active_users}\n"
        f"• Неактивных: {inactive_users}\n\n"
        f"<b>Реферальная программа:</b>\n"
        f"• Всего рефералов: {total_referrals}\n"
        f"• Пригласивших: {users_with_referrals}\n"
        f"• Среднее рефералов: {avg_referrals:.2f}\n\n"
        f"<b>Использование:</b>\n"
        f"• Уведомлений сегодня: {notifications_today}\n"
        f"• Среднее категорий: {avg_cats:.1f}\n\n"
        f"<b>Доход:</b>\n"
        f"• Basic: {plan_revenue['basic']}₽\n"
        f"• Pro: {plan_revenue['pro']}₽\n"
        f"• <b>Всего: {total_revenue}₽</b>",
    )


def _send_analytics_menu(chat_id: int):
    if chat_id != ADMIN_CHAT_ID:
        return
    
    from analytics import generate_analytics_report
    
    report = generate_analytics_report()
    
    buttons = [
        [
            {"text": "📊 DAU/WAU/MAU", "callback_data": "analytics_activity"},
            {"text": "💰 MRR", "callback_data": "analytics_mrr"},
        ],
        [
            {"text": "📈 Конверсия", "callback_data": "analytics_conversion"},
            {"text": "📉 Churn", "callback_data": "analytics_churn"},
        ],
        [
            {"text": "💵 ARPU/LTV", "callback_data": "analytics_revenue"},
            {"text": "📊 Рост", "callback_data": "analytics_growth"},
        ],
        [
            {"text": "📅 Метрики за 30 дней", "callback_data": "analytics_daily"},
        ],
        [{"text": "🏠 Главное меню", "callback_data": "back_to_main_menu"}],
    ]
    
    send_message(chat_id, report, reply_markup={"inline_keyboard": buttons})


def _send_admin_users_list(chat_id: int, page: int = 0):
    if chat_id != ADMIN_CHAT_ID:
        return
    
    users = load_users()
    subs = load_subscriptions()
    
    user_list = []
    for uid, data in users.items():
        plan = get_user_plan(int(uid))
        sub = subs.get(uid, {})
        enabled = data.get("enabled", True)
        cats = len(data.get("categories", []))
        
        status = "✅" if enabled else "❌"
        trial = "🎁" if sub.get("trial_ends_at") and time.time() < sub["trial_ends_at"] else ""
        
        user_list.append(f"{status} {trial} {uid}: {plan['emoji']} {plan['name']} ({cats} кат.)")
    
    per_page = 20
    start = page * per_page
    end = start + per_page
    pages = (len(user_list) - 1) // per_page + 1
    
    page_users = user_list[start:end] if start < len(user_list) else []
    
    text = f"👥 <b>Пользователи</b> (страница {page + 1}/{pages})\n\n"
    text += "\n".join(page_users)
    
    buttons = []
    if page > 0:
        buttons.append({"text": "← Назад", "callback_data": f"admin_users_{page-1}"})
    if page < pages - 1:
        buttons.append({"text": "Вперед →", "callback_data": f"admin_users_{page+1}"})
    
    inline_buttons = [buttons] if buttons else []
    inline_buttons.append([{"text": "← В админ-панель", "callback_data": "admin_menu"}])
    
    send_message(chat_id, text, reply_markup={"inline_keyboard": inline_buttons})


def _handle_update(update: dict):
    msg = update.get("message")
    cb = update.get("callback_query")
    
    if cb:
        chat_id = cb.get("from", {}).get("id", 0)
        cb_data = cb.get("data", "")
        cb_id = cb["id"]
        
        # === ONBOARDING HANDLERS ===
        if cb_data.startswith("onboard_cat:"):
            # Выбор категории на шаге 1
            parent_id = cb_data[12:]
            
            # Открываем подкатегории для выбора
            _send_subcategories_menu(chat_id, parent_id)
            _answer_callback(cb_id, "📂 Выберите подкатегории")
        
        elif cb_data == "onboard_skip":
            # Пропуск шага 1 - переходим к шагу 2
            set_onboarding_step(chat_id, 2)
            _send_onboarding_step_2(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data.startswith("onboard_time:"):
            # Выбор времени уведомлений на шаге 2
            time_choice = cb_data[14:]
            
            if time_choice == "always":
                # 24/7 - отключаем ограничение по времени
                set_user_notification_hours(chat_id, enabled=False)
            elif time_choice == "work":
                # Рабочее время 09:00-18:00
                set_user_notification_hours(chat_id, enabled=True, start=9, end=18)
            elif time_choice == "evening":
                # Вечер 18:00-23:00
                set_user_notification_hours(chat_id, enabled=True, start=18, end=23)
            # skip - оставляем как есть (по умолчанию 24/7)
            
            set_onboarding_step(chat_id, 3)
            _send_onboarding_step_3(chat_id)
            _answer_callback(cb_id, "✅ Время настроено")
        
        elif cb_data == "onboard_finish":
            # Завершение онбординга
            _complete_onboarding(chat_id)
            _answer_callback(cb_id, "🎉 Добро пожаловать!")
        
        elif cb_data == "onboard_customize":
            # Точная настройка - переходим в главное меню
            set_onboarding_step(chat_id, 0)
            _send_main_menu(chat_id)
            send_message(
                chat_id,
                "⚙️ <b>Точная настройка</b>\n\n"
                "Используйте меню для детальной настройки:\n"
                "• 📂 Категории — выбор категорий и фильтров\n"
                "• ⚙️ Настройки — время уведомлений\n"
                "• 💎 Подписка — управление тарифом",
            )
            _answer_callback(cb_id)
        
        # === REGULAR CALLBACK HANDLERS ===
        elif cb_data.startswith("parent:"):
            parent_id = cb_data[7:]
            
            # Проверяем, находимся ли в онбординге
            onboard_step = get_onboarding_step(chat_id)
            if onboard_step == 1:
                # В онбординге - открываем подкатегории и остаёмся на шаге 1
                _send_subcategories_menu(chat_id, parent_id)
                send_message(
                    chat_id,
                    "💡 <i>Выберите нужные подкатегории и нажмите 'Готово'</i>",
                )
            else:
                _send_subcategories_menu(chat_id, parent_id)
            _answer_callback(cb_id)
        
        elif cb_data.startswith("sub:"):
            sub_id = cb_data[4:]
            user_cats = get_user_categories(chat_id)
            sub_data = ALL_SUBCATEGORIES.get(sub_id, {})
            
            # Если подкатегория уже выбрана - снимаем выбор
            if sub_id in user_cats:
                user_cats.remove(sub_id)
                # Также удаляем все фильтры этой подкатегории
                user_cats = [c for c in user_cats if not c.startswith(f"{sub_id}:")]
                set_user_categories(chat_id, user_cats)
                parent_id = sub_data.get("parent")
                if parent_id:
                    _send_subcategories_menu(chat_id, parent_id)
                _answer_callback(cb_id, "❌ Выбор снят")
            
            # Если есть фильтры - открываем меню фильтров
            elif sub_data.get("filters"):
                # Проверяем, выбраны ли уже какие-то фильтры
                has_filters = any(c.startswith(f"{sub_id}:") for c in user_cats)
                if has_filters:
                    # Если есть фильтры - открываем меню для корректировки
                    _send_filters_menu(chat_id, sub_id)
                    _answer_callback(cb_id, "⚙️ Настройте фильтры")
                else:
                    # Если фильтров нет - открываем меню
                    _send_filters_menu(chat_id, sub_id)
                    _answer_callback(cb_id, "⚙️ Выберите фильтры или всю категорию")
            
            # Если фильтров нет - выбираем всю подкатегорию
            else:
                user_cats.append(sub_id)
                set_user_categories(chat_id, user_cats)
                parent_id = sub_data.get("parent")
                if parent_id:
                    _send_subcategories_menu(chat_id, parent_id)
                _answer_callback(cb_id, "✅ Подкатегория выбрана")
        
        elif cb_data.startswith("filter:"):
            full_filter_id = cb_data[7:]
            user_cats = get_user_categories(chat_id)
            
            if full_filter_id in user_cats:
                user_cats.remove(full_filter_id)
            else:
                user_cats.append(full_filter_id)
            
            set_user_categories(chat_id, user_cats)
            
            parts = full_filter_id.split(":")
            if len(parts) >= 2:
                sub_id = parts[0]
                _send_filters_menu(chat_id, sub_id)
            _answer_callback(cb_id, "Фильтр обновлен")
        
        elif cb_data.startswith("selectfilters:"):
            sub_id = cb_data[14:]
            if sub_id in ALL_SUBCATEGORIES:
                user_cats = get_user_categories(chat_id)
                sub_data = ALL_SUBCATEGORIES[sub_id]
                for filter_id in sub_data.get("filters", {}).keys():
                    full_filter_id = f"{sub_id}:{filter_id}"
                    if full_filter_id not in user_cats:
                        user_cats.append(full_filter_id)
                # Удаляем выбор всей категории, если был
                if sub_id in user_cats:
                    user_cats.remove(sub_id)
                set_user_categories(chat_id, user_cats)
                _send_filters_menu(chat_id, sub_id)
                _answer_callback(cb_id, "✅ Все фильтры выбраны")
        
        elif cb_data.startswith("selectwhole:"):
            sub_id = cb_data[12:]
            if sub_id in ALL_SUBCATEGORIES:
                user_cats = get_user_categories(chat_id)
                # Удаляем все фильтры этой категории
                user_cats = [c for c in user_cats if not c.startswith(f"{sub_id}:")]
                # Добавляем выбор всей категории
                if sub_id not in user_cats:
                    user_cats.append(sub_id)
                set_user_categories(chat_id, user_cats)
                parent_id = ALL_SUBCATEGORIES[sub_id].get("parent")
                if parent_id:
                    _send_subcategories_menu(chat_id, parent_id)
                _answer_callback(cb_id, "✅ Вся категория выбрана")
        
        elif cb_data.startswith("back_to_sub:"):
            parent_id = cb_data[12:]
            _send_subcategories_menu(chat_id, parent_id)
            _answer_callback(cb_id)
        
        elif cb_data.startswith("selectall:"):
            parent_id = cb_data[10:]
            if parent_id in CATEGORIES_TREE:
                user_cats = get_user_categories(chat_id)
                for sub_id in CATEGORIES_TREE[parent_id]["subcategories"].keys():
                    if sub_id not in user_cats:
                        user_cats.append(sub_id)
                set_user_categories(chat_id, user_cats)
                _send_subcategories_menu(chat_id, parent_id)
                _answer_callback(cb_id, "Все подкатегории выбраны")
        
        elif cb_data == "back_to_main":
            _send_main_categories_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "save_cats":
            user_cats = get_user_categories(chat_id)
            if not user_cats:
                send_message(chat_id, "❌ Вы не выбрали ни одной категории")
                _answer_callback(cb_id)
                return
            
            # Проверяем, находимся ли в онбординге
            onboard_step = get_onboarding_step(chat_id)
            if onboard_step == 1:
                # Переходим к шагу 2
                set_onboarding_step(chat_id, 2)
                _send_onboarding_step_2(chat_id)
                _answer_callback(cb_id, "✅ Категории выбраны!")
            else:
                _show_current_selection(chat_id)
                _answer_callback(cb_id, "✅ Сохранено!")
        
        elif cb_data == "show_selection":
            _show_current_selection(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "clear_all":
            set_user_categories(chat_id, [])
            send_message(chat_id, "🗑 <b>Выбор очищен</b>\n\nИспользуйте /categories для нового выбора.")
            _answer_callback(cb_id, "Выбор очищен")
        
        elif cb_data == "close_menu":
            _answer_callback(cb_id, "Закрыто")
        
        elif cb_data == "refresh_stats":
            _send_user_dashboard(chat_id)
            _answer_callback(cb_id, "🔄 Обновлено")
        
        elif cb_data == "subscription_menu":
            _send_subscription_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "plan_info":
            _send_plans_info(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "compare_plans":
            _send_plans_comparison(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "buy_pro" or cb_data == "buy_basic":
            plan_name = "pro" if cb_data == "buy_pro" else "basic"
            plan = PLANS[plan_name]
            
            buttons = [
                [
                    {"text": f"💳 {plan['price']}₽/мес", "callback_data": f"pay_{plan_name}_monthly"},
                    {"text": f"🗓 {plan.get('price_yearly', plan['price']*12)}₽/год (-27%)", "callback_data": f"pay_{plan_name}_yearly"},
                ],
                [{"text": "← Назад", "callback_data": "subscription"}],
            ]
            
            send_message(
                chat_id,
                f"💳 <b>Оформление тарифа {plan['emoji']} {plan['name']}</b>\n\n"
                f"✅ {plan['notifications_per_day'] if plan['notifications_per_day'] > 0 else 'Безлимит'} уведомлений/день\n"
                f"✅ {plan['max_categories'] if plan['max_categories'] > 0 else 'Безлимит'} категорий\n"
                f"{'✅ Все фильтры' if plan['filters_allowed'] else '❌ Без фильтров'}\n"
                f"{'✅ Без водяных знаков' if not plan['watermark'] else '❌ С водяным знаком'}\n\n"
                f"Выберите период подписки:",
                reply_markup={"inline_keyboard": buttons},
            )
            _answer_callback(cb_id)
        
        elif cb_data.startswith("pay_"):
            parts = cb_data.split("_")
            if len(parts) != 3:
                _answer_callback(cb_id, "Ошибка выбора тарифа")
                return
            
            plan = parts[1]
            period = parts[2]
            plan_type = f"{plan}_{period}"
            
            from payment import create_payment, PLANS_PRICES
            
            return_url = f"https://t.me/kwork_projects_bot?start=payment_success"
            result = create_payment(chat_id, plan_type, return_url)
            
            if "error" in result:
                send_message(chat_id, f"❌ {result['error']}\n\nОбратитесь в поддержку: @your_support_bot")
            else:
                send_message(
                    chat_id,
                    f"💳 <b>Оплата тарифа {PLANS[plan]['name']}</b>\n\n"
                    f"💰 Сумма: {PLANS_PRICES[plan_type]['amount']}₽\n\n"
                    f"👇 Нажмите кнопку ниже для перехода к оплате:",
                    reply_markup={
                        "inline_keyboard": [
                            [{"text": "💳 Перейти к оплате", "url": result['confirmation_url']}],
                            [{"text": "← Назад", "callback_data": "subscription"}],
                        ]
                    },
                )
            _answer_callback(cb_id)
        
        elif cb_data == "upgrade_pro":
            send_message(
                chat_id,
                "⭐ <b>Улучшение до Pro</b>\n\n"
                "Доплата: 500₽ (разница тарифов)\n\n"
                "Для перехода на Pro напишите в поддержку\n"
                "или оплатите по ссылке:\n"
                "🔗 kwork-bot.ru/upgrade/pro",
            )
            _answer_callback(cb_id)
        
        elif cb_data == "menu_categories":
            _send_main_categories_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "menu_subscription":
            _send_subscription_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "menu_stats":
            user_cats = get_user_categories(chat_id)
            plan = get_user_plan(chat_id)
            notifications_today = get_user_notifications_count(chat_id)
            
            send_message(
                chat_id,
                f"📊 <b>Ваша статистика</b>\n\n"
                f"📊 Тариф: {plan['emoji']} {plan['name']}\n"
                f"📂 Категорий: {len([c for c in user_cats if ':' not in c])}\n"
                f"⚙️ Фильтров: {len([c for c in user_cats if ':' in c])}\n"
                f"📬 Уведомлений сегодня: {notifications_today}",
            )
            _answer_callback(cb_id)
        
        elif cb_data == "menu_settings":
            _send_settings_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "set_email":
            send_message(
                chat_id,
                "📧 <b>Укажите email</b>\n\n"
                "Введите ваш email для получения уведомлений:\n"
                "• Окончание триала\n"
                "• Окончание подписки\n"
                "• Еженедельная статистика (Pro)\n\n"
                "Для отмены отправьте /cancel",
            )
            _set_user_state(chat_id, "email")
            _answer_callback(cb_id)
        
        elif cb_data == "notification_hours_menu":
            _send_notification_hours_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "min_budget_menu":
            _send_min_budget_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data.startswith("set_budget:"):
            budget = int(cb_data.split(":")[1])
            set_user_min_budget(chat_id, budget)
            _send_min_budget_menu(chat_id)
            budget_text = f"{budget} ₽" if budget > 0 else "Любой"
            _answer_callback(cb_id, f"✅ Бюджет: {budget_text}")
        
        elif cb_data == "set_budget_custom":
            send_message(
                chat_id,
                "✏️ <b>Установка минимального бюджета</b>\n\n"
                "Введите сумму в рублях (минимум 100):\n\n"
                "Пример: <code>15000</code>\n\n"
                "Для отмены отправьте /cancel",
            )
            _set_user_state(chat_id, "set_budget_custom")
            _answer_callback(cb_id)
        
        elif cb_data.startswith("toggle_hours_"):
            enabled = int(cb_data.split("_")[2]) == 1
            set_user_notification_hours(chat_id, enabled=enabled)
            _send_notification_hours_menu(chat_id)
            status = "включены" if enabled else "выключены"
            _answer_callback(cb_id, f"⏰ Ограничения по времени {status}")
        
        elif cb_data == "select_start_hour":
            _send_start_hour_selection(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "select_end_hour":
            _send_end_hour_selection(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "select_timezone":
            _send_timezone_selection(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data.startswith("set_start_"):
            hour = int(cb_data.split("_")[2])
            set_user_notification_hours(chat_id, start=hour)
            _send_notification_hours_menu(chat_id)
            _answer_callback(cb_id, f"✅ Начало: {hour:02d}:00")
        
        elif cb_data.startswith("set_end_"):
            hour = int(cb_data.split("_")[2])
            set_user_notification_hours(chat_id, end=hour)
            _send_notification_hours_menu(chat_id)
            _answer_callback(cb_id, f"✅ Конец: {hour:02d}:00")
        
        elif cb_data.startswith("set_tz_"):
            tz = cb_data[7:].replace("_", "/")
            set_user_notification_hours(chat_id, timezone=tz)
            _send_notification_hours_menu(chat_id)
            _answer_callback(cb_id, f"✅ Часовой пояс: {tz.split('/')[-1]}")
        
        elif cb_data == "back_to_settings":
            _send_settings_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "back_to_main_menu":
            _send_main_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "faq_menu":
            _send_faq_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data.startswith("faq_custom_"):
            faq_key = cb_data[11:]
            _send_faq_answer(chat_id, faq_key, is_custom=True)
            _answer_callback(cb_id)
        
        elif cb_data.startswith("faq_"):
            faq_key = cb_data[4:]
            _send_faq_answer(chat_id, faq_key)
            _answer_callback(cb_id)
        
        elif cb_data == "admin_faq_menu":
            _send_admin_faq_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "admin_contacts_menu":
            _send_admin_contacts_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "admin_faq_add":
            send_message(
                chat_id,
                "➕ <b>Добавление вопроса FAQ</b>\n\n"
                "Формат:\n"
                "<code>ключ|вопрос</code>\n\n"
                "Пример:\n"
                "<code>delivery|Как быстро приходит уведомление?</code>\n\n"
                "Для отмены отправьте /cancel",
            )
            _set_admin_state(chat_id, "faq_add")
            _answer_callback(cb_id)
        
        elif cb_data.startswith("admin_faq_edit_"):
            faq_key = cb_data[15:]
            _send_admin_faq_edit(chat_id, faq_key)
            _answer_callback(cb_id)
        
        elif cb_data.startswith("admin_faq_delete_"):
            faq_key = cb_data[18:]
            _delete_faq_item(chat_id, faq_key)
            _answer_callback(cb_id, "✅ Вопрос удален")
        
        elif cb_data.startswith("admin_faq_edit_answer_"):
            faq_key = cb_data[22:]
            send_message(
                chat_id,
                f"✏️ <b>Редактирование ответа</b>\n\n"
                f"Введите новый ответ для вопроса.\n"
                f"Можно использовать HTML-разметку.\n\n"
                f"Для отмены отправьте /cancel",
            )
            _set_admin_state(chat_id, f"faq_edit_answer_{faq_key}")
            _answer_callback(cb_id)
        
        elif cb_data == "admin_contacts_edit":
            contacts = load_contacts()
            send_message(
                chat_id,
                "📞 <b>Редактирование контактов</b>\n\n"
                "Формат:\n"
                "<code>поле|значение</code>\n\n"
                "<b>Поля:</b>\n"
                f"• support_username (сейчас: {contacts['support_username']})\n"
                f"• support_email (сейчас: {contacts['support_email']})\n"
                f"• work_hours (сейчас: {contacts['work_hours']})\n"
                f"• weekend (сейчас: {contacts['weekend']})\n"
                f"• response_time_free (сейчас: {contacts['response_time_free']})\n"
                f"• response_time_basic (сейчас: {contacts['response_time_basic']})\n"
                f"• response_time_pro (сейчас: {contacts['response_time_pro']})\n\n"
                "Пример:\n"
                "<code>support_username|@new_support_bot</code>\n\n"
                "Для отмены отправьте /cancel",
            )
            _set_admin_state(chat_id, "contacts_edit")
            _answer_callback(cb_id)
        
        elif cb_data.startswith("history_"):
            parts = cb_data.split("_")
            if len(parts) == 2:
                page = int(parts[1])
                _send_history_menu(chat_id, page)
            _answer_callback(cb_id)
        
        elif cb_data == "history_search":
            send_message(
                chat_id,
                "🔍 <b>Поиск по истории</b>\n\n"
                "Введите ключевое слово для поиска:\n"
                "• Поиск по названию проекта\n"
                "• Поиск по описанию\n\n"
                "Для отмены отправьте /cancel",
            )
            _set_user_state(chat_id, "history_search")
            _answer_callback(cb_id)
        
        elif cb_data == "history_export_json":
            plan = get_user_plan(chat_id)
            history_days = plan.get("history_days", 0)
            
            if history_days > 0:
                json_data = export_user_history(chat_id, "json")
                if json_data:
                    send_message(
                        chat_id,
                        f"📥 <b>Экспорт истории (JSON)</b>\n\n"
                        f"Проектов: {count_user_history(chat_id)}\n"
                        f"Период: {history_days} дней\n\n"
                        f"<code>{json_data[:4000]}</code>\n\n"
                        f"{'... (обрезано)' if len(json_data) > 4000 else ''}",
                    )
                else:
                    send_message(chat_id, "❌ История пуста")
            else:
                send_message(chat_id, "❌ История недоступна на Free тарифе")
            _answer_callback(cb_id)
        
        elif cb_data == "admin_menu":
            _send_admin_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "admin_stats":
            _send_admin_stats(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "admin_users":
            _send_admin_users_list(chat_id, 0)
            _answer_callback(cb_id)
        
        elif cb_data.startswith("admin_users_"):
            page = int(cb_data.split("_")[2])
            _send_admin_users_list(chat_id, page)
            _answer_callback(cb_id)
        
        elif cb_data == "admin_check":
            _set_check_requested()
            send_message(chat_id, "🔍 Проверка проектов запущена")
            _answer_callback(cb_id, "Проверка запущена")
        
        elif cb_data == "admin_broadcast":
            send_message(
                chat_id,
                "📨 <b>Рассылка всем пользователям</b>\n\n"
                "Отправьте сообщение для рассылки.\n"
                "Для отмены отправьте /cancel",
            )
            _set_admin_state(chat_id, "broadcast")
            _answer_callback(cb_id)
        
        elif cb_data == "admin_grant":
            send_message(
                chat_id,
                "🎁 <b>Выдать подписку</b>\n\n"
                "Формат: <code>user_id plan days</code>\n"
                "Пример: <code>123456789 pro 30</code>\n\n"
                "Plan: basic, pro\n"
                "Для отмены отправьте /cancel",
            )
            _set_admin_state(chat_id, "grant")
            _answer_callback(cb_id)
        
        elif cb_data == "admin_promos" or cb_data == "promo_menu":
            _send_promo_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "promo_list":
            _send_promo_list(chat_id, 0)
            _answer_callback(cb_id)
        
        elif cb_data.startswith("promo_list_"):
            page = int(cb_data.split("_")[2])
            _send_promo_list(chat_id, page)
            _answer_callback(cb_id)
        
        elif cb_data == "promo_create":
            send_message(
                chat_id,
                "🎫 <b>Создать промокод</b>\n\n"
                "Формат: <code>code discount_percent max_uses</code>\n"
                "Пример: <code>NEWYEAR50 50 100</code>\n\n"
                "Параметры:\n"
                "• code: код промокода (латиница, цифры)\n"
                "• discount_percent: скидка в %\n"
                "• max_uses: макс. использований (-1 = безлимит)\n\n"
                "Для отмены отправьте /cancel",
            )
            _set_admin_state(chat_id, "promo_create")
            _answer_callback(cb_id)
        
        elif cb_data.startswith("promo_delete_"):
            code = cb_data.split("_")[2]
            from promos import delete_promo
            if delete_promo(code):
                send_message(chat_id, f"✅ Промокод {code} удален")
                _send_promo_list(chat_id, 0)
            else:
                send_message(chat_id, f"❌ Промокод {code} не найден")
            _answer_callback(cb_id)
        
        elif cb_data == "my_stats":
            user_cats = get_user_categories(chat_id)
            plan = get_user_plan(chat_id)
            notifications_today = get_user_notifications_count(chat_id)
            
            send_message(
                chat_id,
                f"📊 <b>Ваша статистика</b>\n\n"
                f"📊 Тариф: {plan['emoji']} {plan['name']}\n"
                f"📂 Категорий выбрано: {len([c for c in user_cats if ':' not in c])}\n"
                f"⚙️ Фильтров выбрано: {len([c for c in user_cats if ':' in c])}\n"
                f"📬 Уведомлений сегодня: {notifications_today}\n"
                f"📝 Всего получено: {len(user_cats)} проектов",
            )
            _answer_callback(cb_id)
        
        elif cb_data == "favorites_menu":
            favorites = get_user_favorites(chat_id, 0)
            total_favorites = count_user_favorites(chat_id)
            
            if not favorites:
                send_message(
                    chat_id,
                    "⭐ <b>Избранное</b>\n\n"
                    "У вас пока нет избранных проектов.\n\n"
                    "Нажмите ☆ на уведомлении о проекте, чтобы добавить его в избранное.",
                    reply_markup={"inline_keyboard": [[
                        {"text": "⬅️ Назад", "callback_data": "subscription_menu"}
                    ]]},
                )
            else:
                text = f"⭐ <b>Избранное</b> ({total_favorites})\n"
                text += "━━━━━━━━━━━━━━━━━━\n\n"
                
                for i, proj in enumerate(favorites[:10], 1):
                    title = proj.get("title", "Без названия")[:50]
                    price = proj.get("price", "Цена не указана")
                    date = datetime.fromtimestamp(proj.get("timestamp", 0)).strftime("%d.%m")
                    text += f"{i}. {title}\n"
                    text += f"   💰 {price} • 📅 {date}\n\n"
                
                if total_favorites > 10:
                    text += f"\n... и еще {total_favorites - 10} проектов"
                
                buttons = [
                    [{"text": f"📄 Страница 1", "callback_data": "favorites_0"}],
                    [{"text": "🗑 Очистить все", "callback_data": "favorites_clear"}],
                    [{"text": "⬅️ Назад", "callback_data": "subscription_menu"}],
                ]
                
                send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})
            
            _answer_callback(cb_id)
        
        elif cb_data.startswith("favorites_"):
            page = int(cb_data.split("_")[1])
            favorites = get_user_favorites(chat_id, page)
            total_favorites = count_user_favorites(chat_id)
            
            text = f"⭐ <b>Избранное</b> ({total_favorites})\n"
            text += "━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, proj in enumerate(favorites, 1):
                title = proj.get("title", "Без названия")[:50]
                price = proj.get("price", "Цена не указана")
                date = datetime.fromtimestamp(proj.get("timestamp", 0)).strftime("%d.%m")
                text += f"{i + page * 10}. {title}\n"
                text += f"   💰 {price} • 📅 {date}\n\n"
            
            pages = (total_favorites - 1) // 10 + 1
            buttons = []
            
            nav_buttons = []
            if page > 0:
                nav_buttons.append({"text": "⬅️", "callback_data": f"favorites_{page-1}"})
            nav_buttons.append({"text": f"{page+1}/{pages}", "callback_data": "favorites_page"})
            if page < pages - 1:
                nav_buttons.append({"text": "➡️", "callback_data": f"favorites_{page+1}"})
            
            if nav_buttons:
                buttons.append(nav_buttons)
            
            buttons.append([{"text": "⬅️ Назад", "callback_data": "favorites_menu"}])
            
            send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})
            _answer_callback(cb_id)
        
        elif cb_data == "favorites_clear":
            from pathlib import Path
            favs = load_favorites()
            if str(chat_id) in favs:
                del favs[str(chat_id)]
                save_favorites(favs)
                send_message(chat_id, "🗑 <b>Избранное очищено</b>")
            else:
                send_message(chat_id, "⭐ Избранное уже пусто")
            _answer_callback(cb_id)
        
        elif cb_data == "toggle_notif_on":
            users = load_users()
            if str(chat_id) in users:
                users[str(chat_id)]["enabled"] = True
                save_users(users)
                _answer_callback(cb_id, "🔔 Уведомления включены")
                send_message(chat_id, "✅ Уведомления включены")
        
        elif cb_data == "toggle_notif_off":
            users = load_users()
            if str(chat_id) in users:
                users[str(chat_id)]["enabled"] = False
                save_users(users)
                _answer_callback(cb_id, "🔔 Уведомления выключены")
                send_message(chat_id, "❌ Уведомления выключены")
        
        elif cb_data == "promo_enter":
            send_message(
                chat_id,
                "🎫 <b>Ввести промокод</b>\n\n"
                "Введите промокод для получения скидки:\n\n"
                "Формат: <code>/promo КОД</code>\n"
                "Пример: <code>/promo WELCOME20</code>\n\n"
                "Для отмены отправьте /cancel",
            )
            _set_user_state(chat_id, "promo_enter")
            _answer_callback(cb_id)
        
        elif cb_data == "referral_link":
            referral_link = get_referral_link(chat_id)
            referrals_count = count_referrals(chat_id)
            
            send_message(
                chat_id,
                f"🔗 <b>Ваша реферальная ссылка</b>\n\n"
                f"<code>{referral_link}</code>\n\n"
                f"👥 Приглашено: {referrals_count}\n"
                f"🎁 Бонус: +7 дней за каждого друга",
            )
            _answer_callback(cb_id)
        
        elif cb_data == "analytics_menu":
            _send_analytics_menu(chat_id)
            _answer_callback(cb_id)
        
        elif cb_data == "analytics_activity":
            from analytics import calculate_dau, calculate_wau, calculate_mau
            dau = calculate_dau()
            wau = calculate_wau()
            mau = calculate_mau()
            stickiness_week = (dau / wau * 100) if wau > 0 else 0
            stickiness_month = (dau / mau * 100) if mau > 0 else 0
            send_message(
                chat_id,
                f"📊 <b>Активность пользователей</b>\n\n"
                f"<b>DAU (Daily Active Users)</b>\n"
                f"Активных сегодня: {dau}\n\n"
                f"<b>WAU (Weekly Active Users)</b>\n"
                f"Активных за неделю: {wau}\n\n"
                f"<b>MAU (Monthly Active Users)</b>\n"
                f"Активных за месяц: {mau}\n\n"
                f"<b>Stickiness (липкость)</b>\n"
                f"DAU/WAU: {stickiness_week:.1f}%\n"
                f"DAU/MAU: {stickiness_month:.1f}%",
            )
            _answer_callback(cb_id)
        
        elif cb_data == "analytics_mrr":
            from analytics import calculate_mrr
            mrr = calculate_mrr()
            arr = mrr["total"] * 12
            send_message(
                chat_id,
                f"💰 <b>MRR (Monthly Recurring Revenue)</b>\n\n"
                f"<b>Текущий MRR:</b>\n"
                f"• Basic: {mrr['basic']:,}₽\n"
                f"• Pro: {mrr['pro']:,}₽\n"
                f"• <b>Итого: {mrr['total']:,}₽</b>\n\n"
                f"<b>ARR (Annual Run Rate):</b>\n"
                f"• {arr:,}₽/год",
            )
            _answer_callback(cb_id)
        
        elif cb_data == "analytics_conversion":
            from analytics import calculate_conversion_rates
            conversion = calculate_conversion_rates()
            send_message(
                chat_id,
                f"📈 <b>Воронка конверсии</b>\n\n"
                f"• Free → Paid: {conversion['free_to_paid']:.1f}%\n"
                f"• Trial → Paid: {conversion['trial_to_paid']:.1f}%\n"
                f"• Reg → Active: {conversion['registration_to_active']:.1f}%",
            )
            _answer_callback(cb_id)
        
        elif cb_data == "analytics_churn":
            from analytics import calculate_churn_rate
            churn = calculate_churn_rate()
            send_message(
                chat_id,
                f"📉 <b>Churn Rate (Отток)</b>\n\n"
                f"• Отвалилось: {churn['churned']}\n"
                f"• Churn Rate: {churn['rate']:.1f}%",
            )
            _answer_callback(cb_id)
        
        elif cb_data == "analytics_revenue":
            from analytics import calculate_arpu, calculate_ltv
            arpu = calculate_arpu()
            ltv = calculate_ltv()
            send_message(
                chat_id,
                f"💵 <b>ARPU & LTV</b>\n\n"
                f"<b>ARPU:</b>\n"
                f"• В день: {arpu['daily']:.2f}₽\n"
                f"• В месяц: {arpu['monthly']:.2f}₽\n\n"
                f"<b>LTV:</b>\n"
                f"• Basic: {ltv['basic']:,}₽\n"
                f"• Pro: {ltv['pro']:,}₽",
            )
            _answer_callback(cb_id)
        
        elif cb_data == "analytics_growth":
            from analytics import get_growth_metrics
            growth = get_growth_metrics()
            send_message(
                chat_id,
                f"📊 <b>Рост (сегодня vs вчера)</b>\n\n"
                f"• Регистрации: {growth['registrations']['growth']:+.1f}%\n"
                f"• Доход: {growth['revenue']['growth']:+.1f}%\n"
                f"• Оплаты: {growth['payments']['growth']:+.1f}%",
            )
            _answer_callback(cb_id)
        
        elif cb_data == "analytics_daily":
            from analytics import get_daily_metrics
            daily = get_daily_metrics(7)
            if not daily:
                send_message(chat_id, "📊 Нет данных за последние 7 дней")
            else:
                text = "📅 <b>Метрики за 7 дней</b>\n\n"
                text += "Дата    | Рег | Опл | Доход\n"
                text += "━━━━━━━━━━━━━━━━━━━━━━\n"
                for day in daily:
                    date = day["date"].split("-")[1] + "." + day["date"].split("-")[2]
                    reg = day.get("registrations", 0)
                    pay = day.get("payments", 0)
                    rev = day.get("revenue", 0)
                    text += f"{date} | {reg:3d} | {pay:3d} | {rev}₽\n"
                send_message(chat_id, text)
            _answer_callback(cb_id)
        
        elif cb_data == "cancel_cats":
            _answer_callback(cb_id, "Закрыто")
        
        elif cb_data.startswith("ni:"):
            pid = cb_data[3:]
            
            # Добавляем в скрытые
            hide_project_for_user(chat_id, pid)
            
            msg_id = cb.get("message", {}).get("message_id")
            if msg_id:
                _edit_message_reply_markup(chat_id, msg_id)
            _answer_callback(cb_id, "🚫 Проект скрыт")
        
        elif cb_data.startswith("vl:"):
            pid = cb_data[3:]
            sent = load_sent_projects()
            if pid in sent:
                add_deferred(chat_id, pid, sent[pid])
                msg_id = cb.get("message", {}).get("message_id")
                if msg_id:
                    _edit_message_reply_markup(chat_id, msg_id)
                _answer_callback(cb_id, "Отложено")
            else:
                _answer_callback(cb_id, "Уже обработано")
        
        elif cb_data.startswith("uc:"):
            sub_id = cb_data[3:]
            user_cats = get_user_categories(chat_id)
            
            # Удаляем саму категорию
            if sub_id in user_cats:
                user_cats.remove(sub_id)
            
            # Удаляем все фильтры этой категории
            user_cats = [c for c in user_cats if not c.startswith(f"{sub_id}:")]
            
            set_user_categories(chat_id, user_cats)
            
            sub_name = ALL_SUBCATEGORIES.get(sub_id, {}).get("name", sub_id)
            _answer_callback(cb_id, f"❌ Отписались от «{sub_name}»")
        
        elif cb_data.startswith("pd:"):
            project_id = cb_data[3:]
            project = get_project_by_id(project_id)
            
            if not project:
                _answer_callback(cb_id, "❌ Проект не найден")
                return
            
            title = project.get("title", "Без названия")
            price = project.get("price", "Цена не указана")
            description = project.get("description", "Описание недоступно")
            category = project.get("category", "Категория")
            url = project.get("url", "")
            
            # Определяем длину описания в зависимости от тарифа
            plan = get_user_plan(chat_id)
            if plan["name"] in ["Pro", "Admin"]:
                desc_display = description  # Полное описание для Pro
                tariff_note = "⭐ Pro тариф — полное описание"
            elif plan["name"] == "Basic":
                desc_display = description[:700]  # 700 символов для Basic
                tariff_note = "💼 Basic тариф — до 700 символов"
            else:
                desc_display = description[:300]  # 300 символов для Free
                tariff_note = "🆓 Free тариф — до 300 символов"
            
            if len(description) > len(desc_display):
                desc_display += "...\n\n<i>📐 Для полного описания обновите тариф</i>"
            
            full_text = (
                f"📋 <b>Подробности проекта</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"📝 <b>{title}</b>\n\n"
                f"💰 {price}\n"
                f"📂 {category}\n\n"
                f"<b>Описание:</b>\n"
                f"{desc_display}\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<i>{tariff_note}</i>\n\n"
                f"🔗 <a href=\"{url}\">Открыть на Kwork</a>"
            )
            
            # Добавляем кнопки действий
            is_fav = is_in_favorites(chat_id, project_id)
            fav_text = "⭐ В избранном" if is_fav else "☆ В избранное"
            fav_cb = f"uf:{project_id}" if is_fav else f"af:{project_id}"
            
            buttons = [
                [
                    {"text": fav_text, "callback_data": fav_cb},
                    {"text": "📌 Отложить", "callback_data": f"vl:{project_id}"},
                ],
                [
                    {"text": "🔗 Открыть на Kwork", "url": url},
                    {"text": "🚫 Скрыть", "callback_data": f"ni:{project_id}"},
                ],
            ]
            
            send_message(chat_id, full_text, reply_markup={"inline_keyboard": buttons})
            _answer_callback(cb_id, "📋 Подробности показаны")
        
        elif cb_data.startswith("af:"):
            project_id = cb_data[3:]
            project = get_project_by_id(project_id)
            
            if not project:
                _answer_callback(cb_id, "❌ Проект не найден")
                return
            
            add_to_favorites(chat_id, project_id, project)
            
            msg_id = cb.get("message", {}).get("message_id")
            if msg_id:
                plan = get_user_plan(chat_id)
                reply_markup = {
                    "inline_keyboard": [
                        [
                            {"text": "📋 Подробнее", "callback_data": f"pd:{project_id}"},
                            {"text": "⭐ В избранном", "callback_data": f"uf:{project_id}"},
                        ],
                        [
                            {"text": "📌 Отложить", "callback_data": f"vl:{project_id}"},
                            {"text": "🚫 Скрыть", "callback_data": f"ni:{project_id}"},
                        ],
                        [
                            {"text": "🔗 Открыть на Kwork", "url": project.get("url", "")},
                        ],
                    ]
                }
                
                if plan["filters_allowed"]:
                    reply_markup["inline_keyboard"].append([
                        {"text": "📉 Отписаться от категории", "callback_data": f"uc:{project.get('categories', [''])[0] if project.get('categories') else ''}"}
                    ])
                
                _edit_message_reply_markup(chat_id, msg_id, reply_markup)
            
            _answer_callback(cb_id, "⭐ Добавлено в избранное")
        
        elif cb_data.startswith("uf:"):
            project_id = cb_data[3:]
            remove_from_favorites(chat_id, project_id)
            
            msg_id = cb.get("message", {}).get("message_id")
            if msg_id:
                project = get_project_by_id(project_id)
                plan = get_user_plan(chat_id)
                reply_markup = {
                    "inline_keyboard": [
                        [
                            {"text": "📋 Подробнее", "callback_data": f"pd:{project_id}"},
                            {"text": "☆ В избранное", "callback_data": f"af:{project_id}"},
                        ],
                        [
                            {"text": "📌 Отложить", "callback_data": f"vl:{project_id}"},
                            {"text": "🚫 Скрыть", "callback_data": f"ni:{project_id}"},
                        ],
                        [
                            {"text": "🔗 Открыть на Kwork", "url": project.get("url", "") if project else ""},
                        ],
                    ]
                }
                
                if plan["filters_allowed"] and project:
                    reply_markup["inline_keyboard"].append([
                        {"text": "📉 Отписаться от категории", "callback_data": f"uc:{project.get('categories', [''])[0] if project.get('categories') else ''}"}
                    ])
                
                _edit_message_reply_markup(chat_id, msg_id, reply_markup)
            
            _answer_callback(cb_id, "❌ Удалено из избранного")
        
        elif cb_data.startswith("dd:"):
            pid = cb_data[3:]
            remove_deferred(chat_id, pid)
            _answer_callback(cb_id, "Удалено из отложенных")
            _send_deferred_list(chat_id)
        
        elif cb_data.startswith("iv:"):
            minutes = int(cb_data[3:])
            set_interval(minutes)
            _answer_callback(cb_id, f"Период: {minutes} мин")
            _send_settings_menu(chat_id)
        
        return
    
    if msg:
        chat_id = msg.get("from", {}).get("id", 0)
        text = (msg.get("text") or "").strip()
        
        admin_state = _get_admin_state(chat_id)
        if admin_state and chat_id == ADMIN_CHAT_ID:
            if text == "/cancel":
                _clear_admin_state(chat_id)
                send_message(chat_id, "❌ Действие отменено")
                return
            
            if admin_state == "broadcast":
                users = load_users()
                success = 0
                for uid in users.keys():
                    if send_message(int(uid), text):
                        success += 1
                _clear_admin_state(chat_id)
                send_message(chat_id, f"✅ Рассылка завершена\n\nОтправлено: {success}/{len(users)}")
                return
            
            if admin_state == "grant":
                try:
                    parts = text.split()
                    if len(parts) != 3:
                        send_message(chat_id, "❌ Неверный формат. Используйте: user_id plan days")
                        return
                    
                    user_id = int(parts[0])
                    plan = parts[1].lower()
                    days = int(parts[2])
                    
                    if plan not in ["basic", "pro"]:
                        send_message(chat_id, "❌ Plan должен быть: basic или pro")
                        return
                    
                    activate_subscription(user_id, plan, days)
                    send_message(user_id, f"🎁 <b>Подписка активирована!</b>\n\nТариф: {PLANS[plan]['emoji']} {PLANS[plan]['name']}\nПериод: {days} дней")
                    send_message(chat_id, f"✅ Подписка выдана пользователю {user_id}")
                    _clear_admin_state(chat_id)
                except Exception as e:
                    send_message(chat_id, f"❌ Ошибка: {e}")
                return
            
            if admin_state == "promo_create":
                try:
                    parts = text.split()
                    if len(parts) < 3:
                        send_message(chat_id, "❌ Неверный формат. Используйте: code discount_percent max_uses")
                        return
                    
                    code = parts[0].upper()
                    discount_percent = int(parts[1])
                    max_uses = int(parts[2])
                    
                    if discount_percent < 1 or discount_percent > 100:
                        send_message(chat_id, "❌ Скидка должна быть от 1 до 100%")
                        return
                    
                    from promos import create_promo
                    result = create_promo(
                        code=code,
                        discount_percent=discount_percent,
                        max_uses=max_uses,
                        description=f"Скидка {discount_percent}%"
                    )
                    
                    if "error" in result:
                        send_message(chat_id, f"❌ {result['error']}")
                    else:
                        send_message(chat_id, f"✅ Промокод создан:\n\n🎫 {code}\n💰 Скидка: {discount_percent}%\n👥 Лимит: {max_uses if max_uses > 0 else 'безлимит'}")
                        _clear_admin_state(chat_id)
                except Exception as e:
                    send_message(chat_id, f"❌ Ошибка: {e}")
                return
            
            if admin_state == "faq_add":
                try:
                    parts = text.split("|", 1)
                    if len(parts) != 2:
                        send_message(chat_id, "❌ Неверный формат. Используйте: ключ|вопрос")
                        return
                    
                    faq_key = parts[0].strip().lower().replace(" ", "_")
                    question = parts[1].strip()
                    
                    custom_faq = load_faq_custom()
                    custom_faq[faq_key] = {
                        "question": question,
                        "answer": "",
                        "order": len(custom_faq) + 1,
                    }
                    save_faq_custom(custom_faq)
                    
                    _clear_admin_state(chat_id)
                    _set_admin_state(chat_id, f"faq_edit_answer_{faq_key}")
                    send_message(
                        chat_id,
                        f"✅ Вопрос создан: <b>{question}</b>\n\n"
                        f"Теперь введите ответ (можно использовать HTML-разметку):"
                    )
                except Exception as e:
                    send_message(chat_id, f"❌ Ошибка: {e}")
                return
            
            if admin_state.startswith("faq_edit_answer_"):
                try:
                    faq_key = admin_state[16:]
                    
                    custom_faq = load_faq_custom()
                    if faq_key not in custom_faq:
                        send_message(chat_id, "❌ Вопрос не найден")
                        _clear_admin_state(chat_id)
                        return
                    
                    custom_faq[faq_key]["answer"] = text
                    save_faq_custom(custom_faq)
                    
                    _clear_admin_state(chat_id)
                    send_message(
                        chat_id,
                        f"✅ Ответ сохранен!\n\n"
                        f"<b>Вопрос:</b> {custom_faq[faq_key]['question']}\n\n"
                        f"<b>Ответ:</b>\n{text[:500]}{'...' if len(text) > 500 else ''}"
                    )
                    _send_admin_faq_menu(chat_id)
                except Exception as e:
                    send_message(chat_id, f"❌ Ошибка: {e}")
                return
            
            if admin_state == "contacts_edit":
                try:
                    parts = text.split("|", 1)
                    if len(parts) != 2:
                        send_message(chat_id, "❌ Неверный формат. Используйте: поле|значение")
                        return
                    
                    field = parts[0].strip().lower()
                    value = parts[1].strip()
                    
                    contacts = load_contacts()
                    
                    valid_fields = [
                        "support_username", "support_email", "work_hours",
                        "weekend", "response_time_free", "response_time_basic",
                        "response_time_pro"
                    ]
                    
                    if field not in valid_fields:
                        send_message(
                            chat_id,
                            f"❌ Неверное поле.\n\n"
                            f"Доступные поля:\n"
                            f"• {chr(10).join(valid_fields)}"
                        )
                        return
                    
                    contacts[field] = value
                    save_contacts(contacts)
                    
                    _clear_admin_state(chat_id)
                    send_message(
                        chat_id,
                        f"✅ Контакт обновлен!\n\n"
                        f"<b>{field}:</b> {value}"
                    )
                    _send_admin_contacts_menu(chat_id)
                except Exception as e:
                    send_message(chat_id, f"❌ Ошибка: {e}")
                return
        
        user_state = _get_user_state(chat_id)
        if user_state:
            if text == "/cancel":
                _clear_user_state(chat_id)
                send_message(chat_id, "❌ Действие отменено")
                return
            
            if user_state == "email":
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if re.match(email_pattern, text):
                    with _lock:
                        users = load_users()
                        if str(chat_id) not in users:
                            users[str(chat_id)] = {}
                        users[str(chat_id)]["email"] = text
                        save_users(users)
                    _clear_user_state(chat_id)
                    send_message(chat_id, f"✅ Email сохранен: {text}\n\nТеперь вы будете получать уведомления на этот email.")
                else:
                    send_message(chat_id, "❌ Неверный формат email. Попробуйте еще раз или /cancel для отмены.")
                return
            
            if user_state == "history_search":
                _clear_user_state(chat_id)
                _send_history_menu(chat_id, 0, text)
                return
            
            if user_state == "promo_enter":
                _clear_user_state(chat_id)
                code = text.strip()
                
                from promos import validate_promo
                
                validation = validate_promo(code, chat_id)
                
                if not validation.get("valid"):
                    send_message(chat_id, f"❌ {validation.get('error', 'Промокод недействителен')}")
                else:
                    promo = validation["promo"]
                    discount = ""
                    if promo.get("discount_percent", 0) > 0:
                        discount = f"Скидка: {promo['discount_percent']}%"
                    elif promo.get("discount_amount", 0) > 0:
                        discount = f"Скидка: {promo['discount_amount']}₽"
                    
                    send_message(
                        chat_id,
                        f"✅ <b>Промокод принят!</b>\n\n"
                        f"🎫 Код: {promo['code']}\n"
                        f"💰 {discount}\n"
                        f"📝 {promo.get('description', '-')}\n\n"
                        f"Промокод будет применен при оплате подписки.",
                    )
                return
            
            if user_state == "confirm_delete":
                _clear_user_state(chat_id)
                
                if text.strip().upper() == "DELETE":
                    if delete_user_data(chat_id):
                        send_message(
                            chat_id,
                            "✅ <b>Аккаунт удален</b>\n\n"
                            "Все ваши данные были безвозвратно удалены.\n"
                            "Спасибо, что были с нами!",
                        )
                        notify_admin(f"🗑 User {chat_id} deleted account (GDPR)", "warning")
                    else:
                        send_message(chat_id, "❌ Ошибка при удалении. Обратитесь в поддержку.")
                else:
                    send_message(chat_id, "❌ Удаление отменено. Введите DELETE для подтверждения.")
                return
            
            if user_state == "set_budget_custom":
                _clear_user_state(chat_id)
                
                try:
                    budget = int(text.strip())
                    
                    if budget < 100:
                        send_message(chat_id, "❌ Минимальная сумма: 100 ₽")
                        _send_min_budget_menu(chat_id)
                        return
                    
                    if budget > 1000000:
                        send_message(chat_id, "❌ Максимальная сумма: 1 000 000 ₽")
                        _send_min_budget_menu(chat_id)
                        return
                    
                    set_user_min_budget(chat_id, budget)
                    send_message(
                        chat_id,
                        f"✅ <b>Минимальный бюджет установлен</b>\n\n"
                        f"💰 Вы будете получать уведомления о проектах от {budget} ₽",
                    )
                    _send_min_budget_menu(chat_id)
                except ValueError:
                    send_message(chat_id, "❌ Неверный формат. Введите число, например: 5000")
                    _send_min_budget_menu(chat_id)
                return
        
        if text.startswith("/start"):
            referrer_id = None
            if " " in text:
                param = text.split(" ", 1)[1]
                if param.startswith("ref_"):
                    try:
                        referrer_id = int(param.split("_")[1])
                    except (ValueError, IndexError):
                        pass
            
            is_new = register_user(chat_id, referrer_id)
            if is_new:
                # Сохраняем referrer_id для использования в онбординге
                if referrer_id:
                    with _lock:
                        users = load_users()
                        if str(chat_id) in users:
                            users[str(chat_id)]["referrer_id"] = referrer_id
                            save_users(users)
                
                # Запускаем онбординг
                _send_onboarding_step_1(chat_id)
                
                if referrer_id:
                    add_referral_bonus(referrer_id, days=7)
                    send_message(
                        referrer_id,
                        "🎉 <b>У вас новый реферал!</b>\n\n"
                        "🎁 Вы получили +7 дней подписки!\n"
                        "💵 Приглашайте друзей и получайте бонусы!",
                    )
            else:
                # Проверяем, завершен ли онбординг
                onboard_step = get_onboarding_step(chat_id)
                if onboard_step > 0:
                    # Продолжаем онбординг с текущего шага
                    if onboard_step == 1:
                        _send_onboarding_step_1(chat_id)
                    elif onboard_step == 2:
                        _send_onboarding_step_2(chat_id)
                    elif onboard_step == 3:
                        _send_onboarding_step_3(chat_id)
                else:
                    _send_main_menu(chat_id)
        
        elif text == "/menu":
            _send_main_menu(chat_id)
        
        elif text == "/quick":
            plan = get_user_plan(chat_id)
            notifications_today = get_user_notifications_count(chat_id)
            notifications_limit = plan["notifications_per_day"]
            user_cats = get_user_categories(chat_id)
            
            notif_text = f"{notifications_today}/{notifications_limit}" if notifications_limit > 0 else f"{notifications_today} ∞"
            cats_count = len([c for c in user_cats if ':' not in c])
            filters_count = len([c for c in user_cats if ':' in c])
            
            text = (
                "⚡ <b>Быстрые действия</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 <b>Статус:</b>\n"
                f"📬 Сегодня: {notif_text} уведомлений\n"
                f"📂 {cats_count} категорий, {filters_count} фильтров\n\n"
            )
            
            buttons = [
                [
                    {"text": "🔔 Уведомления ВКЛ", "callback_data": "toggle_notif_on"},
                    {"text": "🔔 Уведомления ВЫКЛ", "callback_data": "toggle_notif_off"},
                ],
                [
                    {"text": "📂 Изменить категории", "callback_data": "menu_categories"},
                    {"text": "💎 Подписка", "callback_data": "subscription_menu"},
                ],
                [
                    {"text": "⭐ Избранное", "callback_data": "favorites_menu"},
                    {"text": "📊 Статистика", "callback_data": "my_stats"},
                ],
                [
                    {"text": "⚙️ Настройки", "callback_data": "back_to_settings"},
                    {"text": "🎫 Промокод", "callback_data": "promo_enter"},
                ],
                [
                    {"text": "🔗 Реферальная ссылка", "callback_data": "referral_link"},
                ],
            ]
            
            send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})
        
        elif text == "📂 Категории":
            _send_main_categories_menu(chat_id)
        
        elif text == "💎 Подписка":
            _send_subscription_menu(chat_id)
        
        elif text == "📊 Статистика":
            user_cats = get_user_categories(chat_id)
            plan = get_user_plan(chat_id)
            notifications_today = get_user_notifications_count(chat_id)
            
            send_message(
                chat_id,
                f"📊 <b>Ваша статистика</b>\n\n"
                f"📊 Тариф: {plan['emoji']} {plan['name']}\n"
                f"📂 Категорий: {len([c for c in user_cats if ':' not in c])}\n"
                f"⚙️ Фильтров: {len([c for c in user_cats if ':' in c])}\n"
                f"📬 Уведомлений сегодня: {notifications_today}\n\n"
                f"💳 /subscription — управление подпиской",
            )
        
        elif text == "⚡ Быстрые действия":
            plan = get_user_plan(chat_id)
            notifications_today = get_user_notifications_count(chat_id)
            notifications_limit = plan["notifications_per_day"]
            user_cats = get_user_categories(chat_id)
            
            notif_text = f"{notifications_today}/{notifications_limit}" if notifications_limit > 0 else f"{notifications_today} ∞"
            cats_count = len([c for c in user_cats if ':' not in c])
            filters_count = len([c for c in user_cats if ':' in c])
            
            text = (
                "⚡ <b>Быстрые действия</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 <b>Статус:</b>\n"
                f"📬 Сегодня: {notif_text} уведомлений\n"
                f"📂 {cats_count} категорий, {filters_count} фильтров\n\n"
            )
            
            buttons = [
                [
                    {"text": "🔔 Уведомления ВКЛ", "callback_data": "toggle_notif_on"},
                    {"text": "🔔 Уведомления ВЫКЛ", "callback_data": "toggle_notif_off"},
                ],
                [
                    {"text": "📂 Изменить категории", "callback_data": "menu_categories"},
                    {"text": "💎 Подписка", "callback_data": "subscription_menu"},
                ],
                [
                    {"text": "⭐ Избранное", "callback_data": "favorites_menu"},
                    {"text": "📊 Статистика", "callback_data": "my_stats"},
                ],
                [
                    {"text": "⚙️ Настройки", "callback_data": "back_to_settings"},
                    {"text": "🎫 Промокод", "callback_data": "promo_enter"},
                ],
                [
                    {"text": "🔗 Реферальная ссылка", "callback_data": "referral_link"},
                ],
            ]
            
            send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})
        
        elif text == "⚙️ Настройки":
            _send_settings_menu(chat_id)
        
        elif text == "/referral" or text == "🎁 Пригласить друга":
            referral_link = get_referral_link(chat_id)
            referrals_count = count_referrals(chat_id)
            
            send_message(
                chat_id,
                f"🎁 <b>Реферальная программа</b>\n\n"
                f"📲 <b>Ваша ссылка:</b>\n"
                f"<code>{referral_link}</code>\n\n"
                f"👥 Приглашено друзей: <b>{referrals_count}</b>\n\n"
                f"<b>🎁 Бонусы:</b>\n"
                f"• Вы получаете: +7 дней подписки\n"
                f"• Друг получает: +7 дней триала\n\n"
                f"<b>📤 Как пригласить:</b>\n"
                f"1. Скопируйте ссылку выше\n"
                f"2. Отправьте другу\n"
                f"3. Друг переходит и регистрируется\n"
                f"4. Вы оба получаете бонусы!\n\n"
                f"💡 Нет ограничения на количество приглашений!",
            )
        
        elif text == "/faq" or text == "❓ Помощь":
            _send_faq_menu(chat_id)
        
        elif text == "/help":
            _send_help(chat_id)
        
        elif text == "/history" or text == "📜 История":
            _send_history_menu(chat_id)
        
        elif text.startswith("/promo "):
            code = text.split(" ", 1)[1].strip()
            
            from promos import validate_promo
            
            validation = validate_promo(code, chat_id)
            
            if not validation.get("valid"):
                send_message(chat_id, f"❌ {validation.get('error', 'Промокод недействителен')}")
            else:
                promo = validation["promo"]
                discount = ""
                if promo.get("discount_percent", 0) > 0:
                    discount = f"Скидка: {promo['discount_percent']}%"
                elif promo.get("discount_amount", 0) > 0:
                    discount = f"Скидка: {promo['discount_amount']}₽"
                
                send_message(
                    chat_id,
                    f"✅ <b>Промокод принят!</b>\n\n"
                    f"🎫 Код: {promo['code']}\n"
                    f"💰 {discount}\n"
                    f"📝 {promo.get('description', '-')}\n\n"
                    f"Промокод будет применен при оплате подписки.",
                )
        
        elif text == "/categories":
            _send_main_categories_menu(chat_id)
        
        elif text == "/subscription":
            _send_subscription_menu(chat_id)
        
        elif text == "/settings":
            _send_settings_menu(chat_id)
        
        elif text == "/deferred":
            _send_deferred_list(chat_id)
        
        elif text == "/stats":
            _send_user_dashboard(chat_id)
        
        elif text == "/export_data":
            data = export_user_data(chat_id)
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            
            if len(json_str) > 4000:
                send_message(
                    chat_id,
                    f"📥 <b>Экспорт данных (GDPR)</b>\n\n"
                    f"Ваши данные слишком большие для отображения.\n"
                    f"Файл с данными будет отправлен отдельно.",
                )
            else:
                send_message(
                    chat_id,
                    f"📥 <b>Экспорт данных (GDPR)</b>\n\n"
                    f"<code>{json_str}</code>",
                )
            
            notify_admin(f"📤 User {chat_id} exported data (GDPR)", "info")
        
        elif text == "/delete_account":
            send_message(
                chat_id,
                "⚠️ <b>Удаление аккаунта</b>\n\n"
                "Это действие <b>необратимо</b>!\n\n"
                "Будут удалены:\n"
                "• Ваш профиль\n"
                "• Подписки\n"
                "• История проектов\n"
                "• Избранное\n\n"
                "Для подтверждения введите: <code>DELETE</code>\n"
                "Для отмены отправьте /cancel",
            )
            _set_user_state(chat_id, "confirm_delete")
        
        elif text == "/admin":
            if chat_id == ADMIN_CHAT_ID:
                _send_admin_menu(chat_id)
            else:
                send_message(chat_id, "⛔ У вас нет доступа к админ-панели")
        
        elif text == "📊 Статистика" and chat_id == ADMIN_CHAT_ID:
            _send_admin_stats(chat_id)
        
        elif text == "👥 Пользователи" and chat_id == ADMIN_CHAT_ID:
            _send_admin_users_list(chat_id, 0)
        
        elif text == "📨 Рассылка" and chat_id == ADMIN_CHAT_ID:
            send_message(
                chat_id,
                "📨 <b>Рассылка всем пользователям</b>\n\n"
                "Отправьте сообщение для рассылки.\n"
                "Для отмены отправьте /cancel",
            )
            _set_admin_state(chat_id, "broadcast")
        
        elif text == "🎁 Выдать подписку" and chat_id == ADMIN_CHAT_ID:
            send_message(
                chat_id,
                "🎁 <b>Выдать подписку</b>\n\n"
                "Формат: <code>user_id plan days</code>\n"
                "Пример: <code>123456789 pro 30</code>\n\n"
                "Plan: basic, pro\n"
                "Для отмены отправьте /cancel",
            )
            _set_admin_state(chat_id, "grant")
        
        elif text == "🎫 Промокоды" and chat_id == ADMIN_CHAT_ID:
            _send_promo_menu(chat_id)
        
        elif text == "📈 Аналитика" and chat_id == ADMIN_CHAT_ID:
            _send_analytics_menu(chat_id)
        
        elif text == "❓ FAQ" and chat_id == ADMIN_CHAT_ID:
            _send_admin_faq_menu(chat_id)
        
        elif text == "📞 Контакты" and chat_id == ADMIN_CHAT_ID:
            _send_admin_contacts_menu(chat_id)
        
        elif text == "🔍 Проверить проекты" and chat_id == ADMIN_CHAT_ID:
            _check_requested.set()
            send_message(chat_id, "🔍 Проверка проектов запущена")
        
        elif text == "🏠 Главное меню":
            _send_main_menu(chat_id)
        
        elif text == "/stop":
            with _lock:
                users = load_users()
                if str(chat_id) in users:
                    users[str(chat_id)]["enabled"] = False
                    save_users(users)
            send_message(
                chat_id,
                "⏸ <b>Уведомления приостановлены</b>\n\n"
                "Используйте /start чтобы снова получать уведомления о новых проектах.",
            )
        
        elif text == "/check":
            send_message(chat_id, "🔍 Запускаю проверку...")
            _check_requested.set()


def _poll_updates():
    global _update_offset
    GET_UPDATES_URL = f"{BASE_URL}/getUpdates"
    
    while True:
        try:
            resp = requests.get(GET_UPDATES_URL, params={
                "offset": _update_offset + 1,
                "timeout": 30,
            }, timeout=40)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    for update in result.get("result", []):
                        _update_offset = update.get("update_id", _update_offset)
                        try:
                            _handle_update(update)
                        except Exception as e:
                            log.error("Error handling update: %s", e)
        except Exception as e:
            log.error("Poll error: %s", e)
        time.sleep(3)


def start_bot():
    log.info("Admin ID: %s", ADMIN_CHAT_ID)
    _setup_bot_commands()
    t = threading.Thread(target=_poll_updates, daemon=True)
    t.start()
    log.info("Bot started (multi-user mode)")
