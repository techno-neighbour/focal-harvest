import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["substack.com"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Substack articles/newsletters."""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # 1. Locate the main article container
    # Substack wraps the readable body in class "available-content" or "markup" or inside "article"
    article_container = (
        soup.find(class_="available-content") or 
        soup.find(class_="body markup") or 
        soup.find("article") or 
        soup.find(class_="post-content")
    )
    
    target_el = article_container if article_container else soup.find('body')
    if not target_el:
        target_el = soup
        
    # 2. Extract Title & Subtitle
    title_el = soup.find('h1', class_='post-title') or soup.find('h1', class_='post-header-title') or soup.find('h1')
    title = title_el.get_text().strip() if title_el else ""
    if not title:
        title = soup.title.string.strip() if soup.title else "Substack Newsletter"
        
    subtitle_el = soup.find(class_='subtitle') or soup.find(class_='post-subtitle')
    subtitle = subtitle_el.get_text().strip() if subtitle_el else ""
    
    # 3. Extract Author
    author_el = soup.find(class_='post-author-name') or soup.find(class_='author') or soup.find(attrs={"rel": "author"})
    author = author_el.get_text().strip() if author_el else "unknown"
    
    # 4. Clean up subscription widgets, like panels, share dialogs, and popups
    el_copy = BeautifulSoup(str(target_el), "html.parser")
    
    # Decompose common Substack boilerplate / CTA widgets
    boilerplate_selectors = [
        ".subscription-widget-wrap",
        ".paywall-subscription-widget",
        ".post-ufi",          # Like/comment panel
        ".share-dialog",
        ".button-wrapper",
        ".sidestack",
        ".comments-button",
        ".paywall-teaser",
        "form"                # Subscribe forms
    ]
    for sel in boilerplate_selectors:
        for match in el_copy.select(sel):
            match.decompose()
            
    # Also remove any button elements
    for btn in el_copy.find_all('button'):
        btn.decompose()
        
    # 5. Extract content elements and format as Markdown
    content_lines = []
    for child in el_copy.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li']):
        # Ignore sub elements
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
            for li in child.find_all('li', recursive=False):
                content_lines.append(f"* {li.get_text().strip()}")
            content_lines.append("")
        elif tag == 'li':
            content_lines.append(f"* {text}")
        elif tag == 'p':
            # Skip short links or navigation text
            clean_text = text.lower()
            if len(text) > 10 and not any(x in clean_text for x in ["subscribe", "share", "write a comment", "like this post"]):
                content_lines.append(f"{text}\n")
                
    raw_text = "\n".join(content_lines).strip()
    if not raw_text:
        raw_text = "No article content could be extracted."
        
    final_text = f"Title: {title}\n"
    if subtitle:
        final_text += f"Subtitle: {subtitle}\n"
    final_text += f"Author: {author}\n\n{raw_text}"
    
    return {
        "title": f"Substack: {title}",
        "raw_text": final_text,
        "headings": [{"level": 2, "text": "Content"}],
        "paragraphs": content_lines,
        "success": True
    }
