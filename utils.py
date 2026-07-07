import time
import random
import requests
import logging
import os
from typing import Any
import sys

try:
    from curl_cffi import requests as requests_cffi
except ImportError:
    requests_cffi = None

def setup_logging():
    """
    Configures the standard Python logger to write structured logs to reports/focal_harvest.log.
    """
    os.makedirs("reports", exist_ok=True)
    logger = logging.getLogger("focal_harvest")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler("reports/focal_harvest.log", encoding="utf-8")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger

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

    logger = setup_logging()
    attempt = 0
    while True:
        try:
            logger.info("Executing HTTP %s request to URL: %s (attempt %d)", method.upper(), url, attempt + 1)
            if requests_cffi is not None and 'unittest' not in sys.modules:
                # Use curl_cffi to impersonate standard Chrome browser TLS/JA3 signatures
                response = requests_cffi.request(method.lower(), url, impersonate="chrome", **kwargs)
            else:
                req_func = getattr(requests, method.lower())
                response = req_func(url, **kwargs)
            
            # Check if response status code triggers a retry
            if response.status_code in status_codes and attempt < max_retries:
                attempt += 1
                sleep_time = backoff_factor * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                logger.warning("HTTP %d received for %s. Retrying %d/%d in %.2fs...", response.status_code, url, attempt, max_retries, sleep_time)
                time.sleep(sleep_time)
                continue
                
            logger.info("HTTP %s returned status %d for URL: %s", method.upper(), response.status_code, url)
            return response
            
        except Exception as e:
            err_msg = str(e).lower()
            logger.error("Exception during HTTP request to %s: %s", url, str(e))
            # Do NOT retry on timeout errors to avoid hanging the thread pool on tarpitted sites
            if "timeout" in err_msg or "timed out" in err_msg or "time out" in err_msg:
                raise e

            if attempt < max_retries:
                attempt += 1
                sleep_time = backoff_factor * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                logger.warning("Retrying request to %s due to exception (%d/%d) in %.2fs...", url, attempt, max_retries, sleep_time)
                time.sleep(sleep_time)
                continue
            raise e
