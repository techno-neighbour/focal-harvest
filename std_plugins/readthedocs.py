import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["readthedocs.io"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for ReadTheDocs Sphinx/MkDocs documentation sites."""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # 1. Extract Title
    title_el = soup.find('h1') or soup.find('title')
    title = title_el.get_text().strip() if title_el else "Documentation Page"
    
    # Remove documentation suffixes
    for suffix in [" — Documentation", " - Read the Docs"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()
            
    # 2. Locate the main documentation body container
    # Sphinx/MkDocs standard layouts use specific roles and classes
    body_container = (
        soup.find(role="main") or 
        soup.find(class_="document") or 
        soup.find(class_="body") or 
        soup.find(class_="rst-content")
    )
    
    target_el = body_container if body_container else soup.find('body')
    if not target_el:
        target_el = soup
        
    # 3. Clean up navigation sidebars, breadcrumbs, search bars, and headers
    el_copy = BeautifulSoup(str(target_el), "html.parser")
    
    # Decompose common documentation navigation structures
    nav_selectors = [
        "nav", 
        ".wy-nav-side", 
        ".sphinxsidebar", 
        ".toctree-wrapper",  # TOC trees
        ".rst-breadcrumbs",  # Breadcrumb trails
        ".rst-sidebar", 
        "#sidebar",
        ".headerlink"        # Paragraph permalink paragraph symbols (¶)
    ]
    for sel in nav_selectors:
        for match in el_copy.select(sel):
            match.decompose()
            
    # 4. Extract content and format as Markdown
    content_lines = []
    
    # Sphinx admonitions (Note, Warning) require formatting
    for admonition in el_copy.find_all(class_=lambda v: v and 'admonition' in v):
        title_el = admonition.find(class_='admonition-title')
        admonition_title = title_el.get_text().strip() if title_el else "Note"
        # Extract body text without the title
        if title_el:
            title_el.decompose()
        admonition_text = admonition.get_text().strip()
        # Re-write the admonition content block
        admonition.clear()
        admonition.name = 'blockquote'
        admonition.string = f"**{admonition_title}**: {admonition_text}"
        
    # Query semantic body elements
    for child in el_copy.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li']):
        # Ignore elements nested inside larger blocks we already parse
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
            # Extract code language from parent classes if possible
            lang = "python"  # Default fallback
            parent = child.parent
            if parent and parent.name == 'div':
                cls = "".join(parent.get('class', []))
                if 'highlight-' in cls:
                    lang = cls.split('highlight-')[1].split(' ')[0]
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
        raw_text = "No documentation content could be extracted."
        
    final_text = f"Title: {title}\n\n{raw_text}"
    
    return {
        "title": f"Documentation: {title}",
        "raw_text": final_text,
        "headings": [{"level": 2, "text": "Content"}],
        "paragraphs": content_lines,
        "success": True if raw_text != "No documentation content could be extracted." else False
    }
