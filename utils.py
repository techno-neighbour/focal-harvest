import time
import random
import requests
import logging
import os
from typing import Any, Optional, Dict
import sys

try:
    from curl_cffi import requests as requests_cffi
except ImportError:
    requests_cffi = None

try:
    import rookiepy
except ImportError:
    rookiepy = None

def get_cookies_from_browser(domain: str, browser: str = "any") -> Optional[str]:
    """
    Tries to decrypt and load cookies for a specific domain from local browser profiles using rookiepy.
    """
    if rookiepy is None:
        return None
    try:
        browser_name = browser.lower()
        if browser_name == "any":
            method_name = "load"
        else:
            method_name = browser_name
            
        if hasattr(rookiepy, method_name):
            method = getattr(rookiepy, method_name)
            cookies_list = method(domains=[domain])
            cookie_parts = []
            for c in cookies_list:
                name = c.get("name")
                value = c.get("value")
                if name and value:
                    cookie_parts.append(f"{name}={value}")
            return "; ".join(cookie_parts) if cookie_parts else None
    except Exception as e:
        setup_logging().warning("Automated browser cookie extraction failed for domain %s: %s", domain, str(e))
    return None

def parse_netscape_cookies(filepath: str) -> Dict[str, str]:
    """
    Parses a standard Netscape/Mozilla cookies.txt file and returns a dictionary
    mapping domains to their formatted Cookie header strings.
    """
    cookies_by_domain = {}
    if not os.path.exists(filepath):
        return cookies_by_domain
        
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    domain = parts[0].strip().lower()
                    if domain.startswith("."):
                        domain = domain[1:]
                    name = parts[5].strip()
                    value = parts[6].strip()
                    
                    if domain not in cookies_by_domain:
                        cookies_by_domain[domain] = []
                    cookies_by_domain[domain].append(f"{name}={value}")
    except Exception as e:
        setup_logging().warning("Error parsing Netscape cookies file %s: %s", filepath, str(e))
        
    formatted_cookies = {}
    for domain, parts_list in cookies_by_domain.items():
        formatted_cookies[domain] = "; ".join(parts_list)
    return formatted_cookies

