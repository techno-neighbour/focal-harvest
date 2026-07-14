import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["pubmed.ncbi.nlm.nih.gov"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for PubMed abstract pages and search result listings."""
    soup = BeautifulSoup(html_text, "html.parser")
    parsed_url = urllib.parse.urlparse(url)
    
    # Extract path segments, removing empty strings
    path_parts = [p for p in parsed_url.path.strip("/").split("/") if p]
    
    # Check if this is an abstract details page (contains a numeric PMID segment)
    is_abstract = False
    pmid = ""
    for segment in path_parts:
        if segment.isdigit():
            is_abstract = True
            pmid = segment
            break
            
    if is_abstract:
        return _parse_abstract(soup, url, pmid)
    else:
        # Search page or other listing format (check query parameters or root)
        return _parse_search_listing(soup, url)

def _parse_abstract(soup: BeautifulSoup, url: str, pmid: str) -> Dict[str, Any]:
    # Extract Title
    title_el = soup.find('h1', class_='heading-title') or soup.find('h1', class_='title')
    title = title_el.get_text().strip() if title_el else ""
    if not title:
        title = soup.title.string.strip() if soup.title else f"PubMed Article {pmid}"
        
    # Extract Authors
    authors_el = soup.find('div', class_='authors-list') or soup.find(class_='authors')
    authors = ""
    if authors_el:
        # Extract all full-name links
        names = [a.get_text().strip() for a in authors_el.find_all('a', class_='full-name')]
        if names:
            authors = ", ".join(names)
        else:
            # Fallback text extract
            authors = authors_el.get_text().strip()
            
    # Extract Abstract
    abstract_el = soup.find('div', class_='abstract-content') or soup.find(id='eng-abstract') or soup.find(class_='abstract')
    abstract_text = ""
    if abstract_el:
        # Paragraphs within abstract
        paras = abstract_el.find_all('p')
        if paras:
            abstract_text = "\n\n".join([p.get_text().strip() for p in paras])
        else:
            abstract_text = abstract_el.get_text().strip()
            
    # Extract Affiliations
    affiliations_el = soup.find('div', class_='affiliations') or soup.find(class_='affiliations-list')
    affiliations = ""
    if affiliations_el:
        # Format affiliations as bullet list
        items = []
        for li in affiliations_el.find_all('li'):
            # Decompose label sub elements if any
            for sup in li.find_all('sup'):
                sup.decompose()
            items.append(f"- {li.get_text().strip()}")
        affiliations = "\n".join(items) if items else affiliations_el.get_text().strip()
        
    # Extract DOI
    doi = "unknown"
    doi_a = soup.find('a', attrs={"data-ga-action": "DOI"})
    if doi_a:
        doi = doi_a.get_text().strip()
    else:
        # Fallback to citation line parsing
        doi_el = soup.find(class_='cit') or soup.find(class_='cit-doi')
        if doi_el:
            doi_text = doi_el.get_text()
            if "doi" in doi_text.lower():
                parts = doi_text.split("doi:")
                if len(parts) > 1:
                    doi = parts[1].strip().split(" ")[0].rstrip(".")
                
    raw_text = (
        f"Title: {title}\n"
        f"Authors: {authors}\n"
        f"PMID: {pmid} | DOI: {doi}\n\n"
        f"Affiliations:\n{affiliations}\n\n"
        f"Abstract:\n{abstract_text}"
    )
    
    return {
        "title": f"PubMed Abstract: {title} (PMID: {pmid})",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Affiliations"}, {"level": 2, "text": "Abstract"}],
        "paragraphs": [authors, affiliations, abstract_text],
        "success": True
    }

def _parse_search_listing(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    # Look for search result blocks (doc-sum)
    rows = soup.find_all(class_='doc-sum')
    
    results_lines = []
    for r in rows:
        title_a = r.find('a', class_='doc-sum-title')
        title = title_a.get_text().strip() if title_a else "Untitled"
        href = title_a.get('href', '').strip() if title_a else ""
        if href.startswith("/"):
            href = urllib.parse.urljoin("https://pubmed.ncbi.nlm.nih.gov", href)
            
        # Try to find authors
        authors_el = r.find(class_='doc-sum-authors')
        authors = authors_el.get_text().strip() if authors_el else "unknown"
        
        # Try to find snippet/abstract excerpt
        snippet_el = r.find(class_='doc-sum-snippet')
        snippet = snippet_el.get_text().strip() if snippet_el else ""
        
        # Try to find PMID from link or metadata
        pmid_el = r.find(class_='doc-sum-pmid')
        pmid = pmid_el.get_text().strip() if pmid_el else "unknown"
        
        results_lines.append(
            f"* **{title}** (PMID: {pmid})\n"
            f"  Authors: {authors}\n"
            f"  Link: {href}\n"
            f"  Snippet: {snippet}\n"
        )
        
    if not results_lines:
        # Fallback to general anchors matching digit URLs
        links = soup.find_all('a', href=lambda val: val and val.strip("/").isdigit())
        for l in links[:20]:
            title = l.get_text().strip()
            href = urllib.parse.urljoin("https://pubmed.ncbi.nlm.nih.gov", l.get('href'))
            pmid = l.get('href').strip("/")
            if title:
                results_lines.append(f"* **{title}** (PMID: {pmid})\n  Link: {href}\n")
                
    raw_text = "PubMed Search Results Listing:\n\n" + "\n".join(results_lines)
    return {
        "title": "PubMed Search Results Listing",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "PubMed Search Results Listing"}],
        "paragraphs": results_lines,
        "success": True
    }
