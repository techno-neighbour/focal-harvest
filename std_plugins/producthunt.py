import urllib.parse
import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["producthunt.com"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Product Hunt launch posts."""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # 1. Extract Product Name
    title_el = soup.find('h1') or soup.find(class_=lambda v: v and 'title' in v.lower())
    title = title_el.get_text().strip() if title_el else ""
    if not title:
        title = soup.title.string.strip() if soup.title else "Product Hunt Post"
        
    # Clean title suffix
    for suffix in [" - Product Hunt", " | Product Hunt"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()
            
    # 2. Extract Upvote Count
    upvotes = "0 upvotes"
    # Find any elements containing upvote counts
    upvote_el = soup.find(lambda tag: tag.name in ['button', 'span', 'div'] and 'upvote' in tag.get_text().lower())
    if upvote_el:
        upvote_text = upvote_el.get_text().strip()
        match = re.search(r'(\d+[\d,]*)\s*(?:upvote|vote)', upvote_text, re.IGNORECASE)
        if match:
            upvotes = f"{match.group(1)} upvotes"
        elif len(upvote_text) < 15:
            # Fallback direct text if it's just the number
            upvotes = f"{upvote_text} upvotes"
            
    # 3. Extract Tagline / Subtitle
    tagline = ""
    # Look for subheadings or paragraphs near h1
    tagline_el = soup.find(class_=lambda v: v and any(x in v.lower() for x in ['tagline', 'description', 'subtitle']))
    if tagline_el and tagline_el.name != 'h1':
        tagline = tagline_el.get_text().strip()
        
    # 4. Extract Launch Description
    desc_lines = []
    # Query paragraphs describing the product
    body_container = soup.find(class_=lambda v: v and any(x in v.lower() for x in ['styles_description', 'body-text', 'post-content']))
    target_body = body_container if body_container else soup.find('body')
    
    if target_body:
        for p in target_body.find_all('p'):
            txt = p.get_text().strip()
            # Skip short links or navigation text
            if len(txt) > 20 and not any(x in txt.lower() for x in ["upvote", "share", "embed", "comment", "sign in"]):
                desc_lines.append(txt)
                
    description = "\n\n".join(desc_lines)
    
    # 5. Extract Comments / Feedback discussion
    comments = []
    comment_blocks = soup.find_all(class_=lambda v: v and any(x in v.lower() for x in ['comment__content', 'styles_comment', 'comment-text']))
    for block in comment_blocks[:10]:  # Keep top 10 comments
        author_el = block.find_previous(class_=lambda v: v and any(x in v.lower() for x in ['author-name', 'user-name', 'styles_username']))
        author = author_el.get_text().strip() if author_el else "User"
        
        comment_text = block.get_text().strip()
        if comment_text and len(comment_text) > 10:
            # Deduplicate nested comments
            formatted_comment = f"* **{author}**: \"{comment_text}\""
            if formatted_comment not in comments:
                comments.append(formatted_comment)
                
    comments_section = "\n".join(comments)
    
    raw_text = (
        f"Product: {title}\n"
        f"Stats: {upvotes}\n"
    )
    if tagline:
        raw_text += f"Tagline: {tagline}\n"
    raw_text += (
        f"\nDescription:\n{description}\n\n"
        f"Discussion & Comments:\n{comments_section}"
    )
    
    return {
        "title": f"Product Hunt: {title}",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Description"}, {"level": 2, "text": "Discussion & Comments"}],
        "paragraphs": desc_lines + comments,
        "success": True if description or comments else False
    }
