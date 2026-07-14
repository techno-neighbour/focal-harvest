import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["scholar.google.com"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Google Scholar searches and author profiles."""
    soup = BeautifulSoup(html_text, "html.parser")
    parsed_url = urllib.parse.urlparse(url)
    
    # Check url path to route
    path = parsed_url.path.strip("/")
    
    if "citations" in path:
        return _parse_author_profile(soup, url)
    else:
        # Defaults to search results listing
        return _parse_search_listing(soup, url)

def _parse_search_listing(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    # Find all search result containers
    rows = soup.find_all(class_=lambda v: v and "gs_r" in v and "gs_or" in v)
    
    results_lines = []
    for r in rows:
        # Title
        title_el = r.find(class_='gs_rt')
        title = "Untitled"
        href = ""
        if title_el:
            title = title_el.get_text().strip()
            # If title contains metadata labels like [PDF] or [HTML]
            a_tag = title_el.find('a', href=True)
            if a_tag:
                href = a_tag.get('href', '').strip()
                
        # Authors & Venue info
        author_el = r.find(class_='gs_a')
        authors_venue = author_el.get_text().strip() if author_el else "unknown"
        
        # Excerpt
        snippet_el = r.find(class_='gs_rs')
        snippet = snippet_el.get_text().strip() if snippet_el else ""
        
        # PDF/Sidebar Link
        pdf_url = ""
        sidebar_el = r.find(class_='gs_or_ggside')
        if sidebar_el:
            pdf_a = sidebar_el.find('a', href=True)
            if pdf_a:
                pdf_url = pdf_a.get('href', '').strip()
                
        # Citations
        citations = "0 citations"
        fl_el = r.find(class_='gs_fl')
        if fl_el:
            cite_a = fl_el.find('a', string=lambda t: t and 'Cited by' in t)
            if cite_a:
                citations = cite_a.get_text().strip()
                
        # Build line item
        pdf_str = f" | PDF: {pdf_url}" if pdf_url else ""
        results_lines.append(
            f"* **{title}**\n"
            f"  Metadata: {authors_venue}\n"
            f"  Link: {href}{pdf_str}\n"
            f"  Snippet: {snippet}\n"
            f"  Status: {citations}\n"
        )
        
    if not results_lines:
        # Fallback parsing
        links = soup.find_all('a', href=lambda val: val and '/scholar?cites=' in val)
        for l in links[:20]:
            title = l.get_text().strip()
            href = urllib.parse.urljoin("https://scholar.google.com", l.get('href'))
            results_lines.append(f"* **{title}**\n  Link: {href}\n")
            
    raw_text = "Google Scholar Search Results:\n\n" + "\n".join(results_lines)
    return {
        "title": "Google Scholar Search Results",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Google Scholar Search Results"}],
        "paragraphs": results_lines,
        "success": True
    }

def _parse_author_profile(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    # Extract Author Info
    name_el = soup.find(id='gsc_prf_in')
    name = name_el.get_text().strip() if name_el else "Unknown Scholar"
    
    aff_els = soup.find_all(class_='gsc_prf_il')
    affiliations = ", ".join([el.get_text().strip() for el in aff_els if el.get_text().strip() and "homepage" not in el.get_text().lower()])
    
    # Extract metrics table if present
    metrics_lines = []
    metrics_table = soup.find(id='gsc_rsb_table')
    if metrics_table:
        headers = [th.get_text().strip() for th in metrics_table.find_all('th')]
        for tr in metrics_table.find_all('tr')[1:]:
            tds = [td.get_text().strip() for td in tr.find_all('td')]
            if len(tds) >= 2:
                label = tds[0]
                val = tds[1]
                metrics_lines.append(f"- {label}: {val}")
                
    metrics_section = "\n".join(metrics_lines)
    
    # Extract Publications list
    pubs_lines = []
    pub_rows = soup.find_all(class_='gsc_a_tr')
    for r in pub_rows:
        title_a = r.find(class_='gsc_a_at')
        title = title_a.get_text().strip() if title_a else "Untitled"
        href = title_a.get('href', '').strip() if title_a else ""
        if href.startswith("/"):
            href = urllib.parse.urljoin("https://scholar.google.com", href)
            
        # Gray text metadata blocks
        grays = r.find_all(class_='gs_gray')
        authors = grays[0].get_text().strip() if len(grays) > 0 else "unknown"
        journal = grays[1].get_text().strip() if len(grays) > 1 else "unknown"
        
        # Citations
        cite_a = r.find(class_='gsc_a_ac')
        citations = cite_a.get_text().strip() if cite_a else "0"
        
        # Year
        year_el = r.find(class_='gsc_a_h')
        year = year_el.get_text().strip() if year_el else ""
        
        year_str = f" ({year})" if year else ""
        pubs_lines.append(
            f"* **{title}**{year_str}\n"
            f"  Authors: {authors}\n"
            f"  Journal: {journal}\n"
            f"  Link: {href}\n"
            f"  Citations: {citations}\n"
        )
        
    pubs_section = "\n".join(pubs_lines)
    
    raw_text = (
        f"Scholar Profile: {name}\n"
        f"Affiliation: {affiliations}\n\n"
        f"Metrics:\n{metrics_section}\n\n"
        f"Publications:\n{pubs_section}"
    )
    
    return {
        "title": f"Google Scholar Profile: {name}",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Metrics"}, {"level": 2, "text": "Publications"}],
        "paragraphs": [affiliations, metrics_section, pubs_section],
        "success": True
    }
