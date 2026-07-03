import time
import random
import requests
from typing import Any

def safe_request(method: str, url: str, **kwargs: Any) -> requests.Response:
    """
    Executes an HTTP request using requests with configurable retry limits and
    exponential backoff with random jitter.
    """
    # Load settings from config to allow user customization
    try:
        import config_manager
        config = config_manager.load_config()
        max_retries = config.get("max_retries", 3)
        backoff_factor = config.get("backoff_factor", 1.0)
        status_codes = config.get("retry_on_status_codes", [429, 500, 502, 503, 504])
    except Exception:
        max_retries = 3
        backoff_factor = 1.0
        status_codes = [429, 500, 502, 503, 504]

    attempt = 0
    while True:
        try:
            req_func = getattr(requests, method.lower())
            response = req_func(url, **kwargs)
            
            # Check if response status code triggers a retry
            if response.status_code in status_codes and attempt < max_retries:
                attempt += 1
                # Exponential backoff: factor * 2^(attempt-1) + small random jitter
                sleep_time = backoff_factor * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                time.sleep(sleep_time)
                continue
                
            return response
            
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout) as e:
            if attempt < max_retries:
                attempt += 1
                sleep_time = backoff_factor * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                time.sleep(sleep_time)
                continue
            raise e
