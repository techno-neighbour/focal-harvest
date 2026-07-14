import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["medium.com"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Medium articles."""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # 1. Locate the main article container
    article_container = soup.find('article')
    
    # If no article tag is found, fallback to the entire page body
    target_el = article_container if article_container else soup.find('body')
    if not target_el:
        target_el = soup
        
    # 2. Extract Title
    title_el = None
    if article_container:
        title_el = article_container.find('h1')
    if not title_el:
        title_el = soup.find('h1')
        
    title = title_el.get_text().strip() if title_el else ""
    if not title:
        title = soup.title.string.strip() if soup.title else "Medium Article"
        
    # Remove " - Medium" or similar suffixes from title if present
    for suffix in [" - Medium", " | Medium"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()
            
    # 3. Clean up newsletter popups, related posts, and modal wrappers inside the target element
    # Clone the target element to avoid modifying the main parsed tree
    el_copy = BeautifulSoup(str(target_el), "html.parser")
    
    # Decompose common overlays, popups, and footer suggestions
    for element in el_copy.find_all(class_=lambda v: v and any(x in v.lower() for x in ["signup", "subscribe", "related", "newsletter", "popover", "modal", "overlay"])):
        element.decompose()
        
    # 4. Extract content blocks and format as Markdown
    content_lines = []
    # Query semantic body elements
    for child in el_copy.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li']):
        # Ignore elements that are part of other parsed containers to prevent duplication
        if child.find_parent(['blockquote', 'pre', 'li', 'ul', 'ol']):
            continue
            
        text = child.get_text().strip()
        if not text:
            continue
            
        tag = child.name
        if tag == 'h1' and text != title:
            content_lines.append(f"# {text}\n")
        elif tag == 'h2':
            content_lines.append(f"## {text}\n")
        elif tag in ['h3', 'h4']:
            content_lines.append(f"### {text}\n")
        elif tag == 'blockquote':
            content_lines.append(f"> {text}\n")
        elif tag == 'pre':
            content_lines.append(f"\n```\n{text}\n```\n")
        elif tag in ['ul', 'ol']:
            # Extract bullet points
            for li in child.find_all('li', recursive=False):
                content_lines.append(f"* {li.get_text().strip()}")
            content_lines.append("")
        elif tag == 'li':
            content_lines.append(f"* {text}")
        elif tag == 'p':
            # Skip short links or navigation text
            if len(text) > 10 and not any(x in text.lower() for x in ["sign in", "sign up", "terms of service", "privacy policy"]):
                content_lines.append(f"{text}\n")
                
    raw_text = "\n".join(content_lines).strip()
    if not raw_text:
        raw_text = "No article content could be extracted."
        
    return {
        "title": f"Medium Article: {title}",
        "raw_text": f"Title: {title}\n\n{raw_text}",
        "headings": [{"level": 2, "text": "Content"}],
        "paragraphs": content_lines,
        "success": True
    }
