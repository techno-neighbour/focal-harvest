import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["wikipedia.org"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Wikipedia articles."""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # 1. Extract Title
    title_el = soup.find('h1', id='firstHeading') or soup.find('h1')
    title = title_el.get_text().strip() if title_el else ""
    if not title:
        title = soup.title.string.strip() if soup.title else "Wikipedia Article"
        
    # Remove " - Wikipedia" suffix from title if present
    for suffix in [" - Wikipedia", " | Wikipedia"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()
            
    # 2. Locate main content parser output div
    parser_output = soup.find(class_="mw-parser-output")
    target_el = parser_output if parser_output else soup.find(id="bodyContent")
    if not target_el:
        target_el = soup.find('body') or soup
        
    # 3. Clean up boilerplate, edit links, citation links, TOC, and hatnotes
    # Clone the target element to avoid modifying the main soup tree
    el_copy = BeautifulSoup(str(target_el), "html.parser")
    
    # Decompose edit buttons
    for edit_sec in el_copy.find_all(class_="mw-editsection"):
        edit_sec.decompose()
        
    # Decompose reference superscript links (e.g. [1], [2])
    for ref in el_copy.find_all(class_="reference"):
        ref.decompose()
        
    # Decompose Table of Contents (TOC)
    for toc in el_copy.find_all(class_=lambda v: v and any(x in v.lower() for x in ["toc", "table-of-contents"])):
        toc.decompose()
        
    # Decompose hatnotes / disambiguation notices
    for hatnote in el_copy.find_all(class_=lambda v: v and any(x in v.lower() for x in ["hatnote", "disambig", "navigation-not-search"])):
        hatnote.decompose()
        
    # Decompose navigation tables / infoboxes to keep article prose clean
    for nav_table in el_copy.find_all(class_=lambda v: v and any(x in v.lower() for x in ["infobox", "navbox", "metadata", "ambox"])):
        nav_table.decompose()
        
    # 4. Extract content blocks and format as Markdown
    content_lines = []
    
    # Query semantic headers, paragraphs, and list blocks
    for child in el_copy.find_all(['h2', 'h3', 'h4', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li']):
        # Ignore nested items inside parent blocks we already parse
        if child.find_parent(['blockquote', 'pre', 'li', 'ul', 'ol']):
            continue
            
        text = child.get_text().strip()
        if not text:
            continue
            
        tag = child.name
        if tag == 'h2':
            # Remove reference/external link section titles if they start appearing
            if any(x in text.lower() for x in ["references", "external links", "see also", "further reading"]):
                # Skip subsequent sections if we've reached references/links
                continue
            content_lines.append(f"## {text}\n")
        elif tag == 'h3':
            content_lines.append(f"### {text}\n")
        elif tag == 'h4':
            content_lines.append(f"#### {text}\n")
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
        "title": f"Wikipedia: {title}",
        "raw_text": final_text,
        "headings": [{"level": 2, "text": "Overview"}],
        "paragraphs": content_lines,
        "success": True
    }
