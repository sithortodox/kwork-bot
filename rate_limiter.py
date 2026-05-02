import time
import threading
from collections import defaultdict
import logging

log = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = defaultdict(list)
        self.lock = threading.Lock()
    
    def allow(self, key: str = "default") -> bool:
        with self.lock:
            now = time.time()
            self.calls[key] = [t for t in self.calls[key] if now - t < self.period]
            
            if len(self.calls[key]) < self.max_calls:
                self.calls[key].append(now)
                return True
            return False
    
    def wait_time(self, key: str = "default") -> float:
        with self.lock:
            now = time.time()
            self.calls[key] = [t for t in self.calls[key] if now - t < self.period]
            
            if len(self.calls[key]) < self.max_calls:
                return 0.0
            
            oldest = min(self.calls[key])
            return self.period - (now - oldest)


TELEGRAM_LIMITER = RateLimiter(25, 1.0)
YOOKASSA_LIMITER = RateLimiter(5, 1.0)
KWORK_LIMITER = RateLimiter(10, 1.0)
