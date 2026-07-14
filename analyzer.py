import re
import os
import requests
from typing import List, Dict, Any, Set
from collections import Counter
import math
import utils
logger = utils.setup_logging()

# A basic list of stop words to filter out during keyword analysis
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "arent", "as", "at", 
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "cant", "cannot", "could", 
    "couldnt", "did", "didnt", "do", "does", "doesnt", "doing", "dont", "down", "during", "each", "few", "for", "from", 
    "further", "had", "hadnt", "has", "hasnt", "have", "havent", "having", "he", "hed", "hell", "hes", "her", "here", 
    "heres", "hers", "herself", "him", "himself", "his", "how", "hows", "i", "id", "ill", "im", "ive", "if", "in", 
    "into", "is", "isnt", "it", "its", "itself", "lets", "me", "more", "most", "mustnt", "my", "myself", "no", "nor", 
    "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", 
    "same", "shant", "she", "shed", "shell", "shes", "should", "shouldnt", "so", "some", "such", "than", "that", "thats", 
    "the", "their", "theirs", "them", "themselves", "then", "there", "theres", "these", "they", "theyd", "theyll", 
    "theyre", "theyve", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasnt", "we", 
    "wed", "well", "were", "weve", "werent", "what", "whats", "when", "whens", "where", "wheres", "which", "while", 
    "who", "whos", "whom", "why", "whys", "with", "wont", "would", "wouldnt", "you", "youd", "youll", "youre", "youve", 
    "your", "yours", "yourself", "yourselves"
}

def split_into_sentences(text: str) -> List[str]:
    """Splits raw text block into individual sentences using heuristic regex rules."""
    # Handle paragraph endings and common abbreviations
    text = text.replace('\n', ' ')
    sentence_endings = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s')
    sentences = sentence_endings.split(text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]

def extract_keywords(query: str) -> Set[str]:
    """Extracts unique lowercase keywords from a search query or topic, excluding stop words."""
    words = re.findall(r'\b\w+\b', query.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}

def score_sentence(sentence: str, keywords: Set[str], position_weight: float) -> float:
    """Calculates relevance score of a sentence based on keywords and relative placement."""
    words = re.findall(r'\b\w+\b', sentence.lower())
    if not words:
        return 0.0
        
    match_count = sum(1 for w in words if w in keywords)
    unique_matches = len({w for w in words if w in keywords})
    
    if match_count == 0:
        return 0.0
        
    # Density score
    density = match_count / len(words)
    
    # Text length penalty (prefer medium sentences between 12 and 35 words)
    length_penalty = 1.0
    if len(words) < 8:
        length_penalty = 0.5
    elif len(words) > 40:
        length_penalty = 0.7
        
    score = (unique_matches * 2.0 + match_count * 0.5) * density * length_penalty * position_weight
    return score

