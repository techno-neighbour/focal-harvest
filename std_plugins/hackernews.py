from bs4 import BeautifulSoup
from typing import Dict, Any
import urllib.parse

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["news.ycombinator.com"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for news.ycombinator.com (handles both individual item threads and list feeds)."""
    soup = BeautifulSoup(html_text, 'html.parser')
    parsed_url = urllib.parse.urlparse(url)
    
    # Identify if the URL is a single thread (contains item or has query id) or a list feed (e.g. /shownew, /newest)
    if "item" in parsed_url.path or "id=" in parsed_url.query:
        return parse_thread(soup)
    else:
        return parse_listing(soup, parsed_url.path)

def parse_thread(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extracts hierarchical comment tree from a Hacker News thread."""
    title_span = soup.find('span', class_='titleline')
    title = title_span.get_text().strip() if title_span else "Hacker News Thread"
    
    comments = []
    comment_rows = soup.find_all('tr', class_='comtr')
    
    for row in comment_rows:
        user_el = row.find('a', class_='hnuser')
        username = user_el.text.strip() if user_el else "anonymous"
        
        body_el = row.find('div', class_='comment')
        if not body_el:
            continue
            
        reply_div = body_el.find('div', class_='reply')
        if reply_div:
            reply_div.decompose()
        comment_text = body_el.get_text().strip()
        
        ind_img = row.find('img', src='s.gif')
        width = int(ind_img.get('width', 0)) if ind_img else 0
        indent_level = width // 40
        
        indent_str = "    " * indent_level
        comments.append(f"{indent_str}* **@{username}**: {comment_text}")

    raw_text = f"Hacker News Thread: {title}\n\nDiscussion:\n" + "\n".join(comments)
    
    return {
        "title": f"Hacker News: {title}",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Discussion Thread"}],
        "paragraphs": comments
    }

def parse_listing(soup: BeautifulSoup, path: str) -> Dict[str, Any]:
    """Extracts submissions, links, scores, and comments from listing pages (like /shownew)."""
    clean_path = path.strip("/")
    page_name = clean_path.upper() if clean_path else "HOME"
    title = f"Hacker News - {page_name}"
    
    posts = []
    athing_rows = soup.find_all('tr', class_='athing')
    
    for row in athing_rows:
        title_line = row.find('span', class_='titleline')
        if not title_line:
            continue
            
        link_el = title_line.find('a')
        post_title = title_line.get_text().strip()
        post_url = link_el.get('href') if link_el else ""
        
        # Pull subtext data (points, submitter, and comments link) from the next sibling row
        points = "0 points"
        comments_info = "0 comments"
        subtext_row = row.find_next_sibling('tr')
        if subtext_row:
            score_el = subtext_row.find('span', class_='score')
            if score_el:
                points = score_el.get_text().strip()
                
            links = subtext_row.find_all('a')
            for link in links:
                text = link.get_text()
                if "comment" in text or "discuss" in text:
                    comments_info = text.strip()
                    break
                    
        posts.append(f"* **{post_title}**\n  * Link: {post_url}\n  * Stats: {points} | {comments_info}")
        
    raw_text = f"Hacker News Listing Page: {page_name}\n\nSubmissions:\n" + "\n".join(posts)
    
    return {
        "title": title,
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Submissions"}],
        "paragraphs": posts
    }
