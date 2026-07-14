import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["dev.to"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Dev.to blog articles."""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # 1. Extract Title
    title_el = soup.find('h1') or soup.find(class_='crayons-article__title')
    title = title_el.get_text().strip() if title_el else ""
    if not title:
        title = soup.title.string.strip() if soup.title else "Dev.to Article"
        
    # Remove Dev.to branding suffixes from title
    for suffix in [" - DEV Community", " | DEV Community"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()
            
    # 2. Extract Author
    author = "unknown"
    author_el = soup.find(class_=lambda v: v and any(x in v for x in ['author-name', 'spec-author-name'])) or soup.find(attrs={"data-testid": "author-name"})
    if author_el:
        author = author_el.get_text().strip()
        
    # 3. Locate the main article content container
    # Dev.to Forem platform wraps the story body in ID "article-body" or class "crayons-article__body"
    body_container = (
        soup.find(id="article-body") or 
        soup.find(class_="crayons-article__body") or 
        soup.find("article")
    )
    
    target_el = body_container if body_container else soup.find('body')
    if not target_el:
        target_el = soup
        
    # 4. Clean up reaction bars, social floating panels, ads, and related listings
    el_copy = BeautifulSoup(str(target_el), "html.parser")
    
    boilerplate_selectors = [
        ".crayons-article__reactions",
        ".crayons-article__comments",
        ".crayons-story__reactions",
        ".comments-container",
        "form",
        "button",
        "#comments"
    ]
    for sel in boilerplate_selectors:
        for match in el_copy.select(sel):
            match.decompose()
            
    # 5. Extract content and format as Markdown
    content_lines = []
    
    for child in el_copy.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li']):
        # Skip nested tags inside elements we already process
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
            # Resolve code language from crayons highlight class
            lang = "python"
            cls = "".join(child.get('class', []))
            if 'highlight' in cls:
                # Often crayons pre highlights code language inside inner classes
                code_el = child.find('code')
                if code_el:
                    code_cls = "".join(code_el.get('class', []))
                    if 'language-' in code_cls:
                        lang = code_cls.split('language-')[1].split(' ')[0]
            content_lines.append(f"\n```{lang}\n{text}\n```\n")
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
        
    final_text = f"Title: {title}\nAuthor: {author}\n\n{raw_text}"
    
    return {
        "title": f"Dev.to: {title}",
        "raw_text": final_text,
        "headings": [{"level": 2, "text": "Content"}],
        "paragraphs": content_lines,
        "success": True if raw_text != "No article content could be extracted." else False
    }