def generate_local_summary(scraped_data: List[Dict[str, Any]], query: str, spec_topic: str) -> str:
    """
    Performs local, rule-based extractive summarization and outputs a beautiful,
    well-structured Markdown deep dive report.
    """
    keywords = extract_keywords(query) | extract_keywords(spec_topic)
    
    all_sentences_with_meta = []
    
    for doc_idx, doc in enumerate(scraped_data):
        if not doc.get("success") or not doc.get("paragraphs"):
            continue
            
        paragraphs = doc["paragraphs"]
        total_p = len(paragraphs)
        
        for p_idx, p in enumerate(paragraphs):
            sentences = split_into_sentences(p)
            for s_idx, s in enumerate(sentences):
                # Sentences closer to the beginning of the article or paragraph get higher weight
                doc_pos_weight = 1.0 + (1.5 / (p_idx + 1))
                s_pos_weight = 1.0 + (1.0 / (s_idx + 1))
                position_weight = doc_pos_weight * s_pos_weight
                
                score = score_sentence(s, keywords, position_weight)
                if score > 0.05:
                    all_sentences_with_meta.append({
                        "text": s,
                        "score": score,
                        "source_title": doc["title"] or f"Source {doc_idx+1}",
                        "source_url": doc["url"],
                        "doc_index": doc_idx
                    })
                    
    # Sort sentences by score descending
    all_sentences_with_meta.sort(key=lambda x: x["score"], reverse=True)
    
    # Deduplicate sentences (avoid highly similar content)
    unique_sentences = []
    seen_texts = set()
    for s_info in all_sentences_with_meta:
        # Check simple cosine/overlap similarity with already selected sentences
        text_words = set(re.findall(r'\b\w+\b', s_info["text"].lower()))
        is_duplicate = False
        for seen in seen_texts:
            seen_words = set(re.findall(r'\b\w+\b', seen.lower()))
            if not text_words or not seen_words:
                continue
            overlap = len(text_words & seen_words) / min(len(text_words), len(seen_words))
            if overlap > 0.65:
                is_duplicate = True
                break
        if not is_duplicate:
            unique_sentences.append(s_info)
            seen_texts.add(s_info["text"])
            if len(unique_sentences) >= 15: # Grab top 15 key sentences
                break

    # Build Markdown report
    markdown_lines = []
    markdown_lines.append(f"# Deep Dive Report: {query}")
    markdown_lines.append(f"**Focus Area:** {spec_topic}\n")
    markdown_lines.append("## Executive Summary\n")
    
    # Build a coherent executive summary out of the top sentences
    exec_sentences = unique_sentences[:6]
    # Re-sort executive sentences by document index to maintain some source structure
    exec_sentences.sort(key=lambda x: (x["doc_index"], x["text"]))
    
    if exec_sentences:
        for s in exec_sentences:
            markdown_lines.append(f"- {s['text']} *([Source]({s['source_url']}))*")
    else:
        markdown_lines.append("*No highly relevant sentences matching your query could be extracted from the scraped content.*")
        
    markdown_lines.append("\n## Key Insights & Detailed Synthesis\n")
    
    # Group findings by topic or source
    source_sentences = {}
    for s in unique_sentences[6:15]:
        source_title = s["source_title"]
        if source_title not in source_sentences:
            source_sentences[source_title] = []
        source_sentences[source_title].append(s)
        
    if source_sentences:
        for title, s_list in source_sentences.items():
            url = s_list[0]["source_url"]
            markdown_lines.append(f"### Findings from [{title}]({url})")
            for s in s_list:
                markdown_lines.append(f"- {s['text']}")
            markdown_lines.append("")
    else:
        markdown_lines.append("*Refer to sources table below for specific references.*")
        
    # Sources Table
    markdown_lines.append("\n## Sources Scraped\n")
    markdown_lines.append("| No. | Source Title | URL | Status |")
    markdown_lines.append("|---|---|---|---|")
    for idx, doc in enumerate(scraped_data):
        status = "Success" if doc["success"] else f"Failed ({doc.get('error')})"
        title = doc["title"] or f"Source {idx+1}"
        url = doc["url"]
        # Limit title length
        if len(title) > 50:
            title = title[:47] + "..."
        markdown_lines.append(f"| {idx+1} | {title} | [{url}]({url}) | {status} |")
        
    return "\n".join(markdown_lines)

