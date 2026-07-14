import json
import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup
import utils

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["reddit.com", "www.reddit.com", "old.reddit.com"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Reddit threads and listings utilizing the public .json endpoint shortcut with HTML fallback."""
    # Ensure we append .json cleanly to the URL path
    parsed_url = urllib.parse.urlparse(url)
    json_path = parsed_url.path.rstrip("/") + ".json"
    json_url = urllib.parse.urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        json_path,
        parsed_url.params,
        parsed_url.query,
        parsed_url.fragment
    ))

    # Fetch structured data directly, bypassing obfuscated HTML DOMs
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = utils.safe_request("GET", json_url, headers=headers, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Reddit API returned status code {response.status_code}")
        
        data = response.json()
        
        # 1. Parse thread page JSON response
        if isinstance(data, list) and len(data) >= 2:
            post_data = data[0].get("data", {}).get("children", [{}])[0].get("data", {})
            comments_data = data[1].get("data", {}).get("children", [])
            
            title = post_data.get("title", "Reddit Thread")
            author = post_data.get("author", "unknown")
            subreddit = post_data.get("subreddit_name_prefixed", "r/unknown")
            selftext = post_data.get("selftext", "")
            
            # Parse nested comments recursively
            comments_lines = []
            _extract_comments_json(comments_data, comments_lines, depth=0)
            
            raw_text = (
                f"Subreddit: {subreddit}\n"
                f"Title: {title}\n"
                f"Posted by: @{author}\n\n"
                f"Original Post:\n{selftext}\n\n"
                f"Comments:\n" + "\n".join(comments_lines)
            )
            
            return {
                "title": f"Reddit: {title} ({subreddit})",
                "raw_text": raw_text,
                "headings": [{"level": 2, "text": "Original Post"}, {"level": 2, "text": "Comments"}],
                "paragraphs": [selftext] + comments_lines,
                "success": True
            }
            
        # 2. Parse listing page JSON response
        elif isinstance(data, dict) and data.get("kind") == "Listing":
            children = data.get("data", {}).get("children", [])
            posts_lines = []
            for child in children:
                p_data = child.get("data", {})
                title = p_data.get("title", "No Title")
                url_dest = p_data.get("url", "")
                if url_dest.startswith("/"):
                    url_dest = urllib.parse.urljoin("https://reddit.com", url_dest)
                author = p_data.get("author", "unknown")
                score = p_data.get("score", 0)
                num_comments = p_data.get("num_comments", 0)
                sub = p_data.get("subreddit_name_prefixed", "r/unknown")
                
                posts_lines.append(
                    f"* **{title}**\n"
                    f"  Subreddit: {sub} | Posted by: @{author}\n"
                    f"  Link: {url_dest}\n"
                    f"  Score: {score} | Comments: {num_comments}\n"
                )
                
            raw_text = f"Reddit Listing:\n\n" + "\n".join(posts_lines)
            return {
                "title": f"Reddit Listing: {url}",
                "raw_text": raw_text,
                "headings": [{"level": 2, "text": "Reddit Listing"}],
                "paragraphs": posts_lines,
                "success": True
            }
            
    except Exception as e:
        # JSON fetch failed, attempt parsing passed HTML directly (e.g. if we fetched Wayback's old.reddit.com or www.reddit.com)
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # Fallback 1: Thread page HTML (old.reddit.com layout format)
        commentarea = soup.find('div', class_='commentarea')
        if commentarea:
            title_el = soup.find('a', class_='title') or soup.find('h1')
            title = title_el.get_text().strip() if title_el else "Reddit Thread"
            
            sub_el = soup.find('span', class_='reddit-textbox') or soup.find('a', class_='subreddit')
            subreddit = sub_el.get_text().strip() if sub_el else "r/unknown"
            
            post_author_el = soup.find('p', class_='tagline')
            author = "unknown"
            if post_author_el:
                author_a = post_author_el.find('a', class_='author')
                if author_a:
                    author = author_a.get_text().strip()
                    
            expando = soup.find('div', class_='expando')
            selftext = ""
            if expando:
                s_body = expando.find('div', class_='usertext-body')
                if s_body:
                    selftext = s_body.get_text().strip()
            
            comments_lines = []
            sitetable = commentarea.find('div', class_='sitetable', recursive=False)
            if not sitetable:
                sitetable = commentarea
                
            top_comments = sitetable.find_all('div', class_='comment', recursive=False)
            for c in top_comments:
                _extract_comments_html(c, comments_lines, depth=0)
                
            raw_text = (
                f"Subreddit: {subreddit}\n"
                f"Title: {title}\n"
                f"Posted by: @{author}\n\n"
                f"Original Post:\n{selftext}\n\n"
                f"Comments:\n" + "\n".join(comments_lines)
            )
            
            return {
                "title": f"Reddit: {title} ({subreddit})",
                "raw_text": raw_text,
                "headings": [{"level": 2, "text": "Original Post"}, {"level": 2, "text": "Comments"}],
                "paragraphs": [selftext] + comments_lines,
                "success": True
            }

        # Fallback 2: Thread page HTML (www.reddit.com Redesign layout format)
        comment_elements = soup.find_all(attrs={"data-testid": "comment"})
        if comment_elements:
            title_el = soup.find('h1') or soup.find('a', class_='title')
            title = title_el.get_text().strip() if title_el else "Reddit Thread"
            
            subreddit = "r/unknown"
            sub_a = soup.find('a', href=lambda val: val and val.startswith('/r/'))
            if sub_a:
                subreddit = sub_a.get_text().strip()
                
            post_author_a = soup.find('a', href=lambda val: val and val.startswith('/user/'))
            author = "unknown"
            if post_author_a:
                parts = post_author_a['href'].split('/')
                if len(parts) >= 3:
                    author = parts[2]
            
            post_body_el = soup.find(attrs={"data-click-id": "text"}) or soup.find(attrs={"data-testid": "post-container"})
            selftext = ""
            if post_body_el:
                selftext = "\n".join([p.get_text().strip() for p in post_body_el.find_all('p')])
                
            comments_lines = []
            for c in comment_elements:
                parent_el = c.find_parent(attrs={"id": lambda val: val and val.startswith("t1_")})
                if not parent_el:
                    parent_el = c.parent.parent.parent
                    
                author_link = parent_el.find('a', href=lambda val: val and val.startswith('/user/')) if parent_el else None
                author_name = "unknown"
                if author_link:
                    parts = author_link['href'].split('/')
                    if len(parts) >= 3:
                        author_name = parts[2]
                        
                padding_style = parent_el.get('style', '') if parent_el else ''
                depth = 0
                if 'padding-left' in padding_style:
                    try:
                        pixels = int(''.join(filter(str.isdigit, padding_style)))
                        depth = pixels // 16
                    except Exception:
                        depth = 0
                        
                clean_body = c.get_text().strip().replace('\n', ' ')
                indent = "    " * depth
                comments_lines.append(f"{indent}* **@{author_name}**: {clean_body}")
                
            raw_text = (
                f"Subreddit: {subreddit}\n"
                f"Title: {title}\n"
                f"Posted by: @{author}\n\n"
                f"Original Post:\n{selftext}\n\n"
                f"Comments:\n" + "\n".join(comments_lines)
            )
            
            return {
                "title": f"Reddit: {title} ({subreddit})",
                "raw_text": raw_text,
                "headings": [{"level": 2, "text": "Original Post"}, {"level": 2, "text": "Comments"}],
                "paragraphs": [selftext] + comments_lines,
                "success": True
            }

        # Fallback 3: Subreddit/listing page HTML parsing
        link_elements = soup.find_all('div', class_='link')
        if link_elements:
            posts_lines = []
            for p in link_elements:
                title_a = p.find('a', class_='title')
                if not title_a:
                    continue
                title = title_a.get_text().strip()
                href = title_a.get('href', '')
                if href.startswith("/"):
                    href = urllib.parse.urljoin("https://reddit.com", href)
                    
                author_a = p.find('a', class_='author')
                author = author_a.get_text().strip() if author_a else "unknown"
                
                score_el = p.find(class_='score')
                score = score_el.get_text().strip() if score_el else "0"
                
                comments_a = p.find('a', class_='comments')
                comments_text = comments_a.get_text().strip() if comments_a else "0 comments"
                
                posts_lines.append(
                    f"* **{title}**\n"
                    f"  Posted by: @{author}\n"
                    f"  Link: {href}\n"
                    f"  Score: {score} | {comments_text}\n"
                )
                
            raw_text = f"Reddit Listing:\n\n" + "\n".join(posts_lines)
            return {
                "title": f"Reddit Listing: {url}",
                "raw_text": raw_text,
                "headings": [{"level": 2, "text": "Reddit Listing"}],
                "paragraphs": posts_lines,
                "success": True
            }

        return {
            "title": "Reddit Thread",
            "raw_text": f"Failed to retrieve Reddit JSON feed: {str(e)}",
            "headings": [],
            "paragraphs": [],
            "success": False,
            "error": str(e)
        }

    return {
        "title": "Reddit Feed",
        "raw_text": "Unsupported Reddit layout page.",
        "headings": [],
        "paragraphs": [],
        "success": False,
        "error": "Unsupported Reddit layout page"
    }

def _extract_comments_json(children: List[Dict[str, Any]], output_lines: List[str], depth: int):
    """Recursively walks the JSON replies tree to create indented comment bullet points."""
    for child in children:
        if child.get("kind") != "t1":  # t1 denotes comment records
            continue
        
        c_data = child.get("data", {})
        author = c_data.get("author", "deleted")
        body = c_data.get("body", "[empty]")
        
        # Skip moderator automated comments to reduce token counts
        if c_data.get("distinguished") == "moderator" or "automoderator" in author.lower():
            continue
            
        indent = "    " * depth
        clean_body = body.replace("\n", " ")
        output_lines.append(f"{indent}* **@{author}**: {clean_body}")
        
        # Process replies
        replies = c_data.get("replies")
        if isinstance(replies, dict):
            reply_children = replies.get("data", {}).get("children", [])
            _extract_comments_json(reply_children, output_lines, depth + 1)

def _extract_comments_html(parent_el, output_lines: List[str], depth: int):
    """Recursively walks the HTML DOM tree to create indented comment bullet points from old.reddit.com."""
    author = parent_el.get('data-author') or "unknown"
    body_el = parent_el.find('div', class_='usertext-body')
    md_el = body_el.find('div', class_='md') if body_el else None
    body = md_el.get_text().strip() if md_el else (body_el.get_text().strip() if body_el else "[empty]")
    
    # Skip moderator automated comments to reduce token counts
    if "automoderator" in author.lower():
        return
        
    clean_body = body.replace("\n", " ")
    indent = "    " * depth
    output_lines.append(f"{indent}* **@{author}**: {clean_body}")
    
    # Process nested replies
    child_div = parent_el.find('div', class_='child', recursive=False)
    if child_div:
        sitetable = child_div.find('div', class_='sitetable', recursive=False)
        if sitetable:
            comment_divs = sitetable.find_all('div', class_='comment', recursive=False)
            for c in comment_divs:
                _extract_comments_html(c, output_lines, depth + 1)
