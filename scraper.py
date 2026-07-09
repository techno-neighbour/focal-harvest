import urllib.parse
import requests
import httpx
import asyncio
from bs4 import BeautifulSoup
from readability import Document
import time
import random
import os
from typing import List, Dict, Any, Callable, Optional
import utils
import hashlib
import datetime
import json
import threading
import re
import html
from youtube_transcript_api import YouTubeTranscriptApi

wayback_cache_lock = threading.Lock()
logger = utils.setup_logging()

# List of common User-Agents to avoid scraping detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
]

def get_headers() -> Dict[str, str]:
    """Generates random headers to mimic a normal browser request."""
    ua = random.choice(USER_AGENTS)
    
    # Match client hints to the selected user-agent
    if "Chrome/120" in ua:
        ch_ua = '"Not A(Brand";v="99", "Google Chrome";v="120", "Chromium";v="120"'
    elif "Chrome/119" in ua:
        ch_ua = '"Not A(Brand";v="99", "Google Chrome";v="119", "Chromium";v="119"'
    else:
        ch_ua = '"Not A(Brand";v="99", "Chromium";v="120"'

    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": "https://www.google.com/",
        "sec-ch-ua": ch_ua,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"'
    }

def search_tavily(query: str, api_key: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches using the Tavily Search API. Returns a structured list of results
    containing 'title', 'url', and 'snippet'.
    """
    logger.info("Executing Tavily API search for query: '%s' (max_results=%d)", query, max_results)
    url = "https://api.tavily.com/search"
    headers = {"Content-Type": "application/json"}
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
        "max_results": max_results
    }
    
    try:
        response = utils.safe_request("post", url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            results = []
            for item in res_json.get("results", []):
                results.append({
                    "title": item.get("title", "No Title"),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")
                })
            logger.info("Tavily search returned %d candidate results.", len(results))
            return results
        else:
            logger.error("Tavily search returned non-200 status code: %d", response.status_code)
            return []
    except Exception as e:
        logger.error("Exception during Tavily search: %s", str(e))
        return []

def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Orchestrated search function that routes to Tavily Search if TAVILY_API_KEY
    is configured, falling back to DuckDuckGo search.
    """
    try:
        import config_manager
        config = config_manager.load_config()
    except Exception:
        config = {}
        
    tavily_key = config.get("tavily_api_key") or os.environ.get("TAVILY_API_KEY")
    if tavily_key:
        logger.info("Preferred search provider Tavily detected.")
        return search_tavily(query, tavily_key, max_results)
    else:
        logger.info("No Tavily API key found. Falling back to multi-engine Aggregated Crawler...")
        return search_aggregated(query, max_results)

def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches DuckDuckGo HTML interface and returns list of results.
    Each result contains 'title', 'url', and 'snippet'.
    """
    logger.info("Executing DuckDuckGo HTML search for query: '%s' (max_results=%d)", query, max_results)
    encoded_query = urllib.parse.quote_plus(query)
    # Using the standard HTML-only version of DuckDuckGo which is lightweight and reliable
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    try:
        response = utils.safe_request("get", url, headers=get_headers(), timeout=15)
        if response.status_code != 200:
            # Try a fallback URL (Lite interface)
            url_lite = f"https://lite.duckduckgo.com/lite/"
            response = utils.safe_request("post", url_lite, data={"q": query}, headers=get_headers(), timeout=15)
            if response.status_code != 200:
                return []
                
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        # In html.duckduckgo.com, results are inside <div class="result results_links results_links_deep web-result">
        result_elements = soup.find_all('div', class_='result')
        
        # If result_elements is empty, try parsing Lite layout
        if not result_elements:
            # Lite layout uses tables
            tables = soup.find_all('table')
            # Let's search for table rows containing links
            for table in tables:
                rows = table.find_all('tr')
                # Iterate row-by-row to find result-link and look ahead for result-snippet
                for i, r in enumerate(rows):
                    link_el = r.find('a', class_='result-link')
                    if link_el and 'href' in link_el.attrs:
                        title = link_el.get_text().strip()
                        raw_url = link_el['href']
                        
                        # Resolve duckduckgo redirect url if necessary
                        parsed_url = urllib.parse.urlparse(raw_url)
                        actual_url = raw_url
                        if parsed_url.netloc in ('duckduckgo.com', 'lite.duckduckgo.com') and 'uddg' in urllib.parse.parse_qs(parsed_url.query):
                            actual_url = urllib.parse.parse_qs(parsed_url.query)['uddg'][0]
                        
                        # Look ahead up to 3 rows to find the snippet
                        snippet = ""
                        for next_idx in range(i + 1, min(i + 4, len(rows))):
                            next_row = rows[next_idx]
                            # If we hit another result link, stop looking ahead
                            if next_row.find('a', class_='result-link'):
                                break
                            snippet_el = next_row.find('td', class_='result-snippet')
                            if snippet_el:
                                snippet = snippet_el.get_text().strip()
                                break
                        
                        results.append({
                            "title": title,
                            "url": actual_url,
                            "snippet": snippet
                        })
                        if len(results) >= max_results:
                            break
                if results:
                    break
        else:
            for element in result_elements:
                link_el = element.find('a', class_='result__url') or element.find('a', class_='result__snippet')
                title_el = element.find('a', class_='result__a')
                snippet_el = element.find('a', class_='result__snippet')
                
                if title_el and title_el.get('href'):
                    title = title_el.get_text().strip()
                    raw_url = title_el['href']
                    
                    # Clean up DuckDuckGo redirect link if present
                    parsed_url = urllib.parse.urlparse(raw_url)
                    actual_url = raw_url
                    if parsed_url.netloc in ('duckduckgo.com', 'html.duckduckgo.com') and 'uddg' in urllib.parse.parse_qs(parsed_url.query):
                        actual_url = urllib.parse.parse_qs(parsed_url.query)['uddg'][0]
                    
                    snippet = snippet_el.get_text().strip() if snippet_el else ""
                    
                    results.append({
                        "title": title,
                        "url": actual_url,
                        "snippet": snippet
                    })
                    
                    if len(results) >= max_results:
                        break
                        
        return results
    except Exception as e:
        # In case of any error, fail gracefully and return empty list
        return []

def _search_google_mobile(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches Google using the old-school JS-free mobile layout.
    """
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://google.com/search?q={encoded_query}&num={max_results}&gbv=1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    try:
        response = utils.safe_request("get", url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
        for result in soup.find_all("div", class_="ZINbbc xpd O0w1lb rl7tS"):
            link_element = result.find("a", href=True)
            if not link_element:
                continue
                
            raw_url = link_element["href"]
            if "/url?q=" in raw_url:
                clean_url = raw_url.split("/url?q=")[1].split("&")[0]
                clean_url = urllib.parse.unquote(clean_url)
                
                # Fetch text snippet
                snippet_div = result.find("div", class_="BNeawe s3v9rd AP7Wnd")
                description = snippet_div.get_text() if snippet_div else ""
                
                # Fetch title
                title_div = result.find("div", class_="BNeawe vvjwfb rl7tS dd1u6b title") or result.find("div", class_="BNeawe vvjwfb rl7tS dd1u6b")
                title = title_div.get_text() if title_div else "No Title"
                
                results.append({
                    "title": title,
                    "url": clean_url,
                    "snippet": description
                })
                if len(results) >= max_results:
                    break
        return results
    except Exception:
        return []

def search_aggregated(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Performs concurrent aggregated search using both Google Mobile and DuckDuckGo.
    """
    logger.info("Executing aggregated search (Google Mobile + DDG) for query: '%s' (max_results=%d)", query, max_results)
    google_res = _search_google_mobile(query, max_results * 2)
    ddg_res = search_duckduckgo(query, max_results * 2)
    logger.info("Retrieved candidate pool: Google Mobile (%d), DuckDuckGo (%d)", len(google_res), len(ddg_res))
    
    seen_urls = set()
    merged = []
    
    for r in (google_res + ddg_res):
        norm_url = r["url"].rstrip("/")
        if norm_url not in seen_urls:
            seen_urls.add(norm_url)
            merged.append(r)
            if len(merged) >= max_results:
                break
    logger.info("Merged and deduplicated aggregated results to %d candidates.", len(merged))
    return merged

def _parse_sitemap_xml(xml_content: str, max_urls: int = 10) -> List[str]:
    """
    Parses standard sitemap XML structure to extract page/sitemap URLs.
    """
    try:
        import warnings
        from bs4 import XMLParsedAsHTMLWarning
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    except ImportError:
        pass

    try:
        soup = BeautifulSoup(xml_content, "html.parser")
        is_index = soup.find("sitemapindex") is not None or soup.find("sitemap") is not None
        
        loc_tags = soup.find_all("loc")
        urls = []
        for tag in loc_tags:
            url = tag.get_text().strip()
            if not url:
                continue
                
            if is_index:
                urls.append(url)
            else:
                # Exclude tag, category, author archive pages (non-articles)
                url_lower = url.lower()
                exclude_patterns = ["/tagged/", "/category/", "/author/", "/@", "/search/", "/tags/", "/categories/"]
                if any(pat in url_lower for pat in exclude_patterns):
                    continue
                urls.append(url)
                
            if len(urls) >= max_urls:
                break
        return urls
    except Exception:
        return []

def scan_sitemap_urls(domain: str, max_urls: int = 10) -> List[str]:
    """
    Scans a domain for XML sitemaps by reading its robots.txt first,
    falling back to common paths if none are declared.
    """
    logger.info("Initializing sitemap scan for domain: %s", domain)
    sitemap_urls = []
    headers = get_headers()
    
    # Tier 1: Try reading robots.txt dynamically
    robots_url = f"https://{domain}/robots.txt"
    try:
        response = utils.safe_request("get", robots_url, headers=headers, timeout=10)
        if response.status_code == 200:
            logger.info("Successfully fetched robots.txt for domain: %s", domain)
            for line in response.text.splitlines():
                line = line.strip()
                if line.lower().startswith("sitemap:"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        sitemaps_found = parts[1].strip()
                        if sitemaps_found and sitemaps_found not in sitemap_urls:
                            sitemap_urls.append(sitemaps_found)
            if sitemap_urls:
                logger.info("Found %d sitemap URL(s) listed in robots.txt", len(sitemap_urls))
    except Exception as e:
        logger.error("Exception scanning robots.txt on %s: %s", domain, str(e))
        
    # Tier 2: Fall back to guessing common paths if no sitemaps were found in robots.txt
    if not sitemap_urls:
        logger.info("No sitemaps declared in robots.txt. Falling back to guessing standard paths.")
        sitemap_paths = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-posts.xml", "/sitemap/sitemap.xml"]
        for path in sitemap_paths:
            sitemap_urls.append(f"https://{domain}{path}")
            
    # Scan the resolved sitemap URLs (resolving indexes dynamically)
    for url in sitemap_urls:
        try:
            logger.info("Attempting to parse sitemap XML: %s", url)
            response = utils.safe_request("get", url, headers=headers, timeout=10)
            if response.status_code == 200:
                is_index = "sitemapindex" in response.text or "<sitemap>" in response.text
                urls = _parse_sitemap_xml(response.text, max_urls)
                
                if not is_index and urls:
                    logger.info("Successfully resolved %d pages from sitemap: %s", len(urls), url)
                    return urls
                elif is_index and urls:
                    logger.info("Detected Sitemap Index with %d sub-sitemaps at %s. Resolving recursively...", len(urls), url)
                    prioritized = []
                    others = []
                    for sub_url in urls:
                        sub_lower = sub_url.lower()
                        if any(k in sub_lower for k in ["post", "article", "story", "page", "sitemap-1", "sitemap_1"]):
                            prioritized.append(sub_url)
                        else:
                            others.append(sub_url)
                            
                    # Query sub-sitemaps in order of priority
                    for sub_url in (prioritized + others):
                        try:
                            logger.info("Querying nested sub-sitemap: %s", sub_url)
                            sub_resp = utils.safe_request("get", sub_url, headers=headers, timeout=10)
                            if sub_resp.status_code == 200:
                                sub_pages = _parse_sitemap_xml(sub_resp.text, max_urls)
                                if sub_pages:
                                    logger.info("Resolved %d pages from sub-sitemap: %s", len(sub_pages), sub_url)
                                    return sub_pages
                        except Exception as sub_err:
                            logger.error("Exception crawling nested sitemap %s: %s", sub_url, str(sub_err))
                            continue
        except Exception as err:
            logger.error("Exception crawling sitemap %s: %s", url, str(err))
            continue
            
    logger.warning("No public sitemap URLs could be resolved for domain: %s", domain)
    return []

CACHE_DIR = "reports/cache"

def get_cache_filepath(url: str) -> str:
    """Generates the local cache filepath for a given URL using its MD5 hash."""
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.json")

def load_cached_url(url: str, expiration_hours: int) -> Optional[Dict[str, Any]]:
    """Loads a cached scraping result from disk if it exists and is not expired."""
    filepath = get_cache_filepath(url)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            cached_data = json.load(f)
            
        timestamp_str = cached_data.get("timestamp")
        if not timestamp_str:
            return None
            
        cached_time = datetime.datetime.fromisoformat(timestamp_str)
        now = datetime.datetime.now()
        age = now - cached_time
        
        if age.total_seconds() > expiration_hours * 3600:
            return None # Expired
            
        return cached_data.get("scraped_dict")
    except Exception:
        return None

def save_cached_url(url: str, scraped_dict: Dict[str, Any]) -> None:
    """Saves a successful scraping result to the local cache directory."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        filepath = get_cache_filepath(url)
        payload = {
            "url": url,
            "timestamp": datetime.datetime.now().isoformat(),
            "scraped_dict": scraped_dict
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def _fetch_wayback_cache(url: str, timeout: int = 15) -> Optional[str]:
    """
    Retrieves the pre-rendered HTML page copy from the Internet Archive Wayback Machine.
    """
    cache_url = f"https://web.archive.org/web/2/{url}"
    logger.info("Querying Wayback Machine direct redirect cache for URL: %s", url)
    
    with wayback_cache_lock:
        try:
            # Stagger sequential requests to behave politely to Archive.org API
            time.sleep(random.uniform(1.5, 3.0))
            
            # Request directly and let requests follow the 302/307 redirect
            response = requests.get(cache_url, headers=get_headers(), timeout=timeout, allow_redirects=True)
            if response.status_code == 200 and "web.archive.org/web/" in response.url:
                logger.info("Wayback Machine cache hit found for URL: %s", url)
                return response.text
            else:
                logger.warning("Wayback Machine returned status %d or redirected elsewhere for URL: %s", response.status_code if response else 0, url)
        except Exception as e:
            logger.error("Exception fetching Wayback Machine cache for %s: %s", url, str(e))
    return None

def _clean_wayback_html(html_content: str) -> str:
    """
    Strips the Wayback Machine toolbar and overlay elements.
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Decompose elements with IDs containing 'wm-' (Wayback Machine interface)
        for el in soup.find_all(id=lambda val: val and "wm-" in val):
            el.decompose()
        for script in soup.find_all("script"):
            src = script.get("src", "")
            if "archive.org" in src:
                script.decompose()
        return str(soup)
    except Exception:
        return html_content

def _is_wayback_boilerplate(text: str) -> bool:
    """
    Checks if the text content consists primarily of Wayback Machine's own donation/toolbar text.
    """
    text_lower = text.lower()
    indicators = [
        "please don't scroll past this",
        "internet archive",
        "wayback machine",
        "archive.org",
        "donation",
        "chip in"
    ]
    if len(text) < 800:
        match_count = sum(1 for ind in indicators if ind in text_lower)
        if match_count >= 2:
            return True
    return False

def scrape_url(url: str, timeout: int = 15, fallback_snippet: str = "") -> Dict[str, Any]:
    """
    Scrapes the target URL, checking local cache first.
    """
    logger.info("Initializing scrape request for URL: %s", url)
    try:
        import config_manager
        config = config_manager.load_config()
        cache_enabled = config.get("cache_enabled", True)
        cache_expire_hours = config.get("cache_expiration_hours", 24)
    except Exception:
        cache_enabled = True
        cache_expire_hours = 24

    if cache_enabled:
        cached = load_cached_url(url, cache_expire_hours)
        if cached:
            raw_text = cached.get("raw_text")
            if raw_text is None or (raw_text.strip() and not _is_wayback_boilerplate(raw_text)):
                logger.info("Cache hit for URL: %s (loading cached content)", url)
                cached["cached"] = True
                return cached

    # Check if YouTube URL and fetch transcript directly
    video_id = _get_youtube_video_id(url)
    if video_id:
        logger.info("YouTube link detected. Attempting direct transcript extraction for ID: %s", video_id)
        transcript = _fetch_youtube_transcript(video_id, timeout=timeout)
        if transcript:
            result = {
                "url": url,
                "title": "YouTube Video Transcript",
                "meta_description": "",
                "raw_text": transcript,
                "headings": [],
                "paragraphs": [transcript],
                "success": True,
                "error": None,
                "cached": False
            }
            logger.info("Successfully extracted YouTube transcript.")
            if cache_enabled and result.get("success"):
                save_cached_url(url, result)
            return result
        else:
            logger.warning("YouTube transcript extraction failed. Falling back to Wayback Machine redirection.")

    # Check if this is a known SPA platform that returns empty shells without JS
    is_spa = any(domain in url for domain in ["facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com", "youtu.be"])
    
    if is_spa:
        logger.info("Target URL: %s identified as SPA. Querying Wayback Archive...", url)
        cached_html = _fetch_wayback_cache(url, timeout)
        if cached_html:
            result = _parse_html_to_scraped_dict(url, cached_html)
            result["cached"] = False
            
            # Apply fallback snippet if content is empty or boilerplate
            if result.get("success"):
                raw_txt = result.get("raw_text", "")
                if (not raw_txt.strip() or _is_wayback_boilerplate(raw_txt)) and fallback_snippet:
                    logger.warning("Scrape returned empty/boilerplate for URL: %s. Applying fallback search snippet.", url)
                    result["raw_text"] = fallback_snippet
                    result["paragraphs"] = [fallback_snippet]
                    if result.get("title") == "[no-title]" or not result.get("title"):
                        result["title"] = "Scraped Snippet"
            
            if cache_enabled and result.get("success"):
                save_cached_url(url, result)
            return result

    result = _perform_scrape_url(url, timeout)
    result["cached"] = False

    # Apply fallback snippet if content is empty or boilerplate
    if result.get("success"):
        raw_txt = result.get("raw_text", "")
        if (not raw_txt.strip() or _is_wayback_boilerplate(raw_txt)) and fallback_snippet:
            logger.warning("Scrape returned empty/boilerplate for URL: %s. Applying fallback search snippet.", url)
            result["raw_text"] = fallback_snippet
            result["paragraphs"] = [fallback_snippet]
            if result.get("title") == "[no-title]" or not result.get("title"):
                result["title"] = "Scraped Snippet"

    if cache_enabled and result.get("success"):
        save_cached_url(url, result)

    logger.info("Scrape completed successfully for URL: %s (length: %d chars)", url, len(result.get("raw_text", "")))
    return result

BOT_BLOCK_SIGNATURES = [
    "radware bot manager",
    "please confirm you are a human",
    "confirm you are not a bot",
    "powered and protected by",          # Imperva / Incapsula footer
    "attention required | cloudflare",
    "checking your browser before accessing",
    "enable javascript and cookies to continue",
    "incapsula",
    "distil networks",
    "bot detection",
    "unusual traffic from your computer network"
]

def _is_bot_blocked(title: str, text: str) -> Optional[str]:
    """
    Checks if the page content matches known anti-bot firewall signatures.
    Returns the matching signature or None.
    """
    combined = (title + " " + text).lower()
    for sig in BOT_BLOCK_SIGNATURES:
        if sig in combined:
            return sig
    return None

def _get_youtube_video_id(url: str) -> Optional[str]:
    """Extracts the 11-character YouTube video ID from a URL."""
    match = re.search(r'(?:v=|\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})', url)
    return match.group(1) if match else None

def _fetch_youtube_transcript(video_id: str, timeout: int = 10) -> Optional[str]:
    """
    Fetches the video transcript using the youtube_transcript_api package.
    Returns the full transcript text or None.
    """
    try:
        # Get the transcript
        transcript_list = YouTubeTranscriptApi().fetch(video_id)
        # Combine all parts into a clean space-separated text block
        return " ".join([entry.text for entry in transcript_list])
    except Exception as e:
        logger.error("Exception fetching YouTube transcript via API: %s", str(e))
        return None

def _extract_longest_strings(data: Any) -> List[str]:
    """
    Recursively traverses a JSON structure to extract all text strings longer 
    than 80 characters, filtering out CSS classes, layout elements, and URLs.
    """
    strings = []
    if isinstance(data, str):
        val = data.strip()
        # Filter out URLs, JSON brackets, and short UI text
        if len(val) > 80 and not val.startswith("http") and not val.startswith("/") and "{" not in val:
            strings.append(val)
    elif isinstance(data, dict):
        for v in data.values():
            strings.extend(_extract_longest_strings(v))
    elif isinstance(data, list):
        for item in data:
            strings.extend(_extract_longest_strings(item))
    return strings

def _try_extract_ssr_data(soup: BeautifulSoup) -> Optional[List[str]]:
    """
    Looks for Next.js or Nuxt SSR data scripts, parses the JSON payload, 
    and returns a list of main text paragraphs.
    """
    # 1. Next.js check
    next_tag = soup.find("script", id="__NEXT_DATA__")
    if next_tag:
        try:
            data = json.loads(next_tag.get_text())
            page_props = data.get("props", {}).get("pageProps", {})
            if page_props:
                return _extract_longest_strings(page_props)
        except Exception:
            pass

    # 2. Nuxt.js check (Nuxt 3 uses __NUXT_DATA__ type="application/json")
    nuxt_tag = soup.find("script", id="__NUXT_DATA__")
    if nuxt_tag:
        try:
            data = json.loads(nuxt_tag.get_text())
            if data:
                return _extract_longest_strings(data)
        except Exception:
            pass
            
    return None

def _parse_html_to_scraped_dict(url: str, html_text: str) -> Dict[str, Any]:
    """
    Parses raw HTML text, extracts title, headings, meta descriptions,
    and returns a sanitized scraped dictionary.
    """
    result = {
        "url": url,
        "title": "",
        "meta_description": "",
        "raw_text": "",
        "headings": [],
        "paragraphs": [],
        "success": False,
        "error": None
    }
    
    try:
        full_soup = BeautifulSoup(html_text, 'html.parser')
        
        # Try extracting Next.js / Nuxt SSR data first
        ssr_paragraphs = _try_extract_ssr_data(full_soup)
        if ssr_paragraphs:
            result["title"] = full_soup.title.get_text().strip() if full_soup.title else "SSR Scraped Page"
            result["paragraphs"] = ssr_paragraphs
            result["raw_text"] = "\n\n".join(ssr_paragraphs)
            result["success"] = True
            logger.info("Successfully extracted %d paragraphs from SSR JSON block for URL: %s", len(ssr_paragraphs), url)
            return result
            
        meta_desc = full_soup.find('meta', attrs={'name': 'description'}) or full_soup.find('meta', attrs={'property': 'og:description'})
        if meta_desc and meta_desc.get('content'):
            result["meta_description"] = meta_desc['content'].strip()
            
        if full_soup.title:
            result["title"] = full_soup.title.get_text().strip()

        readability_text = ""
        readability_headings = []
        readability_paragraphs = []
        
        try:
            doc = Document(html_text)
            readability_title = doc.title().strip()
            if readability_title:
                result["title"] = readability_title
                
            summary_html = doc.summary()
            container = BeautifulSoup(summary_html, 'html.parser')
            
            extracted_headings = []
            extracted_paragraphs = []
            all_text_blocks = []
            
            for element in container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li']):
                text = element.get_text().strip()
                if len(text) < 10:
                    continue
                    
                tag_name = element.name
                if tag_name.startswith('h'):
                    level = int(tag_name[1])
                    heading_info = {"level": level, "text": text}
                    extracted_headings.append(heading_info)
                    all_text_blocks.append(f"\n##{ '#' * (level-1) } {text}\n")
                else:
                    extracted_paragraphs.append(text)
                    all_text_blocks.append(text)
                    
            raw_text = "\n\n".join(all_text_blocks)
            if not raw_text.strip():
                text = container.get_text(separator='\n')
                lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 15]
                raw_text = "\n\n".join(lines)
                extracted_paragraphs = lines
                
            readability_text = raw_text
            readability_headings = extracted_headings
            readability_paragraphs = extracted_paragraphs
        except Exception:
            pass

        if len(readability_text.strip()) > 200:
            result["headings"] = readability_headings
            result["paragraphs"] = readability_paragraphs
            result["raw_text"] = readability_text
        else:
            soup_copy = BeautifulSoup(html_text, 'html.parser')
            for element in soup_copy(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript", "svg"]):
                element.decompose()
                
            container = None
            for selector in ['article', 'main', '[role="main"]', '.post', '.article', '.entry', '.content', '#content', '#main']:
                found = soup_copy.select(selector)
                if found:
                    best_match = max(found, key=lambda el: len(el.get_text()))
                    if len(best_match.get_text()) > 300:
                        container = best_match
                        break
            
            if not container:
                container = soup_copy.body if soup_copy.body else soup_copy
                
            extracted_headings = []
            extracted_paragraphs = []
            all_text_blocks = []
            
            for element in container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li']):
                text = element.get_text().strip()
                if len(text) < 10:
                    continue
                    
                tag_name = element.name
                if tag_name.startswith('h'):
                    level = int(tag_name[1])
                    heading_info = {"level": level, "text": text}
                    extracted_headings.append(heading_info)
                    all_text_blocks.append(f"\n##{ '#' * (level-1) } {text}\n")
                else:
                    extracted_paragraphs.append(text)
                    all_text_blocks.append(text)
                    
            raw_text = "\n\n".join(all_text_blocks)
            if not raw_text.strip():
                text = container.get_text(separator='\n')
                lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 15]
                raw_text = "\n\n".join(lines)
                extracted_paragraphs = lines
                
            result["headings"] = extracted_headings
            result["paragraphs"] = extracted_paragraphs
            result["raw_text"] = raw_text

        # Check if the page is actually a bot blocker page (e.g. Radware, Cloudflare, Imperva)
        block_signature = _is_bot_blocked(result["title"], result["raw_text"])
        if block_signature:
            result["success"] = False
            result["error"] = f"Blocked by firewall (matched: {block_signature})"
            result["raw_text"] = ""
            result["paragraphs"] = []
            logger.warning("Bot blocker detected on URL %s: %s", url, block_signature)
            return result

        # Check if the page is YouTube layout skeleton without transcript
        if "youtube.com" in url or "youtu.be" in url:
            if not result.get("raw_text") or len(result["raw_text"]) < 300 or "How YouTube works" in result["raw_text"]:
                result["success"] = False
                result["error"] = "YouTube Transcript Unavailable (PoToken required)"
                result["raw_text"] = ""
                result["paragraphs"] = []
                logger.warning("YouTube scrape failed to extract transcript for URL: %s", url)
                return result

        result["success"] = True
        return result
        
    except Exception as e:
        result["error"] = str(e)
        return result

def _perform_scrape_url(url: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Scrapes the target URL, extracts title, headings, meta descriptions, 
    and returns sanitized text content sorted by structural elements.
    """
    result = {
        "url": url,
        "title": "",
        "meta_description": "",
        "raw_text": "",
        "headings": [],
        "paragraphs": [],
        "success": False,
        "error": None
    }
    
    try:
        response = utils.safe_request("get", url, headers=get_headers(), timeout=timeout, allow_redirects=True)
        if response.status_code != 200:
            result["error"] = f"HTTP status {response.status_code}"
            return result
            
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type:
            result["error"] = f"Unsupported content type: {content_type}"
            return result
            
        # Check if response body is empty or whitespace
        if not response.text or not response.text.strip():
            result["error"] = "Empty response body"
            return result

        return _parse_html_to_scraped_dict(url, response.text)
        
    except Exception as e:
        result["error"] = str(e)
        return result

async def _scrape_urls_concurrently(
    urls: List[str], 
    timeout: int = 15, 
    status_callback: Optional[Callable[[str], None]] = None,
    url_snippets: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    # Wrap the synchronous call to scrape_url in a separate thread using asyncio.to_thread
    async def scrape_and_notify(url):
        fallback_snippet = url_snippets.get(url, "") if url_snippets else ""
        if fallback_snippet:
            res = await asyncio.to_thread(scrape_url, url, timeout, fallback_snippet)
        else:
            res = await asyncio.to_thread(scrape_url, url, timeout)
        if status_callback:
            status_callback(res["url"])
        return res

    tasks = [scrape_and_notify(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results

def scrape_urls_concurrently(
    urls: List[str], 
    timeout: int = 15, 
    status_callback: Optional[Callable[[str], None]] = None,
    url_snippets: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """
    Scrape multiple URLs concurrently using asyncio and requests in a thread pool.
    """
    return asyncio.run(_scrape_urls_concurrently(urls, timeout, status_callback, url_snippets))

def scrape_urls_adaptive(
    candidate_results: List[Dict[str, Any]],
    target_count: int,
    timeout: int = 15,
    status_callback: Optional[Callable[[str], None]] = None
) -> List[Dict[str, Any]]:
    """
    Scrapes URLs from candidate_results concurrently in batches.
    Replenishes failed/empty results until target_count high-quality scrapes are reached,
    or candidates are exhausted.
    """
    logger.info("Initializing adaptive queue scraping for %d candidate(s). Target count: %d", len(candidate_results), target_count)
    all_scraped = []
    pool = list(candidate_results)
    scraped_urls = set()
    
    url_snippets = {r["url"]: r.get("snippet", "") for r in pool}
    
    def get_quality_score(res: Dict[str, Any]) -> int:
        if not res.get("success"):
            return 0
        raw_txt = res.get("raw_text", "")
        if not raw_txt.strip() or _is_wayback_boilerplate(raw_txt):
            return 1
        if res.get("title") == "Scraped Snippet":
            return 2
        return 3

    while pool:
        # Count how many quality 3 or 2 results we have
        good_count = sum(1 for r in all_scraped if get_quality_score(r) >= 2)
        if good_count >= target_count:
            break
            
        # Determine batch size to fetch next
        needed = target_count - good_count
        logger.info("Adaptive replenishment loop state: %d/%d quality resources scraped. Need %d more.", good_count, target_count, needed)
        batch = []
        while len(batch) < needed and pool:
            candidate = pool.pop(0)
            url = candidate["url"]
            if url not in scraped_urls:
                scraped_urls.add(url)
                batch.append(url)
                
        if not batch:
            break
            
        # Scrape concurrently
        logger.info("Scraping next batch of %d URLs concurrently.", len(batch))
        batch_results = scrape_urls_concurrently(
            batch, 
            timeout=timeout, 
            status_callback=status_callback, 
            url_snippets=url_snippets
        )
        all_scraped.extend(batch_results)
        
    # Sort all scraped results by quality score descending
    all_scraped.sort(key=get_quality_score, reverse=True)
    
    # Return the top target_count results
    final_results = all_scraped[:target_count]
    logger.info("Adaptive queue finished. Returning top %d results out of %d total scraped.", len(final_results), len(all_scraped))
    return final_results

# Simple test block
if __name__ == "__main__":
    print("Testing Search...")
    search_res = search_duckduckgo("python web scraping", max_results=3)
    print(f"Search results count: {len(search_res)}")
    for r in search_res:
        title_safe = r['title'].encode('ascii', 'replace').decode('ascii')
        snippet_safe = r['snippet'].encode('ascii', 'replace').decode('ascii')
        print(f"Title: {title_safe}")
        print(f"URL: {r['url']}")
        print(f"Snippet: {snippet_safe}\n")
        
    if search_res:
        print(f"Testing Scraping {search_res[0]['url']}...")
        scrape_res = scrape_urls_concurrently([search_res[0]['url']])[0]
        print(f"Success: {scrape_res['success']}")
        title_safe = scrape_res['title'].encode('ascii', 'replace').decode('ascii')
        print(f"Title: {title_safe}")
        print(f"Headings count: {len(scrape_res['headings'])}")
        print(f"Paragraphs count: {len(scrape_res['paragraphs'])}")
        raw_text_safe = scrape_res['raw_text'][:100].encode('ascii', 'replace').decode('ascii')
        print(f"Sample raw text (100 chars): {raw_text_safe}...")

