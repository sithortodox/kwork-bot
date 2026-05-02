import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "data"
CATEGORY_STATS_FILE = DATA_DIR / "category_stats.json"
_lock = threading.Lock()


def load_category_stats() -> dict:
    if CATEGORY_STATS_FILE.exists():
        with open(CATEGORY_STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"hourly": {}, "last_cleanup": time.time()}


def save_category_stats(stats: dict):
    with open(CATEGORY_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def record_category_activity(categories: list, timestamp: float = None):
    """
    Записывает активность для списка категорий.
    
    Args:
        categories: Список ID категорий (например, ["15", "15:101", "11"])
        timestamp: Unix timestamp (если None, используется текущее время)
    """
    if timestamp is None:
        timestamp = time.time()
    
    with _lock:
        stats = load_category_stats()
        
        # Группируем по часам (YYYY-MM-DD-HH)
        hour_key = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d-%H")
        
        if "hourly" not in stats:
            stats["hourly"] = {}
        
        if hour_key not in stats["hourly"]:
            stats["hourly"][hour_key] = {}
        
        # Увеличиваем счётчик для каждой категории
        for cat_id in categories:
            # Для подкатегорий с фильтрами (15:101) считаем только основную категорию
            base_cat = cat_id.split(":")[0] if ":" in cat_id else cat_id
            
            if base_cat not in stats["hourly"][hour_key]:
                stats["hourly"][hour_key][base_cat] = 0
            stats["hourly"][hour_key][base_cat] += 1
        
        # Очищаем старые данные (> 24 часов)
        stats = _cleanup_old_stats(stats)
        
        save_category_stats(stats)


def _cleanup_old_stats(stats: dict, keep_hours: int = 24) -> dict:
    """Удаляет записи старше keep_hours часов."""
    now = time.time()
    
    # Проверяем, нужна ли очистка (каждый час)
    last_cleanup = stats.get("last_cleanup", 0)
    if now - last_cleanup < 3600:
        return stats
    
    stats["last_cleanup"] = now
    
    cutoff_time = datetime.now() - timedelta(hours=keep_hours)
    cutoff_hour = cutoff_time.strftime("%Y-%m-%d-%H")
    
    if "hourly" in stats:
        # Удаляем старые часы
        hours_to_remove = [
            h for h in stats["hourly"].keys() 
            if h < cutoff_hour
        ]
        for h in hours_to_remove:
            del stats["hourly"][h]
    
    return stats


def get_category_activity_24h() -> dict:
    """
    Возвращает активность категорий за последние 24 часа.
    
    Returns:
        dict: {category_id: count} - количество проектов за 24ч
    """
    with _lock:
        stats = load_category_stats()
        
        now = time.time()
        cutoff_time = datetime.now() - timedelta(hours=24)
        cutoff_hour = cutoff_time.strftime("%Y-%m-%d-%H")
        
        activity = defaultdict(int)
        
        if "hourly" in stats:
            for hour_key, cats in stats["hourly"].items():
                if hour_key >= cutoff_hour:
                    for cat_id, count in cats.items():
                        activity[cat_id] += count
        
        return dict(activity)


def get_top_active_categories(limit: int = 10) -> list:
    """
    Возвращает топ самых активных категорий за 24 часа.
    
    Args:
        limit: Количество категорий в топе
    
    Returns:
        list: [{"id": cat_id, "count": count}, ...]
    """
    activity = get_category_activity_24h()
    
    # Сортируем по количеству
    sorted_cats = sorted(
        activity.items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:limit]
    
    return [
        {"id": cat_id, "count": count}
        for cat_id, count in sorted_cats
    ]


def get_activity_for_categories(category_ids: list) -> dict:
    """
    Возвращает активность для указанных категорий.
    
    Args:
        category_ids: Список ID категорий
    
    Returns:
        dict: {category_id: count}
    """
    activity_24h = get_category_activity_24h()
    
    result = {}
    for cat_id in category_ids:
        # Для фильтров берём активность основной категории
        base_cat = cat_id.split(":")[0] if ":" in cat_id else cat_id
        result[cat_id] = activity_24h.get(base_cat, 0)
    
    return result


def get_total_projects_24h() -> int:
    """Возвращает общее количество проектов за 24 часа."""
    activity = get_category_activity_24h()
    return sum(activity.values())


def get_parent_category_activity(parent_id: str, subcategory_ids: list) -> int:
    """
    Возвращает активность для parent-категории (сумма активностей всех подкатегорий).
    
    Args:
        parent_id: ID основной категории (например, "15")
        subcategory_ids: Список ID подкатегорий
    
    Returns:
        int: Общее количество проектов за 24ч
    """
    activity_24h = get_category_activity_24h()
    total = 0
    
    for sub_id in subcategory_ids:
        total += activity_24h.get(sub_id, 0)
    
    return total


if __name__ == "__main__":
    # Тестирование
    test_categories = ["15", "11", "15:101"]
    record_category_activity(test_categories)
    
    print("Activity 24h:", get_category_activity_24h())
    print("Top 10:", get_top_active_categories(10))
    print("Total 24h:", get_total_projects_24h())