def generate_gemini_summary(scraped_data: List[Dict[str, Any]], query: str, spec_topic: str, api_key: str, raise_on_error: bool = False) -> str:
    """
    Queries Gemini 1.5 Flash using direct HTTP requests to synthesize the scraped text content
    into a gorgeous, highly structured and professional Markdown Deep Dive report.
    """
    context_parts = []
    for idx, doc in enumerate(scraped_data):
        if doc.get("success"):
            text_content = doc.get("raw_text", "")[:4000]
            context_parts.append(f"Source {idx+1}: {doc['title']} ({doc['url']})\nContent:\n{text_content}\n---\n")
            
    context_str = "\n".join(context_parts)
    
    prompt = f"""You are a professional research assistant. Analyze the scraped web content below and generate a deep-dive research report.

User's Original Query: {query}
Specific Information Needed/Focus: {spec_topic}

Scraped Data:
{context_str}

Please synthesize the scraped data to write a detailed, highly structured Markdown report.
Make sure to:
1. Write a professional title and a compelling Executive Summary.
2. Structure the body with clear headings and bullet points answering the user's specific information needs.
3. Cite sources dynamically using Markdown links pointing to the exact source URLs from the Scraped Data.
4. Add a 'Key Takeaways' section.
5. Create a 'Sources Scraped' Markdown table at the end showing the Title and URL of all sources.
6. Write only the Markdown report itself, no wrapping conversational text. Ensure it is clean, comprehensive, and detailed.
"""

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048
        }
    }
    
    try:
        response = utils.safe_request("post", url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            text = res_json['candidates'][0]['content']['parts'][0]['text']
            return text
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    except Exception as e:
        if raise_on_error:
            raise e
        fallback_msg = f"\n\n> [!WARNING]\n> Gemini API call failed: {str(e)}. Falling back to local/rule-based synthesis.\n\n"
        return fallback_msg + generate_local_summary(scraped_data, query, spec_topic)

def generate_openai_summary(scraped_data: List[Dict[str, Any]], query: str, spec_topic: str, api_key: str, raise_on_error: bool = False) -> str:
    """
    Queries OpenAI's Chat Completion API (using gpt-4o-mini) to synthesize scraped content.
    """
    context_parts = []
    for idx, doc in enumerate(scraped_data):
        if doc.get("success"):
            text_content = doc.get("raw_text", "")[:4000]
            context_parts.append(f"Source {idx+1}: {doc['title']} ({doc['url']})\nContent:\n{text_content}\n---\n")
            
    context_str = "\n".join(context_parts)
    
    prompt = f"""Analyze the scraped web content below and generate a deep-dive research report.

User's Original Query: {query}
Specific Information Needed/Focus: {spec_topic}

Scraped Data:
{context_str}

Please synthesize the scraped data to write a detailed, highly structured Markdown report.
Ensure you add a 'Sources Scraped' table at the end and dynamically cite sources with URLs.
"""

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a professional research assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    try:
        response = utils.safe_request("post", url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            return res_json['choices'][0]['message']['content']
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    except Exception as e:
        if raise_on_error:
            raise e
        fallback_msg = f"\n\n> [!WARNING]\n> OpenAI API call failed: {str(e)}. Falling back to local/rule-based synthesis.\n\n"
        return fallback_msg + generate_local_summary(scraped_data, query, spec_topic)

def generate_claude_summary(scraped_data: List[Dict[str, Any]], query: str, spec_topic: str, api_key: str, raise_on_error: bool = False) -> str:
    """
    Queries Anthropic's Messages API (using claude-3-5-sonnet-20241022) to synthesize scraped content.
    """
    context_parts = []
    for idx, doc in enumerate(scraped_data):
        if doc.get("success"):
            text_content = doc.get("raw_text", "")[:4000]
            context_parts.append(f"Source {idx+1}: {doc['title']} ({doc['url']})\nContent:\n{text_content}\n---\n")
            
    context_str = "\n".join(context_parts)
    
    prompt = f"""Analyze the scraped web content below and generate a deep-dive research report.

User's Original Query: {query}
Specific Information Needed/Focus: {spec_topic}

Scraped Data:
{context_str}

Please synthesize the scraped data to write a detailed, highly structured Markdown report.
Ensure you add a 'Sources Scraped' table at the end and dynamically cite sources with URLs.
"""

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 2048,
        "temperature": 0.3,
        "system": "You are a professional research assistant.",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        response = utils.safe_request("post", url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            return res_json['content'][0]['text']
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    except Exception as e:
        if raise_on_error:
            raise e
        fallback_msg = f"\n\n> [!WARNING]\n> Anthropic Claude API call failed: {str(e)}. Falling back to local/rule-based synthesis.\n\n"
        return fallback_msg + generate_local_summary(scraped_data, query, spec_topic)

def synthesize_topics(scraped_data: List[Dict[str, Any]], query: str, spec_topic: str) -> str:
    """
    Orchestrates the synthesis step. Automatically routes to the selected AI provider based on 
    config priority (Gemini -> OpenAI -> Claude) if key is present, with multi-provider failover.
    Falls back to local synthesis only if all configured third-party LLM API calls fail or are missing.
    """
    logger.info("Starting AI synthesis for query: '%s' (Focus: '%s'). Loaded %d source(s) to analyze.", query, spec_topic, len(scraped_data))
    # Import config to check settings dynamically
    try:
        import config_manager
        config = config_manager.load_config()
    except Exception:
        config = {}
        
    preferred = config.get("preferred_provider", "local")
    
    gemini_key = config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    openai_key = config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
    claude_key = config.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
    
    providers_info = {
        "gemini": {
            "fn": generate_gemini_summary,
            "key": gemini_key,
            "name": "Gemini API"
        },
        "openai": {
            "fn": generate_openai_summary,
            "key": openai_key,
            "name": "OpenAI API"
        },
        "anthropic": {
            "fn": generate_claude_summary,
            "key": claude_key,
            "name": "Anthropic Claude API"
        }
    }
    
    attempt_order = []
    
    # 1. Add preferred provider first if it has a key
    if preferred in providers_info and providers_info[preferred]["key"]:
        attempt_order.append(preferred)
        
    # 2. Add remaining providers that have valid keys, following fallback priority: gemini -> openai -> anthropic
    for p in ["gemini", "openai", "anthropic"]:
        if p not in attempt_order and providers_info[p]["key"]:
            attempt_order.append(p)
            
    # If preferred provider is 'local', we skip LLM providers and go straight to local summary
    if preferred == "local":
        logger.info("Routing synthesis to local keyword summary (preferred)...")
        return generate_local_summary(scraped_data, query, spec_topic)
        
    errors = []
    for provider_name in attempt_order:
        info = providers_info[provider_name]
        logger.info("Routing synthesis to %s...", info["name"])
        try:
            return info["fn"](scraped_data, query, spec_topic, info["key"], raise_on_error=True)
        except Exception as e:
            err_msg = f"{info['name']} failed: {str(e)}"
            errors.append(err_msg)
            logger.warning("%s. Trying next available provider...", err_msg)
            
    if errors:
        fallback_msg = "\n\n> [!WARNING]\n> All configured AI providers failed during synthesis:\n"
        for err in errors:
            fallback_msg += f"> * {err}\n"
        fallback_msg += "> Falling back to local/rule-based synthesis.\n\n"
        return fallback_msg + generate_local_summary(scraped_data, query, spec_topic)
        
    logger.warning("No third-party LLM API keys found. Falling back to local keyword synthesis...")
    return generate_local_summary(scraped_data, query, spec_topic)

def generate_gemini_grounding_search(query: str, spec_topic: str, api_key: str) -> Dict[str, Any]:
    """
    Executes a direct HTTP request to the Gemini API with Google Search Grounding enabled.
    This lets the AI search Google directly, reason on real-time findings, and return a report.
    Returns a dict with "report" and "queries".
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""You are a professional research assistant. Perform a real-time web search and generate a highly detailed, structured Markdown research report.

Search Query: {query}
Focus Area & Specific Questions: {spec_topic}

Make sure to:
1. Write a professional title and a compelling Executive Summary.
2. Structure the body with clear headings and bullet points answering the user's specific information needs.
3. Cite the exact websites and URLs you find in real time.
4. Add a 'Key Takeaways' section.
5. Create a 'Sources Scraped' Markdown table at the end listing the titles and URLs of sources used.
6. Write only the Markdown report itself, no wrapping conversational text.
"""
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "tools": [
            {
                "googleSearch": {}
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2500
        }
    }
    
    try:
        response = utils.safe_request("post", url, json=payload, headers=headers, timeout=45)
        if response.status_code == 200:
            res_json = response.json()
            candidate = res_json['candidates'][0]
            text = candidate['content']['parts'][0]['text']
            
            # Extract search queries if available
            queries = []
            grounding_metadata = candidate.get("groundingMetadata", {})
            if "webSearchQueries" in grounding_metadata:
                queries = grounding_metadata["webSearchQueries"]
                
            return {
                "success": True,
                "report": text,
                "queries": queries,
                "error": None
            }
        else:
            return {
                "success": False,
                "report": "",
                "queries": [],
                "error": f"HTTP {response.status_code}: {response.text}"
            }
    except Exception as e:
        return {
            "success": False,
            "report": "",
            "queries": [],
            "error": str(e)
        }


