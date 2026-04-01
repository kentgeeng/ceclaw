import requests, time, threading, logging, random
logging.basicConfig(level=logging.INFO)

class APIClient:
    def __init__(self, base_url, max_retries=3):
        self.base_url = base_url.rstrip('/')
        self.max_retries = max_retries
        self.session = requests.Session()
        self._lock = threading.Lock()
        self.stats = {"success": 0, "fail": 0, "retries": 0}
        self._closed = False

    def fetch(self, endpoint, params=None):
        if self._closed:
            logging.error("Client is closed, cannot make requests")
            return None
        
        url = f"{self.base_url}/{endpoint}"
        attempts = 0
        while attempts < self.max_retries:
            try:
                # 使用更合理的 timeout：connect=3, read=10 秒
                resp = self.session.get(url, params=params, timeout=(3, 10))
                if resp.status_code == 200:
                    with self._lock:
                        self.stats["success"] += 1
                    return resp.json()
                raise ValueError(f"Bad status: {resp.status_code}")
            except Exception as e:
                attempts += 1
                with self._lock:
                    self.stats["retries"] += 1
                    if attempts == self.max_retries:
                        self.stats["fail"] += 1
                        logging.error(f"Failed after {attempts} retries: {e}")
                        return None
                # 指數退避 + jitter：0.1 * 2^(attempts-1) + random(0, 0.1)
                backoff = 0.1 * (2 ** (attempts - 1)) + random.uniform(0, 0.1)
                time.sleep(backoff)

    def get_stats(self):
        return self.stats.copy()

    def close(self):
        if not self._closed:
            logging.info("Closing client...")
            self.session.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
