import urllib.parse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

# Define the domains intercepted by this plugin
SUPPORTED_DOMAINS = ["quora.com"]

def parse(html_text: str, url: str) -> Dict[str, Any]:
    """Custom parser for Quora Q&A pages."""
    # Quora share trick: appending ?share=1 allows full page render without modals
    parsed_url = urllib.parse.urlparse(url)
    if "share=1" not in parsed_url.query:
        query_params = urllib.parse.parse_qs(parsed_url.query)
        query_params["share"] = ["1"]
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        # Update URL for user visibility if needed
        url = urllib.parse.urlunparse(parsed_url._replace(query=new_query))

    soup = BeautifulSoup(html_text, "html.parser")
    
    # 1. Extract Question Title
    question_el = (
        soup.find('h1') or 
        soup.find(class_=lambda v: v and any(x in v.lower() for x in ['question_text', 'inline_editor_value', 'q-title']))
    )
    question = question_el.get_text().strip() if question_el else ""
    if not question:
        # Fallback to page title
        question = soup.title.string.strip() if soup.title else "Quora Question"
        
    for suffix in [" - Quora", " | Quora"]:
        if question.endswith(suffix):
            question = question[:-len(suffix)].strip()
            
    # 2. Extract Answers
    # Quora wraps answers in answer cards, often marked with classes containing 'Answer' or in list items
    answers_data = []
    
    # Try finding elements with Quora's specific box classes or answer layout structures
    answer_blocks = soup.find_all(class_=lambda v: v and any(x in v for x in ['answer_content', 'AnswerCard', 'pagedlist_item']))
    if not answer_blocks:
        # Fallback search for general answer containers
        answer_blocks = soup.find_all('div', class_=lambda v: v and 'q-box' in v and any(x in str(v) for x in ['answer', 'Answer']))
        
    for idx, block in enumerate(answer_blocks):
        # Extract Author Details
        author = "Anonymous"
        author_a = block.find('a', href=lambda val: val and '/profile/' in val) or block.find(class_=lambda v: v and 'user-name' in v.lower())
        if author_a:
            author = author_a.get_text().strip()
            
        credential = ""
        cred_el = block.find(class_=lambda v: v and any(x in v.lower() for x in ['credential', 'profile-credential', 'about-author']))
        if cred_el:
            credential = cred_el.get_text().strip()
            
        # Extract Answer body paragraphs
        paras = []
        body_el = block.find(class_=lambda v: v and any(x in v for x in ['answer_text', 'ExpandedAnswer', 'q-text']))
        if body_el:
            p_tags = body_el.find_all(['p', 'span', 'li'])
            if p_tags:
                for p in p_tags:
                    txt = p.get_text().strip()
                    # Skip duplicate text if nested
                    if txt and not any(txt in existing for existing in paras):
                        paras.append(txt)
            else:
                txt = body_el.get_text().strip()
                if txt:
                    paras.append(txt)
        else:
            # Fallback direct child text extraction
            for p in block.find_all('p'):
                txt = p.get_text().strip()
                if txt:
                    paras.append(txt)
                    
        answer_text = "\n\n".join(paras).strip()
        if answer_text:
            cred_str = f" ({credential})" if credential else ""
            answers_data.append({
                "author": author,
                "credential": credential,
                "text": answer_text,
                "formatted": f"### Answer by {author}{cred_str}\n{answer_text}\n"
            })
            
    # Format the complete output document
    formatted_answers = []
    for item in answers_data:
        # Deduplicate answers to prevent double counting from nested class containers
        if item["formatted"] not in formatted_answers:
            formatted_answers.append(item["formatted"])
            
    raw_text = f"Question: {question}\n\n"
    success = True
    if formatted_answers:
        raw_text += "\n---\n\n".join(formatted_answers)
    else:
        raw_text += "No answers could be extracted."
        success = False
        
    return {
        "title": f"Quora: {question}",
        "raw_text": raw_text,
        "headings": [{"level": 2, "text": "Answers"}],
        "paragraphs": [item["text"] for item in answers_data],
        "success": success
    }
