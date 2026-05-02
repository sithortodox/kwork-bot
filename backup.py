import os
import shutil
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
BACKUP_DIR = Path(__file__).parent / "backups"


def backup_data():
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        backup_path = BACKUP_DIR / timestamp
        backup_path.mkdir(parents=True, exist_ok=True)
        
        files_to_backup = [
            "users.json",
            "subscriptions.json",
            "user_history.json",
            "favorites.json",
            "promos.json",
            "metrics.json",
            "sent_projects.json",
            "config.json",
        ]
        
        backed_up = 0
        for filename in files_to_backup:
            src = DATA_DIR / filename
            if src.exists():
                dst = backup_path / filename
                shutil.copy2(src, dst)
                backed_up += 1
        
        log.info("Backup completed: %s (%d files)", backup_path, backed_up)
        
        cleanup_old_backups()
        
        return True
    except Exception as e:
        log.error("Backup failed: %s", e)
        return False


def cleanup_old_backdays(max_days: int = 30):
    try:
        cutoff = datetime.now() - timedelta(days=max_days)
        
        for backup in BACKUP_DIR.iterdir():
            if backup.is_dir():
                try:
                    backup_date = datetime.strptime(backup.name, "%Y-%m-%d_%H%M")
                    if backup_date < cutoff:
                        shutil.rmtree(backup)
                        log.info("Deleted old backup: %s", backup.name)
                except ValueError:
                    pass
    except Exception as e:
        log.error("Backup cleanup failed: %s", e)


def cleanup_old_backups(max_backups: int = 30):
    try:
        backups = sorted(BACKUP_DIR.iterdir(), key=lambda x: x.name, reverse=True)
        
        for backup in backups[max_backups:]:
            if backup.is_dir():
                shutil.rmtree(backup)
                log.info("Deleted old backup: %s", backup.name)
    except Exception as e:
        log.error("Backup cleanup failed: %s", e)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    backup_data()
