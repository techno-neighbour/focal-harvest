import copy
import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup
import utils

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["github.com"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for GitHub repository pages, issues, listings, trees, and code blobs."""
    soup = BeautifulSoup(html_text, "html.parser")
    parsed_url = urllib.parse.urlparse(url)
    
    # Extract path segments, removing empty strings
    path_parts = [p for p in parsed_url.path.strip("/").split("/") if p]
    
    if len(path_parts) >= 2:
        owner = path_parts[0]
        repo = path_parts[1]
        
        # 1. Repository Home Page (/{owner}/{repo})
        if len(path_parts) == 2:
            return _parse_repo_home(soup, url, owner, repo)
            
        elif len(path_parts) >= 3:
            mode = path_parts[2].lower()
            
            # 2. Blob Page (File View)
            if mode == "blob" and len(path_parts) >= 5:
                branch = path_parts[3]
                filepath = "/".join(path_parts[4:])
                return _parse_blob(soup, url, owner, repo, branch, filepath)
                
            # 3. Tree Page (Directory View)
            elif mode == "tree" and len(path_parts) >= 4:
                branch = path_parts[3]
                subpath = "/".join(path_parts[4:]) if len(path_parts) >= 5 else ""
                return _parse_tree(soup, url, owner, repo, branch, subpath)
                
            # 4. Issues & Discussions Thread
            elif len(path_parts) >= 4 and mode in ["issues", "discussions"]:
                thread_id = path_parts[3]
                return _parse_thread(soup, url, owner, repo, mode, thread_id)
                
            # 5. Issues & Discussions Listing
            elif len(path_parts) == 3 and mode in ["issues", "discussions"]:
                return _parse_listing(soup, url, owner, repo, mode)
            
    # Fallback default response
    return {
        "title": "GitHub Page",
        "raw_text": f"Unsupported GitHub page layout for URL: {url}",
        "headings": [],
        "paragraphs": [],
        "success": False,
        "error": "Unsupported GitHub page layout"
    }

def _format_element_markdown(soup_el) -> str:
    """Helper to convert HTML code elements inside a comment to Markdown format."""
    if not soup_el:
        return ""
    # Clone element to avoid modifying the original tree
    el = BeautifulSoup(str(soup_el), "html.parser")
    
    # Format code blocks (pre + code)
    for pre in el.find_all('pre'):
        code = pre.find('code')
        code_text = code.get_text() if code else pre.get_text()
        pre.replace_with(f"\n```\n{code_text.strip()}\n```\n")
        
    # Format inline code
    for code in el.find_all('code'):
        if not code.find_parent('pre'):
            code.replace_with(f"`{code.get_text().strip()}`")
            
    return el.get_text().strip()

def _parse_repo_home(soup: BeautifulSoup, url: str, owner: str, repo: str) -> Dict[str, Any]:
    # Extract About Description
    about_desc = ""
    f4_els = soup.find_all(class_=lambda v: v and "f4" in v)
    for el in f4_els:
        txt = el.get_text().strip()
        if len(txt) > 0 and "navigation" not in txt.lower() and "sign in" not in txt.lower() and len(txt) < 500:
            about_desc = txt
            break
            
    # Extract README
    readme_el = soup.find(class_="markdown-body")
    readme_text = _format_element_markdown(readme_el) if readme_el else "No README file found."
    
    # Extract files list if present (Box-row or react-directory-row)
    files_lines = []
    file_rows = soup.find_all(class_=lambda v: v and ("Box-row" in v or "react-directory-row" in v or "js-navigation-item" in v or "react-directory-filename-column" in v))
    for r in file_rows:
        if r.find(class_=lambda v: v and ("IssueLabel" in v or "js-issue-row" in v)):
            continue
        link = r.find('a', href=True)
        if link:
            name = link.get_text().strip()
            if name and not any(k in name.lower() for k in ["parent directory", "sign in", "fork", "star", "watch"]):
                files_lines.append(f"- {name}")
                
    deduped_files = []
    for f in files_lines:
        if f not in deduped_files:
            deduped_files.append(f)
            
    files_section = "\n".join(deduped_files[:20])
    
    raw_text = (
        f"Repository: {owner}/{repo}\n"
        f"Description: {about_desc}\n\n"
        f"Files:\n{files_section}\n\n"
        f"README:\n{readme_text}"
    )
    
    return {
        "title": f"GitHub Repository: {owner}/{repo}",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Files"}, {"level": 2, "text": "README"}],
        "paragraphs": [about_desc, files_section, readme_text],
        "success": True
    }

def _parse_blob(soup: BeautifulSoup, url: str, owner: str, repo: str, branch: str, filepath: str) -> Dict[str, Any]:
    # Strategy 1: Attempt to fetch the raw file contents directly from raw.githubusercontent.com
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filepath}"
    try:
        response = utils.safe_request("GET", raw_url, timeout=10)
        if response.status_code == 200:
            content_text = response.text
            raw_text = (
                f"File: {filepath} ({owner}/{repo})\n"
                f"Branch: {branch}\n\n"
                f"Content:\n```\n{content_text}\n```"
            )
            return {
                "title": f"GitHub File: {filepath} in {owner}/{repo}",
                "raw_text": raw_text,
                "headings": [{"level": 2, "text": "Content"}],
                "paragraphs": [content_text],
                "success": True
            }
    except Exception:
        pass
        
    # Strategy 2: Fallback to parsing HTML blob page (useful for private repositories with cookies or rate limits)
    # Check if this is a rendered markdown/text file (uses markdown-body class)
    readme_el = soup.find(class_="markdown-body")
    if readme_el:
        content_text = _format_element_markdown(readme_el)
    else:
        # Code line containers
        lines = [el.get_text() for el in soup.find_all(class_=lambda v: v and "blob-code" in v)]
        if lines:
            content_text = "\n".join(lines)
        else:
            # General textarea raw fallback
            textarea = soup.find('textarea', id="read-only-cursor-text-area") or soup.find('textarea')
            content_text = textarea.get_text().strip() if textarea else soup.get_text().strip()
            
    raw_text = (
        f"File: {filepath} ({owner}/{repo})\n"
        f"Branch: {branch}\n\n"
        f"Content:\n```\n{content_text}\n```"
    )
    return {
        "title": f"GitHub File: {filepath} in {owner}/{repo}",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Content"}],
        "paragraphs": [content_text],
        "success": True
    }

def _parse_tree(soup: BeautifulSoup, url: str, owner: str, repo: str, branch: str, subpath: str) -> Dict[str, Any]:
    # Extract directory files listing (similar to repo home page)
    files_lines = []
    file_rows = soup.find_all(class_=lambda v: v and ("Box-row" in v or "react-directory-row" in v or "js-navigation-item" in v or "react-directory-filename-column" in v))
    for r in file_rows:
        link = r.find('a', href=True)
        if link:
            name = link.get_text().strip()
            if name and not any(k in name.lower() for k in ["parent directory", "sign in", "fork", "star", "watch"]):
                files_lines.append(f"- {name}")
                
    deduped_files = []
    for f in files_lines:
        if f not in deduped_files:
            deduped_files.append(f)
            
    files_section = "\n".join(deduped_files[:30])
    
    # Subdirectories sometimes contain a README folder overview
    readme_el = soup.find(class_="markdown-body")
    readme_text = _format_element_markdown(readme_el) if readme_el else ""
    
    raw_text = (
        f"Repository: {owner}/{repo}\n"
        f"Directory: {subpath} (branch: {branch})\n\n"
        f"Files:\n{files_section}"
    )
    if readme_text:
        raw_text += f"\n\nREADME:\n{readme_text}"
        
    return {
        "title": f"GitHub Directory: {subpath} in {owner}/{repo} ({branch})",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Files"}] + ([{"level": 2, "text": "README"}] if readme_text else []),
        "paragraphs": [files_section] + ([readme_text] if readme_text else []),
        "success": True
    }

def _parse_thread(soup: BeautifulSoup, url: str, owner: str, repo: str, mode: str, thread_id: str) -> Dict[str, Any]:
    # Extract Title
    title_el = soup.find(class_="js-issue-title") or soup.find(class_="gh-header-title")
    title = title_el.get_text().strip() if title_el else (soup.title.string.strip() if soup.title else f"GitHub {mode.capitalize()} #{thread_id}")
    
    # Extract Main original post description
    comments_elements = soup.find_all(class_="comment-body")
    
    selftext = ""
    if comments_elements:
        selftext = _format_element_markdown(comments_elements[0])
        other_comments = comments_elements[1:]
    else:
        other_comments = []
        
    # Extract post author
    author_el = soup.find('a', class_=lambda v: v and 'author' in v) or soup.find('a', attrs={"data-hovercard-type": "user"})
    author = author_el.get_text().strip() if author_el else "unknown"
    
    # Extract comments timeline
    comments_lines = []
    timeline_items = soup.find_all(class_=lambda v: v and ("timeline-comment-group" in v or "TimelineItem" in v or "js-comment-container" in v))
    
    if timeline_items:
        for idx, item in enumerate(timeline_items):
            body_el = item.find(class_="comment-body")
            if not body_el:
                continue
                
            body_text = _format_element_markdown(body_el)
            if body_text == selftext:
                continue # Skip original post body
                
            c_author_el = item.find('a', class_=lambda v: v and 'author' in v) or item.find('a', attrs={"data-hovercard-type": "user"})
            c_author = c_author_el.get_text().strip() if c_author_el else "unknown"
            
            clean_body = body_text.replace("\n", " ")
            comments_lines.append(f"* **@{c_author}**: {clean_body}")
    else:
        # Fallback to direct comments mapping if layout is customized/simplified
        for idx, c in enumerate(other_comments):
            body_text = _format_element_markdown(c).replace("\n", " ")
            comments_lines.append(f"* **@commenter_{idx+1}**: {body_text}")
            
    raw_text = (
        f"Repository: {owner}/{repo}\n"
        f"Title: {title} (#{thread_id})\n"
        f"Posted by: @{author}\n\n"
        f"Original Post:\n{selftext}\n\n"
        f"Comments:\n" + "\n".join(comments_lines)
    )
    
    return {
        "title": f"GitHub {mode[:-1].capitalize()}: {title} in {owner}/{repo}",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Original Post"}, {"level": 2, "text": "Comments"}],
        "paragraphs": [selftext] + comments_lines,
        "success": True
    }

def _parse_listing(soup: BeautifulSoup, url: str, owner: str, repo: str, mode: str) -> Dict[str, Any]:
    # Look for issue rows (Box-row or js-issue-row)
    rows = soup.find_all(class_=lambda v: v and ("Box-row" in v or "js-issue-row" in v or "discussion-list-item" in v))
    
    posts_lines = []
    for r in rows:
        title_a = r.find('a', class_=lambda v: v and ("markdown-title" in v or "js-navigation-open" in v)) or r.find('a', href=True)
        if not title_a:
            continue
            
        title = title_a.get_text().strip()
        href = title_a.get('href', '')
        if href.startswith("/"):
            href = urllib.parse.urljoin("https://github.com", href)
            
        # Try to find labels / tags
        labels = [el.get_text().strip() for el in r.find_all(class_=lambda v: v and ("IssueLabel" in v or "label" in v))]
        labels_str = f" [{', '.join(labels)}]" if labels else ""
        
        # Try to find author
        author_el = r.find('a', class_=lambda v: v and 'author' in v) or r.find('a', attrs={"data-hovercard-type": "user"})
        author = author_el.get_text().strip() if author_el else "unknown"
        
        # Try to find comments count
        comments_el = r.find('a', attrs={"aria-label": lambda val: val and "comment" in val}) or r.find(class_="octicon-comment")
        comments_cnt = "0 comments"
        if comments_el:
            comments_cnt = comments_el.get_text().strip() + " comments"
            
        posts_lines.append(
            f"* **{title}**{labels_str}\n"
            f"  Posted by: @{author}\n"
            f"  Link: {href}\n"
            f"  Status: {comments_cnt}\n"
        )
        
    if not posts_lines:
        # Fallback list item parsing from standard links
        links = soup.find_all('a', href=lambda val: val and (f"/{mode}/" in val or val.endswith(f"/{mode}")))
        for l in links[:20]:
            title = l.get_text().strip()
            href = l.get('href')
            if href.startswith("/"):
                href = urllib.parse.urljoin("https://github.com", href)
            if title:
                posts_lines.append(f"* **{title}**\n  Link: {href}\n")
                
    raw_text = f"GitHub {mode.capitalize()} Listing for {owner}/{repo}:\n\n" + "\n".join(posts_lines)
    return {
        "title": f"GitHub {mode.capitalize()} Listing: {owner}/{repo}",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": f"GitHub {mode.capitalize()} Listing"}],
        "paragraphs": posts_lines,
        "success": True
    }
