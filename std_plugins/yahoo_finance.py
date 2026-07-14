import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["finance.yahoo.com", "yahoo.com"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Yahoo Finance quotes and news articles."""
    soup = BeautifulSoup(html_text, "html.parser")
    parsed_url = urllib.parse.urlparse(url)
    path = parsed_url.path.strip("/")
    
    if "quote" in path:
        return _parse_quote_summary(soup, url)
    else:
        # Default to news article parsing
        return _parse_news_article(soup, url)

def _parse_quote_summary(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    # Extract Ticker and Company Name
    title_el = soup.find('h1')
    title_text = title_el.get_text().strip() if title_el else "Yahoo Finance Quote"
    
    # Extract live price metrics using Yahoo's <fin-streamer> components
    price = "unknown"
    change = ""
    change_pct = ""
    
    price_streamer = soup.find('fin-streamer', attrs={"data-field": "regularMarketPrice"})
    if price_streamer:
        price = price_streamer.get_text().strip()
        
    change_streamer = soup.find('fin-streamer', attrs={"data-field": "regularMarketChange"})
    if change_streamer:
        change = change_streamer.get_text().strip()
        
    pct_streamer = soup.find('fin-streamer', attrs={"data-field": "regularMarketChangePercent"})
    if pct_streamer:
        change_pct = pct_streamer.get_text().strip()
        
    price_info = f"Price: {price}"
    if change and change_pct:
        price_info += f" ({change} / {change_pct})"
        
    # Extract quote summary tables
    # Yahoo Finance groups stats in table rows
    stats_dict = {}
    for tr in soup.find_all('tr'):
        tds = tr.find_all(['td', 'th'])
        if len(tds) == 2:
            key = tds[0].get_text().strip()
            val = tds[1].get_text().strip()
            # Ignore duplicate/empty values
            if key and val and key not in stats_dict:
                stats_dict[key] = val
                
    # Build Markdown table of statistics
    table_lines = []
    if stats_dict:
        table_lines.append("| Metric | Value |")
        table_lines.append("| --- | --- |")
        for k, v in stats_dict.items():
            # Clean up key/value lines from trailing pipes
            clean_k = k.replace("|", "\\|")
            clean_v = v.replace("|", "\\|")
            table_lines.append(f"| {clean_k} | {clean_v} |")
            
    stats_table = "\n".join(table_lines)
    
    raw_text = (
        f"Company: {title_text}\n"
        f"{price_info}\n\n"
        f"Key Statistics:\n{stats_table}"
    )
    
    return {
        "title": f"Yahoo Finance Quote: {title_text}",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Key Statistics"}],
        "paragraphs": [price_info, stats_table],
        "success": True if stats_dict or price != "unknown" else False
    }

def _parse_news_article(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    # Extract Title
    title_el = soup.find('h1') or soup.find(class_=lambda v: v and 'title' in v.lower())
    title = title_el.get_text().strip() if title_el else "Yahoo News Article"
    
    # Locate article body container
    # Yahoo wraps news in classes like "caas-body" or "caas-container" or inside "<article>"
    body_container = (
        soup.find(class_="caas-body") or 
        soup.find(class_="caas-container") or 
        soup.find("article")
    )
    
    target_el = body_container if body_container else soup.find('body')
    if not target_el:
        target_el = soup
        
    # Clean up related ads, newsletter forms, social share bars, and navigation widgets
    el_copy = BeautifulSoup(str(target_el), "html.parser")
    for widget in el_copy.find_all(class_=lambda v: v and any(x in v.lower() for x in ["ad-wrapper", "newsletter", "social-share", "navigation", "footer-card"])):
        widget.decompose()
        
    content_lines = []
    # Extract paragraphs and subheadings
    for child in el_copy.find_all(['h2', 'h3', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li']):
        if child.find_parent(['blockquote', 'pre', 'li', 'ul', 'ol']):
            continue
            
        text = child.get_text().strip()
        if not text:
            continue
            
        tag = child.name
        if tag == 'h2':
            content_lines.append(f"## {text}\n")
        elif tag == 'h3':
            content_lines.append(f"### {text}\n")
        elif tag == 'blockquote':
            content_lines.append(f"> {text}\n")
        elif tag == 'pre':
            content_lines.append(f"\n```\n{text}\n```\n")
        elif tag in ['ul', 'ol']:
            for li in child.find_all('li', recursive=False):
                content_lines.append(f"* {li.get_text().strip()}")
            content_lines.append("")
        elif tag == 'li':
            content_lines.append(f"* {text}")
        elif tag == 'p':
            content_lines.append(f"{text}\n")
            
    raw_text = "\n".join(content_lines).strip()
    if not raw_text:
        raw_text = "No article content could be extracted."
        
    final_text = f"Title: {title}\n\n{raw_text}"
    
    return {
        "title": f"Yahoo News: {title}",
        "raw_text": final_text,
        "headings": [{"level": 2, "text": "Article Body"}],
        "paragraphs": content_lines,
        "success": True if raw_text != "No article content could be extracted." else False
    }