def test_cookie_extraction_diagnostics() -> Dict[str, Any]:
    """
    Runs diagnostic checks on the cookie extraction engine.
    Returns status and helpful suggestions on blocks or locks.
    """
    results = {
        "rookiepy_installed": rookiepy is not None,
        "status": "OK",
        "message": "Automated cookie extraction is functional."
    }
    
    if rookiepy is None:
        results["status"] = "MISSING_DEPENDENCY"
        results["message"] = "rookiepy library is not installed. Run 'pip install rookiepy' to enable auto-extraction."
        return results
        
    try:
        # Try a test extraction on a dummy domain to check OS permission / keychains
        rookiepy.load(domains=["example.com"])
    except PermissionError as pe:
        results["status"] = "BLOCKED_BY_AV"
        results["message"] = f"Access Denied: {str(pe)}. This is commonly caused by Windows Defender or local Antivirus blocking credential extraction. Please whitelist this directory."
    except Exception as e:
        err_msg = str(e)
        if "lock" in err_msg.lower() or "database is locked" in err_msg.lower():
            results["status"] = "DATABASE_LOCKED"
            results["message"] = "Browser database is locked. Please close Chrome/Edge/Firefox completely before extracting cookies."
        else:
            results["status"] = "ERROR"
            results["message"] = f"Extraction failed: {err_msg}"
            
    return results

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
            # Auto-inject configured session cookies and user-agents from config if present
            try:
                import config_manager
                config = config_manager.load_config()
                
                # Parse the target domain
                import urllib.parse
                parsed_url = urllib.parse.urlparse(url)
                netloc = parsed_url.netloc.lower()

                # Check for custom User-Agent override first
                custom_ua = config.get("custom_user_agent")
                if custom_ua:
                    if "headers" not in kwargs or kwargs["headers"] is None:
                        kwargs["headers"] = {}
                    kwargs["headers"]["User-Agent"] = custom_ua
                
                matched_domain = None
                cookie_val = None
                
                # 0. Check for a cookies.txt file (check config/cookies.txt first, then root fallback)
                cookie_path = None
                if os.path.exists(os.path.join("config", "cookies.txt")):
                    cookie_path = os.path.join("config", "cookies.txt")
                elif os.path.exists("cookies.txt"):
                    cookie_path = "cookies.txt"
                    
                if cookie_path:
                    netscape_cookies = parse_netscape_cookies(cookie_path)
                    for dom in netscape_cookies:
                        if netloc == dom or netloc.endswith("." + dom):
                            cookie_val = netscape_cookies[dom]
                            matched_domain = dom
                            break
                
                # 1. Check auto-extraction next if enabled
                if not cookie_val and config.get("auto_extract_cookies", False):
                    parts = netloc.split(".")
                    if len(parts) >= 2:
                        root_domain = ".".join(parts[-2:])
                        if len(parts) >= 3 and parts[-2] in ["com", "co", "org", "net", "edu", "gov"]:
                            root_domain = ".".join(parts[-3:])
                    else:
                        root_domain = netloc
                        
                    cookie_val = get_cookies_from_browser(root_domain, config.get("browser_source", "any"))
                    if cookie_val:
                        matched_domain = root_domain
                
                # 2. Fallback to universal_cookies map
                if not cookie_val:
                    universal_cookies = config.get("universal_cookies", {})
                    for dom in universal_cookies:
                        if netloc == dom or netloc.endswith("." + dom):
                            cookie_val = universal_cookies[dom]
                            matched_domain = dom
                            break
                            
                 # Apply cookie and autodetect Edge User-Agent matching
                if cookie_val:
                    if "headers" not in kwargs or kwargs["headers"] is None:
                        kwargs["headers"] = {}
                    kwargs["headers"]["Cookie"] = cookie_val
                    # If the cookie has edgebucket and no custom User-Agent is set, default to Edge User-Agent to prevent 403 blocks
                    if "edgebucket" in cookie_val and not custom_ua:
                        kwargs["headers"]["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
                else:
                    # If no cookies are configured, use Discordbot User-Agent to bypass Quora guest walls
                    if "quora.com" in netloc and not custom_ua:
                        if "headers" not in kwargs or kwargs["headers"] is None:
                            kwargs["headers"] = {}
                        kwargs["headers"]["User-Agent"] = "Discordbot/2.0 (+https://discordapp.com)"
            except Exception:
                pass

            logger.info("Executing HTTP %s request to URL: %s (attempt %d) with headers: %s", method.upper(), url, attempt + 1, {k: (v[:30] + "..." if len(v) > 30 else v) for k, v in kwargs.get("headers", {}).items()})
            if requests_cffi is not None and 'unittest' not in sys.modules:
                # Use curl_cffi to impersonate standard Chrome browser TLS/JA3 signatures
                # Strip conflicting browser headers so curl_cffi generates consistent fingerprints
                if "headers" in kwargs and kwargs["headers"]:
                    cleaned = {}
                    allowed = ["user-agent", "cookie", "accept", "accept-language", "authorization", "content-type"]
                    for k, v in kwargs["headers"].items():
                        if k.lower() in allowed:
                            cleaned[k] = v
                    kwargs["headers"] = cleaned
                response = requests_cffi.request(method.lower(), url, impersonate="chrome", **kwargs)
            else:
                req_func = getattr(requests, method.lower())
                response = req_func(url, **kwargs)
            
            # Check if response status code triggers a retry
            if response.status_code in status_codes and attempt < max_retries:
                attempt += 1
                if response.status_code == 429:
                    # Rate limit requires a longer cooling period to let the 60s window reset
                    sleep_time = 10.0 * attempt + random.uniform(0.5, 1.5)
                else:
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

import threading

class TokenBucket:
    def __init__(self, capacity: float, fill_rate: float):
        """
        capacity: maximum tokens the bucket can hold
        fill_rate: tokens refilled per second
        """
        self.capacity = float(capacity)
        self.fill_rate = float(fill_rate)
        self.tokens = float(capacity)
        self.last_update = time.time()
        self.lock = threading.Lock()

    def consume(self, amount: float = 1.0) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False

    def wait_for_token(self, amount: float = 1.0):
        while True:
            if self.consume(amount):
                return
            with self.lock:
                now = time.time()
                elapsed = now - self.last_update
                current_tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
                needed = amount - current_tokens
                sleep_time = needed / self.fill_rate
            time.sleep(max(0.1, sleep_time))

def decompose_query_locally(query: str) -> list:
    """
    Decomposes a user query locally into 4-5 highly targeted sub-questions
    or search vectors without making any external API calls.
    """
    import re
    query_clean = query.strip()
    
    # 1. Detect Comparison Intent (matches "vs", "vs.", "compared to", etc.)
    comparison_triggers = [r"\bvs\b", r"\bvs\.\b", r"\bcompared to\b", r"\bdifference between\b"]
    is_comparison = False
    connector = None
    
    for trigger in comparison_triggers:
        match = re.search(trigger, query_clean, re.IGNORECASE)
        if match:
            is_comparison = True
            connector = match.group(0)
            break
            
    if is_comparison:
        parts = re.split(re.escape(connector), query_clean, flags=re.IGNORECASE)
        if len(parts) == 2:
            entity_a = parts[0].strip()
            entity_b = parts[1].strip()
            return [
                query_clean,
                f"{entity_a} vs {entity_b} pricing cost",
                f"{entity_a} vs {entity_b} latency speed benchmarks",
                f"{entity_a} vs {entity_b} features context window",
                f"{entity_a} vs {entity_b} developer use cases reddit reviews"
            ]

    # 2. Informational Fallback (Noun Phrase keyword extraction)
    stop_words = {"what", "is", "how", "to", "the", "a", "an", "and", "in", "on", "for", "with", "about", "why", "of"}
    words = [w for w in re.findall(r"\b\w+\b", query_clean.lower()) if w not in stop_words]
    core_topic = " ".join(words[:4]) if words else query_clean
    
    return [
        query_clean,
        f"{core_topic} guide documentation tutorial",
        f"{core_topic} code examples github implementation",
        f"{core_topic} problems bottlenecks errors issues",
        f"{core_topic} best practices latest updates"
    ]

