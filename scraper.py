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

wayback_cache_lock = threading.Lock()

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
            return results
        else:
            return []
    except Exception as e:
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
        return search_tavily(query, tavily_key, max_results)
    else:
        return search_aggregated(query, max_results)

def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches DuckDuckGo HTML interface and returns list of results.
    Each result contains 'title', 'url', and 'snippet'.
    """
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
    google_res = _search_google_mobile(query, max_results * 2)
    ddg_res = search_duckduckgo(query, max_results * 2)
    
    seen_urls = set()
    merged = []
    
    for r in (google_res + ddg_res):
        norm_url = r["url"].rstrip("/")
        if norm_url not in seen_urls:
            seen_urls.add(norm_url)
            merged.append(r)
            if len(merged) >= max_results:
                break
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
    sitemap_urls = []
    headers = get_headers()
    
    # Tier 1: Try reading robots.txt dynamically
    robots_url = f"https://{domain}/robots.txt"
    try:
        response = utils.safe_request("get", robots_url, headers=headers, timeout=10)
        if response.status_code == 200:
            for line in response.text.splitlines():
                line = line.strip()
                if line.lower().startswith("sitemap:"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        sitemaps_found = parts[1].strip()
                        if sitemaps_found and sitemaps_found not in sitemap_urls:
                            sitemap_urls.append(sitemaps_found)
    except Exception:
        pass
        
    # Tier 2: Fall back to guessing common paths if no sitemaps were found in robots.txt
    if not sitemap_urls:
        sitemap_paths = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-posts.xml", "/sitemap/sitemap.xml"]
        for path in sitemap_paths:
            sitemap_urls.append(f"https://{domain}{path}")
            
    # Scan the resolved sitemap URLs (resolving indexes dynamically)
    for url in sitemap_urls:
        try:
            response = utils.safe_request("get", url, headers=headers, timeout=10)
            if response.status_code == 200:
                is_index = "sitemapindex" in response.text or "<sitemap>" in response.text
                urls = _parse_sitemap_xml(response.text, max_urls)
                
                if not is_index and urls:
                    return urls
                elif is_index and urls:
                    # It's a sitemap index! Locate and prioritize post/article sitemaps
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
                            sub_resp = utils.safe_request("get", sub_url, headers=headers, timeout=10)
                            if sub_resp.status_code == 200:
                                sub_pages = _parse_sitemap_xml(sub_resp.text, max_urls)
                                if sub_pages:
                                    return sub_pages
                        except Exception:
                            continue
        except Exception:
            continue
            
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
    
    with wayback_cache_lock:
        try:
            # Stagger sequential requests to behave politely to Archive.org API
            time.sleep(random.uniform(1.5, 3.0))
            
            # Request directly and let requests follow the 302/307 redirect
            response = requests.get(cache_url, headers=get_headers(), timeout=timeout, allow_redirects=True)
            if response.status_code == 200 and "web.archive.org/web/" in response.url:
                return response.text
        except Exception:
            pass
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

def scrape_url(url: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Scrapes the target URL, checking local cache first.
    """
    try:
        import config_manager
        config = config_manager.load_config()
        cache_enabled = config.get("cache_enabled", True)
        cache_expire_hours = config.get("cache_expiration_hours", 24)
    except Exception:
        cache_enabled = True
        cache_expire_hours = 24

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
            # Only use cache if it has real text and is not Wayback donation boilerplate
            raw_text = cached.get("raw_text")
            if raw_text is None or (raw_text.strip() and not _is_wayback_boilerplate(raw_text)):
                cached["cached"] = True
                return cached

    # Check if this is a known SPA platform that returns empty shells without JS
    is_spa = any(domain in url for domain in ["facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com"])
    
    if is_spa:
        cached_html = _fetch_wayback_cache(url, timeout)
        if cached_html:
            result = _parse_html_to_scraped_dict(url, cached_html)
            result["cached"] = False
            
            # Apply fallback snippet if content is empty or boilerplate
            if result.get("success"):
                raw_txt = result.get("raw_text", "")
                if (not raw_txt.strip() or _is_wayback_boilerplate(raw_txt)) and fallback_snippet:
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
            result["raw_text"] = fallback_snippet
            result["paragraphs"] = [fallback_snippet]
            if result.get("title") == "[no-title]" or not result.get("title"):
                result["title"] = "Scraped Snippet"

    if cache_enabled and result.get("success"):
        save_cached_url(url, result)

    return result

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
    return all_scraped[:target_count]

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

