import urllib.parse
import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["sec.gov"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for SEC EDGAR company filings (10-K, 10-Q, 8-K)."""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # 1. Extract Title
    # Typically, filings have a document title in <title> or in the header text
    title = soup.title.string.strip() if soup.title else "SEC Filing"
    
    # Clean up title suffixes
    for suffix in [" - SEC", " | SEC"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()
            
    # 2. Extract Document Content
    # Filings are typically giant documents, so we want to process the text paragraphs and format tables
    content_lines = []
    
    # Identify and clean up page boundaries, TOC links, and empty formatting spacers
    for element in soup.find_all(['p', 'table', 'h1', 'h2', 'h3', 'h4', 'h5']):
        # If it is a table, format it cleanly to Markdown
        if element.name == 'table':
            # Skip small formatting tables or layout grids (look for multiple rows and cells)
            rows = element.find_all('tr')
            if len(rows) > 1:
                md_table = _parse_html_table_to_markdown(element)
                if md_table:
                    content_lines.append(f"\n{md_table}\n")
            continue
            
        text = element.get_text().strip()
        if not text:
            continue
            
        # Clean up repeated hyphens, underscores, or page page number separators
        if re.match(r'^[_\-\s\.\d]+$', text) or len(text) < 4:
            continue
            
        tag = element.name
        if tag.startswith('h'):
            level = int(tag[1])
            content_lines.append(f"\n##{ '#' * (level-1) } {text}\n")
        else:
            # Check if this paragraph looks like a filing item heading (e.g., "Item 1. Business" or "Item 7. MD&A")
            is_item_heading = re.match(r'^Item\s+\d+[A-Z]?\s*\.?-?\s+[A-Za-z\s]+', text, re.IGNORECASE)
            if is_item_heading and len(text) < 80:
                content_lines.append(f"\n## {text}\n")
            else:
                content_lines.append(f"{text}\n")
                
    raw_text = "\n".join(content_lines).strip()
    
    # Truncate text if it is incredibly long to fit safely within reasonable token/file limits
    # Most 10-Ks can be several hundred KB, we will keep up to 100,000 characters of text
    max_len = 100000
    if len(raw_text) > max_len:
        raw_text = raw_text[:max_len] + "\n\n... [Filing content truncated for length] ..."
        
    if not raw_text or raw_text.startswith("..."):
        raw_text = "No readable filing content could be extracted."
        
    return {
        "title": f"SEC EDGAR: {title}",
        "raw_text": f"Filing URL: {url}\n\n{raw_text}",
        "headings": [{"level": 2, "text": "Filing Content"}],
        "paragraphs": content_lines[:200],  # Keep a sample of paragraphs for structured output
        "success": True if raw_text != "No readable filing content could be extracted." else False
    }

def _parse_html_table_to_markdown(table_soup: BeautifulSoup) -> str:
    """Converts a BeautifulSoup table into a formatted Markdown table."""
    rows = table_soup.find_all('tr')
    md_rows = []
    max_cols = 0
    
    for r in rows:
        # Extract row cells
        cells = r.find_all(['td', 'th'])
        cols = [c.get_text().strip().replace("\n", " ").replace("|", "\\|") for c in cells]
        
        # Filter out empty spacer cells or styling artifacts
        cols = [c for c in cols if c]
        if cols:
            max_cols = max(max_cols, len(cols))
            md_rows.append(cols)
            
    if not md_rows:
        return ""
        
    # Reconstruct formatted Markdown table lines
    lines = []
    # Header Row
    headers = md_rows[0]
    # pad headers if short
    if len(headers) < max_cols:
        headers += [""] * (max_cols - len(headers))
    lines.append("| " + " | ".join(headers) + " |")
    
    # Separator Row
    lines.append("| " + " | ".join(["---"] * max_cols) + " |")
    
    # Data Rows
    for row in md_rows[1:]:
        if len(row) < max_cols:
            row += [""] * (max_cols - len(row))
        lines.append("| " + " | ".join(row) + " |")
        
    return "\n".join(lines)
