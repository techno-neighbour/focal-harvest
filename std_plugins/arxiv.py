import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["arxiv.org"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for arXiv abstracts and search result listings."""
    soup = BeautifulSoup(html_text, "html.parser")
    parsed_url = urllib.parse.urlparse(url)
    
    # Extract path segments, removing empty strings
    path_parts = [p for p in parsed_url.path.strip("/").split("/") if p]
    
    if len(path_parts) >= 2 and path_parts[0] == "abs":
        paper_id = path_parts[1]
        return _parse_abstract(soup, url, paper_id)
        
    elif len(path_parts) >= 1 and (path_parts[0] in ["search", "list"] or parsed_url.query):
        return _parse_search_listing(soup, url)
        
    # Fallback to general page parsing
    title = soup.title.string.strip() if soup.title else "arXiv Page"
    body_text = soup.get_text()
    return {
        "title": title,
        "raw_text": body_text,
        "headings": [],
        "paragraphs": [body_text],
        "success": True
    }

def _parse_abstract(soup: BeautifulSoup, url: str, paper_id: str) -> Dict[str, Any]:
    # Extract Title
    title_el = soup.find('h1', class_='title')
    title = ""
    if title_el:
        # Remove descriptor tag if present
        desc_span = title_el.find('span', class_='descriptor')
        if desc_span:
            desc_span.decompose()
        title = title_el.get_text().strip()
    if not title:
        title = soup.title.string.strip() if soup.title else f"arXiv Paper {paper_id}"
        
    # Extract Authors
    authors_el = soup.find('div', class_='authors')
    authors = ""
    if authors_el:
        desc_span = authors_el.find('span', class_='descriptor')
        if desc_span:
            desc_span.decompose()
        authors = ", ".join([a.get_text().strip() for a in authors_el.find_all('a')])
        if not authors:
            authors = authors_el.get_text().strip()
            
    # Extract Abstract
    abstract_el = soup.find('blockquote', class_='abstract')
    abstract = ""
    if abstract_el:
        desc_span = abstract_el.find('span', class_='descriptor')
        if desc_span:
            desc_span.decompose()
        abstract = abstract_el.get_text().strip()
        
    # Extract Dateline (Submission Date)
    date_el = soup.find(class_='dateline')
    date_str = date_el.get_text().strip(" \t\n\r[]") if date_el else "unknown"
    
    # Extract Subjects
    subjects_el = soup.find('td', class_='subjects')
    subjects = subjects_el.get_text().strip() if subjects_el else "unknown"
    
    # Reconstruct PDF link
    pdf_url = f"https://arxiv.org/pdf/{paper_id}"
    
    raw_text = (
        f"Title: {title}\n"
        f"Authors: {authors}\n"
        f"Date: {date_str}\n"
        f"Subjects: {subjects}\n"
        f"PDF Link: {pdf_url}\n\n"
        f"Abstract:\n{abstract}"
    )
    
    return {
        "title": f"arXiv Abstract: {title} ({paper_id})",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Abstract"}],
        "paragraphs": [authors, date_str, subjects, abstract],
        "success": True
    }

def _parse_search_listing(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    rows = soup.find_all(class_='arxiv-result')
    
    results_lines = []
    for r in rows:
        # Title
        title_el = r.find(class_='title')
        title = title_el.get_text().strip() if title_el else "Untitled"
        
        # Link & ID
        link_el = r.find(class_='list-title')
        link_a = link_el.find('a') if link_el else None
        paper_url = link_a.get('href', '').strip() if link_a else ""
        paper_id = link_a.get_text().strip() if link_a else "unknown"
        
        # PDF Link
        pdf_a = None
        if link_el:
            pdf_a = link_el.find('a', href=lambda val: val and '/pdf/' in val)
        pdf_url = pdf_a.get('href', '').strip() if pdf_a else ""
        if pdf_url.startswith("/"):
            pdf_url = urllib.parse.urljoin("https://arxiv.org", pdf_url)
            
        # Authors
        authors_el = r.find(class_='authors')
        authors = ""
        if authors_el:
            desc_span = authors_el.find('span', class_='descriptor') or authors_el.find('span')
            # Extract links if any
            a_links = authors_el.find_all('a')
            if a_links:
                authors = ", ".join([a.get_text().strip() for a in a_links])
            else:
                txt = authors_el.get_text().strip()
                if desc_span and txt.startswith(desc_span.get_text()):
                    txt = txt[len(desc_span.get_text()):].strip()
                authors = txt
                
        # Abstract
        abstract_el = r.find(class_='abstract')
        abstract = ""
        if abstract_el:
            # Look for full abstract first
            full_span = abstract_el.find(class_='abstract-full')
            short_span = abstract_el.find(class_='abstract-short')
            target_el = full_span or short_span or abstract_el
            
            # Decompose less/more links
            for link in target_el.find_all('a'):
                link.decompose()
            # Decompose abstract label
            desc_span = target_el.find('span')
            if desc_span and "abstract" in desc_span.get_text().lower():
                desc_span.decompose()
                
            abstract = target_el.get_text().strip(" \t\n\r:")
            
        results_lines.append(
            f"* **{title}**\n"
            f"  Authors: {authors}\n"
            f"  Link: {paper_url} | PDF: {pdf_url}\n"
            f"  Abstract: {abstract}\n"
        )
        
    if not results_lines:
        # Fallback to parsing standard article titles
        links = soup.find_all('a', href=lambda val: val and '/abs/' in val)
        for l in links[:20]:
            title = l.get_text().strip()
            href = urllib.parse.urljoin("https://arxiv.org", l.get('href'))
            results_lines.append(f"* **{title}**\n  Link: {href}\n")
            
    raw_text = "arXiv Search Results Listing:\n\n" + "\n".join(results_lines)
    return {
        "title": "arXiv Search Results Listing",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "arXiv Search Results Listing"}],
        "paragraphs": results_lines,
        "success": True
    }
