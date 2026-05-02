import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

from email_sender import check_and_send_notifications, EMAIL_ENABLED

if __name__ == "__main__":
    if not EMAIL_ENABLED:
        log.error("SendGrid not configured. Set SENDGRID_API_KEY in .env")
        sys.exit(1)
    
    log.info("Starting email notification check...")
    check_and_send_notifications()
    log.info("Email notification check completed")
