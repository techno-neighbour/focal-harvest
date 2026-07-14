from bs4 import BeautifulSoup
from typing import Dict, Any

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = [
    "stackoverflow.com", 
    "stackexchange.com", 
    "superuser.com", 
    "serverfault.com", 
    "askubuntu.com"
]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Stack Overflow / Stack Exchange Q&A threads."""
    soup = BeautifulSoup(html_text, 'html.parser')
    
    # 1. Extract Question Title
    title_el = soup.find('h1', id='question-header') or soup.find(class_='question-hyperlink')
    title = title_el.get_text().strip() if title_el else "Stack Overflow Thread"
    
    # 2. Extract Question Body Description (preserve code formatting)
    question_area = soup.find('div', id='question')
    question_body = ""
    if question_area:
        post_body = question_area.find(class_='js-post-body')
        if post_body:
            question_body = _clean_post_content(post_body)
            
    # 3. Extract Answers
    answers = []
    answer_elements = soup.find_all('div', class_='answer')
    
    for ans in answer_elements:
        # Get vote count score
        vote_el = ans.find(class_='js-vote-count')
        score = vote_el.get('data-value') or vote_el.get_text().strip() if vote_el else "0"
        
        # Check if this is the accepted answer (indicators are present on all answers but hidden with d-none on non-accepted ones)
        indicator = ans.find(class_='js-accepted-answer-indicator')
        is_accepted = "accepted-answer" in ans.get("class", []) or (indicator is not None and "d-none" not in indicator.get("class", []))
        
        # Extract answer body
        body_el = ans.find(class_='js-post-body')
        if not body_el:
            continue
        answer_text = _clean_post_content(body_el)
        
        answers.append({
            "score": int(score) if score.replace('-', '').isdigit() else 0,
            "is_accepted": is_accepted,
            "text": answer_text
        })
        
    # Sort answers: Accepted Answer first, then by vote score descending
    answers.sort(key=lambda x: (x["is_accepted"], x["score"]), reverse=True)
    
    # 4. Compile raw text report representation
    formatted_answers = []
    for idx, ans in enumerate(answers):
        status = " [ACCEPTED ANSWER]" if ans["is_accepted"] else ""
        formatted_answers.append(
            f"### Answer {idx + 1}{status} (Score: {ans['score']})\n\n"
            f"{ans['text']}\n"
            f"---"
        )
        
    raw_text = (
        f"Question: {title}\n\n"
        f"## Question Details\n\n"
        f"{question_body}\n\n"
        f"## Answers ({len(answers)} total)\n\n" + 
        "\n\n".join(formatted_answers)
    )
    
    return {
        "title": f"Stack Overflow: {title}",
        "raw_text": raw_text,
        "headings": [
            {"level": 2, "text": "Question Details"}, 
            {"level": 2, "text": f"Answers ({len(answers)})"}
        ],
        "paragraphs": [question_body] + [a["text"] for a in answers],
        "success": True
    }

def _clean_post_content(post_body_el) -> str:
    """Helper to convert HTML posts to Markdown, preserving code blocks exactly."""
    # Convert code blocks (<pre><code>) to Markdown Fenced Code Blocks (```)
    for pre in post_body_el.find_all('pre'):
        code_tag = pre.find('code')
        code_content = code_tag.get_text() if code_tag else pre.get_text()
        
        # Strip trailing newlines and wrap in markdown code fence
        fenced_code = f"\n```\n{code_content.strip()}\n```\n"
        pre.replace_with(fenced_code)
        
    # Convert inline code blocks (<code>) to `code`
    for code in post_body_el.find_all('code'):
        # Only handle if not already inside a pre block
        if code.parent and code.parent.name != 'pre':
            code.replace_with(f"`{code.get_text().strip()}`")
            
    # Return cleaned body text representation
    return post_body_el.get_text().strip()
