import time
from collections import deque
import threading

class GeminiRateLimiter:
    _lock = threading.Lock()
    _history = {} # key_slot -> deque
    _daily_counts = {} # key_slot -> {"date": "YYYY-MM-DD", "count": int}
    _unavailable_until = {} # key_slot -> timestamp
    
    RPM_LIMIT = 5
    DAILY_LIMIT = 20_000_000
    
    @classmethod
    def record_request(cls, key_slot):
        with cls._lock:
            now = time.time()
            today = time.strftime("%Y-%m-%d", time.gmtime(now))
            
            if key_slot not in cls._history:
                cls._history[key_slot] = deque()
            cls._history[key_slot].append(now)
            
            if key_slot not in cls._daily_counts or cls._daily_counts[key_slot]["date"] != today:
                cls._daily_counts[key_slot] = {"date": today, "count": 0}
            cls._daily_counts[key_slot]["count"] += 1

    @classmethod
    def mark_unavailable(cls, key_slot, seconds):
        with cls._lock:
            cls._unavailable_until[key_slot] = time.time() + seconds

    @classmethod
    def get_wait_time(cls, key_slot):
        with cls._lock:
            now = time.time()
            today = time.strftime("%Y-%m-%d", time.gmtime(now))
            
            # Check daily limit
            if key_slot in cls._daily_counts and cls._daily_counts[key_slot]["date"] == today:
                if cls._daily_counts[key_slot]["count"] >= cls.DAILY_LIMIT:
                    return -1 # Permanently exhausted today
            
            # Check temporary unavailability
            if key_slot in cls._unavailable_until:
                if now < cls._unavailable_until[key_slot]:
                    wait = cls._unavailable_until[key_slot] - now
                    # We still need to check if the rolling window wait is longer
                else:
                    del cls._unavailable_until[key_slot]
                    
            # Check rolling window
            if key_slot not in cls._history:
                return max(0, cls._unavailable_until.get(key_slot, 0) - now)
                
            history = cls._history[key_slot]
            while history and now - history[0] >= 60:
                history.popleft()
                
            window_wait = 0
            if len(history) >= cls.RPM_LIMIT:
                window_wait = 60 - (now - history[0])
                
            temp_wait = max(0, cls._unavailable_until.get(key_slot, 0) - now)
            return max(window_wait, temp_wait)
            
    @classmethod
    def reset(cls):
        with cls._lock:
            cls._history.clear()
            cls._daily_counts.clear()
            cls._unavailable_until.clear()
