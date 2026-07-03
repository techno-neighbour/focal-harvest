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
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0"
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
        return search_duckduckgo(query, max_results)

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

def scrape_url(url: str, timeout: int = 15) -> Dict[str, Any]:
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

        # Parse full document with BeautifulSoup first to get meta description and prepare fallback
        full_soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get Meta Description
        meta_desc = full_soup.find('meta', attrs={'name': 'description'}) or full_soup.find('meta', attrs={'property': 'og:description'})
        if meta_desc and meta_desc.get('content'):
            result["meta_description"] = meta_desc['content'].strip()
            
        # Get Title from full_soup by default
        if full_soup.title:
            result["title"] = full_soup.title.get_text().strip()

        # Try using python-readability to extract clean article content
        readability_text = ""
        readability_headings = []
        readability_paragraphs = []
        
        try:
            doc = Document(response.text)
            readability_title = doc.title().strip()
            if readability_title:
                result["title"] = readability_title
                
            summary_html = doc.summary()
            container = BeautifulSoup(summary_html, 'html.parser')
            
            # Extract headings and paragraphs from readability output
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
            # Fall back to BeautifulSoup if readability fails or raises ParserError
            pass

        # Check if readability succeeded in finding a reasonable amount of structured content
        # For non-article pages (directories, tables, indices like Hacker News/GitHub),
        # readability is highly prone to extracting 0 or very few characters.
        if len(readability_text.strip()) > 200:
            result["headings"] = readability_headings
            result["paragraphs"] = readability_paragraphs
            result["raw_text"] = readability_text
        else:
            # Fall back to standard BeautifulSoup cleaning of full document
            soup_copy = BeautifulSoup(response.text, 'html.parser')
            for element in soup_copy(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript", "svg"]):
                element.decompose()
                
            # Try to find primary container
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

async def _scrape_urls_concurrently(urls: List[str], timeout: int = 15, status_callback: Optional[Callable[[str], None]] = None) -> List[Dict[str, Any]]:
    # Wrap the synchronous call to scrape_url in a separate thread using asyncio.to_thread
    async def scrape_and_notify(url):
        res = await asyncio.to_thread(scrape_url, url, timeout)
        if status_callback:
            status_callback(res["url"])
        return res

    tasks = [scrape_and_notify(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results

def scrape_urls_concurrently(urls: List[str], timeout: int = 15, status_callback: Optional[Callable[[str], None]] = None) -> List[Dict[str, Any]]:
    """
    Scrape multiple URLs concurrently using asyncio and requests in a thread pool.
    """
    return asyncio.run(_scrape_urls_concurrently(urls, timeout, status_callback))

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

