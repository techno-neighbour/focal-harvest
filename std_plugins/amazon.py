import urllib.parse
import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin (covering major regional Amazon sites)
SUPPORTED_DOMAINS = [
    "amazon.com", "amazon.co.uk", "amazon.ca", "amazon.de", 
    "amazon.fr", "amazon.it", "amazon.es", "amazon.in", 
    "amazon.co.jp", "amazon.com.mx", "amazon.com.br"
]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Amazon product pages and search listings."""
    soup = BeautifulSoup(html_text, "html.parser")
    parsed_url = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    # Route based on URL structure
    if "/dp/" in parsed_url.path or "/gp/product/" in parsed_url.path:
        return _parse_product_details(soup, url)
    else:
        # Default to search results listing
        return _parse_search_listing(soup, url)

def _parse_product_details(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    # 1. Extract Product Title
    title_el = soup.find(id="productTitle")
    title = title_el.get_text().strip() if title_el else "Amazon Product"
    
    # 2. Extract Price
    price = "unknown"
    # Try different price containers used by Amazon's dynamic templates
    price_el = (
        soup.find(class_="apexPriceToPay") or 
        soup.find(class_="a-price") or 
        soup.find(id="priceblock_ourprice") or
        soup.find(id="priceblock_dealprice")
    )
    if price_el:
        offscreen = price_el.find(class_="a-offscreen")
        if offscreen:
            price = offscreen.get_text().strip()
        else:
            price = price_el.get_text().strip()
    # Normalize price spacing
    price = re.sub(r'\s+', '', price)
    
    # 3. Extract Rating and Reviews
    rating = "No rating"
    rating_el = soup.find(class_=lambda v: v and 'a-star-' in v) or soup.find(id="acrPopover")
    if rating_el:
        # Try getting rating value from title attribute
        title_attr = rating_el.get('title', '')
        if title_attr:
            rating = title_attr.strip()
        else:
            rating = rating_el.get_text().strip()
            
    reviews = "0 reviews"
    reviews_el = soup.find(id="acrCustomerReviewText")
    if reviews_el:
        reviews = reviews_el.get_text().strip()
        
    # 4. Extract Key Feature Bullets
    bullets = []
    bullets_container = soup.find(id="feature-bullets") or soup.find(class_="a-unordered-list")
    if bullets_container:
        for li in bullets_container.find_all('li'):
            # Ignore sub elements or layout helpers
            if not li.find(class_="a-list-item"):
                txt = li.get_text().strip()
            else:
                txt = li.find(class_="a-list-item").get_text().strip()
            if txt and "make sure this fits" not in txt.lower():
                bullets.append(f"* {txt}")
                
    bullets_text = "\n".join(bullets)
    
    # 5. Extract Tech Specs Table
    specs = {}
    
    # Try prodDetails table first
    prod_details = soup.find(id="prodDetails") or soup.find(id="detailBullets_feature_div")
    if prod_details:
        for tr in prod_details.find_all('tr'):
            tds = tr.find_all(['td', 'th'])
            if len(tds) == 2:
                k = tds[0].get_text().strip()
                v = tds[1].get_text().strip()
                if k and v:
                    # Clean spacing inside values
                    specs[k] = re.sub(r'\s+', ' ', v)
        # Try bulleted spec list fallback
        if not specs:
            for li in prod_details.find_all('li'):
                span_keys = li.find_all('span', class_='a-text-bold')
                if span_keys:
                    k = span_keys[0].get_text().strip().rstrip(':')
                    # Value is usually the remaining text in the list item
                    v = li.get_text().replace(span_keys[0].get_text(), "").strip()
                    if k and v:
                        specs[k] = re.sub(r'\s+', ' ', v)
                        
    # Build specs Markdown table
    specs_lines = []
    if specs:
        specs_lines.append("| Specification | Detail |")
        specs_lines.append("| --- | --- |")
        for k, v in specs.items():
            clean_k = k.replace("|", "\\|")
            clean_v = v.replace("|", "\\|")
            specs_lines.append(f"| {clean_k} | {clean_v} |")
            
    specs_table = "\n".join(specs_lines)
    
    raw_text = (
        f"Product: {title}\n"
        f"Price: {price} | Rating: {rating} ({reviews})\n\n"
        f"Key Features:\n{bullets_text}\n\n"
        f"Specifications:\n{specs_table}"
    )
    
    return {
        "title": f"Amazon Product: {title}",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Key Features"}, {"level": 2, "text": "Specifications"}],
        "paragraphs": [f"Price: {price}", bullets_text, specs_table],
        "success": True if price != "unknown" or bullets else False
    }

def _parse_search_listing(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    # Find all search result items
    rows = soup.find_all(attrs={"data-component-type": "s-search-result"})
    
    results_lines = []
    for r in rows:
        # Title
        title_a = r.find('a', class_=lambda v: v and 'a-link-normal' in v and 'a-text-normal' in v)
        title = title_a.get_text().strip() if title_a else "Untitled Product"
        href = title_a.get('href', '').strip() if title_a else ""
        if href.startswith("/"):
            href = urllib.parse.urljoin("https://www.amazon.com", href)
            
        # Price
        price = "unknown"
        price_whole = r.find(class_="a-price-whole")
        price_fraction = r.find(class_="a-price-fraction")
        if price_whole:
            frac = price_fraction.get_text().strip() if price_fraction else "00"
            price = f"${price_whole.get_text().strip().rstrip('.')}.{frac}"
            
        # Rating
        rating = "No rating"
        rating_el = r.find(class_=lambda v: v and 'a-star-' in v)
        if rating_el:
            title_attr = rating_el.get('title', '')
            if title_attr:
                rating = title_attr.strip()
                
        results_lines.append(
            f"* **{title}**\n"
            f"  Price: {price} | Rating: {rating}\n"
            f"  Link: {href}\n"
        )
        
    raw_text = "Amazon Search Results:\n\n" + "\n".join(results_lines)
    return {
        "title": "Amazon Search Results",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Search Results"}],
        "paragraphs": results_lines,
        "success": True if results_lines else False
    }
