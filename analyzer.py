import re
import os
import requests
import datetime
from typing import List, Dict, Any, Set, Optional
from collections import Counter
import math
import utils
logger = utils.setup_logging()

# Rate limiter instance to keep LLM requests under 15 RPM (capacity 5, fill rate 0.25 tokens/sec)
llm_governor = utils.TokenBucket(capacity=5.0, fill_rate=0.25)

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

def generate_local_summary(scraped_data: List[Dict[str, Any]], query: str, spec_topic: str, previous_report: Optional[str] = None) -> str:
    """
    Performs local, rule-based extractive summarization and outputs a beautiful,
    well-structured Markdown deep dive report. Supports incremental report appends.
    """
    if previous_report and previous_report.strip():
        keywords = extract_keywords(query) | extract_keywords(spec_topic)
        all_sentences = []
        for doc_idx, doc in enumerate(scraped_data):
            if not doc.get("success") or not doc.get("paragraphs"):
                continue
            for p in doc["paragraphs"]:
                for s in split_into_sentences(p):
                    score = score_sentence(s, keywords, 1.0)
                    if score > 0.05:
                        all_sentences.append({"text": s, "score": score, "url": doc["url"]})
                        
        all_sentences.sort(key=lambda x: x["score"], reverse=True)
        prev_lower = previous_report.lower()
        new_delta_sentences = []
        for s in all_sentences:
            if s["text"].lower() not in prev_lower:
                new_delta_sentences.append(s)
                if len(new_delta_sentences) >= 5:
                    break
                    
        if not new_delta_sentences:
            return previous_report
            
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        delta_lines = [f"\n\n## 🔄 Incremental Update (Local - {timestamp_str})\n"]
        for s in new_delta_sentences:
            delta_lines.append(f"- {s['text']} *([Source]({s['url']}))*")
            
        if "## Sources Scraped" in previous_report:
            parts = previous_report.rsplit("## Sources Scraped", 1)
            return parts[0] + "\n".join(delta_lines) + "\n\n## Sources Scraped" + parts[1]
        else:
            return previous_report + "\n".join(delta_lines)

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
    
    # Category Keyword Lists
    tech_keywords = {"system", "architecture", "code", "plugin", "python", "api", "tls", "regex", "framework", "database", "git", "implementation", "class", "function", "method", "parser"}
    feasibility_keywords = {"cost", "pricing", "rate limit", "rpm", "tpm", "memory", "ram", "gpu", "hardware", "speed", "latency", "free", "performance", "limit", "bound", "run"}
    safety_keywords = {"security", "legal", "compliance", "terms", "privacy", "tos", "waf", "cloudflare", "cookies", "user-agent", "block", "restrict", "captcha", "ban", "safe"}

    tech_sentences = []
    feasibility_sentences = []
    safety_sentences = []
    uncategorized_sentences = []

    for s in unique_sentences[6:15]:
        text_lower = s["text"].lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        # Check overlap
        is_tech = bool(words & tech_keywords)
        is_feas = bool(words & feasibility_keywords)
        is_safe = bool(words & safety_keywords)
        
        if is_tech:
            tech_sentences.append(s)
        elif is_feas:
            feasibility_sentences.append(s)
        elif is_safe:
            safety_sentences.append(s)
        else:
            uncategorized_sentences.append(s)

    has_sections = False
    
    if tech_sentences:
        markdown_lines.append("### 🛠️ Technical Architecture & Core Mechanisms\n")
        for s in tech_sentences:
            markdown_lines.append(f"- {s['text']} *([Source]({s['source_url']}))*")
        markdown_lines.append("")
        has_sections = True
        
    if feasibility_sentences:
        markdown_lines.append("### 📊 Feasibility & Resource Constraints\n")
        for s in feasibility_sentences:
            markdown_lines.append(f"- {s['text']} *([Source]({s['source_url']}))*")
        markdown_lines.append("")
        has_sections = True
        
    if safety_sentences:
        markdown_lines.append("### 🛡️ Operational, Legal & Safety Perspectives\n")
        for s in safety_sentences:
            markdown_lines.append(f"- {s['text']} *([Source]({s['source_url']}))*")
        markdown_lines.append("")
        has_sections = True
        
    if uncategorized_sentences:
        markdown_lines.append("### 💡 General Findings & Discussions\n")
        for s in uncategorized_sentences:
            markdown_lines.append(f"- {s['text']} *([Source]({s['source_url']}))*")
        markdown_lines.append("")
        has_sections = True
        
    if not has_sections:
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

def _classify_content_style(text: str) -> str:
    """
    Classifies text as 'narrative' (stories, interviews, transcripts) 
    or 'informational' (news, Wikipedia, reports).
    """
    # 1. Count quote/dialogue marks (double quotes, curly quotes, and boundary-aligned single quotes)
    quotes = len(re.findall(r'["“”«»]|(?:\s\'|\'\s)', text))
    words = len(text.split())
    if words == 0:
        return "informational"
        
    quote_density = quotes / words
    
    # 2. Count narrative pronouns (I, me, my, we, us, our)
    narrative_pronouns = len(re.findall(r'\b(i|me|my|we|us|our)\b', text.lower()))
    pronoun_density = narrative_pronouns / words
    
    # Heuristic gate: Dialogue-heavy or high personal narrative density
    if quote_density > 0.015 or pronoun_density > 0.04:
        return "narrative"
    return "informational"

def text_rank_extract(sentences: List[str], query_keywords: Set[str], max_sentences: int = 15) -> List[str]:
    """
    Ranks sentences using the PageRank algorithm over a sentence Jaccard similarity graph.
    """
    n = len(sentences)
    if n <= max_sentences:
        return sentences
        
    # Pre-tokenize sentences to sets of lowercase keywords
    sentence_words = []
    for sent in sentences:
        words = extract_keywords(sent)
        sentence_words.append(words)
        
    # Build Similarity Adjacency Matrix
    # similarity(A, B) = size of intersection / size of union
    weights = [[0.0] * n for _ in range(n)]
    out_sums = [0.0] * n
    for i in range(n):
        for j in range(i + 1, n):
            words_a = sentence_words[i]
            words_b = sentence_words[j]
            intersection = len(words_a.intersection(words_b))
            union = len(words_a.union(words_b))
            
            if union > 0:
                sim = intersection / union
                weights[i][j] = sim
                weights[j][i] = sim
                out_sums[i] += sim
                out_sums[j] += sim

    # PageRank Iteration (Damping factor = 0.85)
    d = 0.85
    scores = [1.0 / n] * n
    
    for _ in range(15):  # 15 power iterations
        new_scores = [0.0] * n
        for i in range(n):
            sum_incoming = 0.0
            for j in range(n):
                if out_sums[j] > 0:
                    sum_incoming += (scores[j] * weights[j][i]) / out_sums[j]
            new_scores[i] = (1 - d) / n + d * sum_incoming
        scores = new_scores

    # Score sentence list: (score, original_index, sentence_text)
    scored_sentences = []
    for i in range(n):
        # Boost sentences slightly if they match query keywords to keep query relevance
        query_boost = 1.0 + 0.5 * len(query_keywords.intersection(sentence_words[i]))
        final_score = scores[i] * query_boost
        
        # Length filter: Skip short/long lines
        words_cnt = len(sentences[i].split())
        if 5 <= words_cnt <= 60:
            scored_sentences.append((final_score, i, sentences[i]))

    # Sort by PageRank score descending, select top matches
    if not scored_sentences:
        return sentences[:max_sentences]
        
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    top_matches = scored_sentences[:max_sentences]
    
    # Sort back into chronological order
    top_matches.sort(key=lambda x: x[1])
    return [item[2] for item in top_matches]

def lead_bias_extract(sentences: List[str], keywords: Set[str], max_sentences: int = 15) -> List[str]:
    """
    Extracts high-value sentences using position-weighted query keyword salience.
    """
    if len(sentences) <= max_sentences:
        return sentences
        
    # Always include the first 2 sentences as structural anchors
    final_selections = []
    final_selections.append((999.0, 0, sentences[0]))
    final_selections.append((999.0, 1, sentences[1]))
    
    scored_sentences = []
    for idx, sent in enumerate(sentences[2:]):
        # 1. Skip gibberish / layout junk (length filters)
        word_count = len(sent.split())
        if word_count < 5 or word_count > 60:
            continue
            
        # 2. Score based on UNIQUE keyword matches
        unique_matches = keywords.intersection(extract_keywords(sent))
        if not unique_matches:
            continue
            
        # Score calculation: unique matches * 2.0 + position weight (favor earlier sentences slightly)
        pos_weight = 1.0 / math.sqrt(idx + 3)
        score = len(unique_matches) * 2.0 + pos_weight
        
        scored_sentences.append((score, idx + 2, sent))
        
    if not scored_sentences:
        return sentences[:max_sentences]
        
    # Sort by score descending and take top matches
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    best_matches = scored_sentences[:max_sentences - 2]
    
    for item in best_matches:
        final_selections.append(item)
        
    # Sort chronologically by original index
    final_selections.sort(key=lambda x: x[1])
    return [item[2] for item in final_selections]

def filter_dense_context(raw_text: str, query: str, spec_topic: str, max_sentences: int = 15) -> str:
    """
    Strips down raw text to the most relevant sentences matching the query keywords.
    Dynamically routes between TextRank (for narratives) and Lead-Bias (for informational articles).
    """
    keywords = extract_keywords(query).union(extract_keywords(spec_topic))
    if not keywords:
        return raw_text[:2000]
        
    sentences = split_into_sentences(raw_text)
    if len(sentences) < 5:
        return raw_text[:2000]
        
    # Classify content type
    style = _classify_content_style(raw_text)
    
    if style == "narrative":
        logger.info("Narrative/Dialogue pattern detected. Using Graph-based TextRank summarization...")
        selected_sentences = text_rank_extract(sentences, keywords, max_sentences)
    else:
        logger.info("Informational pattern detected. Using Position-Weighted Lead-Bias summarization...")
        selected_sentences = lead_bias_extract(sentences, keywords, max_sentences)
        
    return " ".join(selected_sentences)

def generate_gemini_summary(scraped_data: List[Dict[str, Any]], query: str, spec_topic: str, api_key: str, raise_on_error: bool = False, previous_report: Optional[str] = None) -> str:
    """
    Queries Gemini 1.5 Flash using direct HTTP requests to synthesize the scraped text content
    into a gorgeous, highly structured and professional Markdown Deep Dive report.
    """
    llm_governor.wait_for_token()
    try:
        import config_manager
        config = config_manager.load_config()
        use_filtering = config.get("smart_token_filtering", True)
    except Exception:
        use_filtering = True

    context_parts = []
    for idx, doc in enumerate(scraped_data):
        if doc.get("success"):
            raw_text = doc.get("raw_text", "")
            if use_filtering:
                text_content = filter_dense_context(raw_text, query, spec_topic, max_sentences=15)
            else:
                text_content = raw_text[:4000]
            context_parts.append(f"Source {idx+1}: {doc['title']} ({doc['url']})\nContent:\n{text_content}\n---\n")
            
    context_str = "\n".join(context_parts)
    
    if previous_report and previous_report.strip():
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        prompt = f"""You are a professional research assistant. Below is a previously compiled research report, followed by newly scraped web data.

User's Original Query: {query}
Specific Information Needed/Focus: {spec_topic}

[PREVIOUS REPORT]
{previous_report}

[NEW SCRAPED DATA]
{context_str}

Please perform an incremental update on the report:
1. Compare the new scraped data against the [PREVIOUS REPORT]. If there are new findings, technical details, or updates:
   - Preserve the original report structure and content.
   - Append a new section: `## 🔄 Incremental Update ({timestamp_str})` at the bottom of the report (before the Sources table).
   - Write a concise list of new findings, updates, and added technical details under this section.
   - Update the 'Sources Scraped' table at the very end to include any newly scraped sources.
2. If there are no new findings or details, return the [PREVIOUS REPORT] completely unchanged.
3. Write only the Markdown report itself, no wrapping conversational text. Ensure it is clean, comprehensive, and detailed.
"""
    else:
        prompt = f"""You are a professional research assistant. Analyze the scraped web content below and generate a deep-dive research report.

User's Original Query: {query}
Specific Information Needed/Focus: {spec_topic}

Scraped Data:
{context_str}

Please synthesize the scraped data to write a detailed, highly structured Markdown report.
Make sure to:
1. Write a professional title and a compelling Executive Summary.
2. Structure the body systematically into three distinct perspective sections:
   - `### 🛠️ Technical Architecture & Core Mechanisms`: Code structures, technical designs, systems design, and core mechanisms.
   - `### 📊 Feasibility & Resource Constraints`: Pricing, operational overhead, hardware/RAM limits, speed, and latency.
   - `### 🛡️ Operational, Legal & Safety Perspectives`: Privacy concerns, compliance/terms boundaries, security, and usage protocols.
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

def generate_openai_summary(scraped_data: List[Dict[str, Any]], query: str, spec_topic: str, api_key: str, raise_on_error: bool = False, previous_report: Optional[str] = None) -> str:
    """
    Queries OpenAI's Chat Completion API (using gpt-4o-mini) to synthesize scraped content.
    """
    llm_governor.wait_for_token()
    try:
        import config_manager
        config = config_manager.load_config()
        use_filtering = config.get("smart_token_filtering", True)
    except Exception:
        use_filtering = True

    context_parts = []
    for idx, doc in enumerate(scraped_data):
        if doc.get("success"):
            raw_text = doc.get("raw_text", "")
            if use_filtering:
                text_content = filter_dense_context(raw_text, query, spec_topic, max_sentences=15)
            else:
                text_content = raw_text[:4000]
            context_parts.append(f"Source {idx+1}: {doc['title']} ({doc['url']})\nContent:\n{text_content}\n---\n")
            
    context_str = "\n".join(context_parts)
    
    if previous_report and previous_report.strip():
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        prompt = f"""You are a professional research assistant. Below is a previously compiled research report, followed by newly scraped web data.

User's Original Query: {query}
Specific Information Needed/Focus: {spec_topic}

[PREVIOUS REPORT]
{previous_report}

[NEW SCRAPED DATA]
{context_str}

Please perform an incremental update on the report:
1. Compare the new scraped data against the [PREVIOUS REPORT]. If there are new findings, technical details, or updates:
   - Preserve the original report structure and content.
   - Append a new section: `## 🔄 Incremental Update ({timestamp_str})` at the bottom of the report (before the Sources table).
   - Write a concise list of new findings, updates, and added technical details under this section.
   - Update the 'Sources Scraped' table at the very end to include any newly scraped sources.
2. If there are no new findings or details, return the [PREVIOUS REPORT] completely unchanged.
3. Write only the Markdown report itself, no wrapping conversational text. Ensure it is clean, comprehensive, and detailed.
"""
    else:
        prompt = f"""Analyze the scraped web content below and generate a deep-dive research report.

User's Original Query: {query}
Specific Information Needed/Focus: {spec_topic}

Scraped Data:
{context_str}

Please synthesize the scraped data to write a detailed, highly structured Markdown report.
Make sure to:
1. Write a professional title and a compelling Executive Summary.
2. Structure the body systematically into three distinct perspective sections:
   - `### 🛠️ Technical Architecture & Core Mechanisms`: Code structures, technical designs, systems design, and core mechanisms.
   - `### 📊 Feasibility & Resource Constraints`: Pricing, operational overhead, hardware/RAM limits, speed, and latency.
   - `### 🛡️ Operational, Legal & Safety Perspectives`: Privacy concerns, compliance/terms boundaries, security, and usage protocols.
3. Cite sources dynamically using Markdown links pointing to the exact source URLs from the Scraped Data.
4. Add a 'Key Takeaways' section.
5. Create a 'Sources Scraped' Markdown table at the end showing the Title and URL of all sources.
6. Write only the Markdown report itself, no wrapping conversational text. Ensure it is clean, comprehensive, and detailed.
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

def generate_claude_summary(scraped_data: List[Dict[str, Any]], query: str, spec_topic: str, api_key: str, raise_on_error: bool = False, previous_report: Optional[str] = None) -> str:
    """
    Queries Anthropic's Messages API (using claude-3-5-sonnet-20241022) to synthesize scraped content.
    """
    llm_governor.wait_for_token()
    try:
        import config_manager
        config = config_manager.load_config()
        use_filtering = config.get("smart_token_filtering", True)
    except Exception:
        use_filtering = True

    context_parts = []
    for idx, doc in enumerate(scraped_data):
        if doc.get("success"):
            raw_text = doc.get("raw_text", "")
            if use_filtering:
                text_content = filter_dense_context(raw_text, query, spec_topic, max_sentences=15)
            else:
                text_content = raw_text[:4000]
            context_parts.append(f"Source {idx+1}: {doc['title']} ({doc['url']})\nContent:\n{text_content}\n---\n")
            
    context_str = "\n".join(context_parts)
    
    if previous_report and previous_report.strip():
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        prompt = f"""You are a professional research assistant. Below is a previously compiled research report, followed by newly scraped web data.

User's Original Query: {query}
Specific Information Needed/Focus: {spec_topic}

[PREVIOUS REPORT]
{previous_report}

[NEW SCRAPED DATA]
{context_str}

Please perform an incremental update on the report:
1. Compare the new scraped data against the [PREVIOUS REPORT]. If there are new findings, technical details, or updates:
   - Preserve the original report structure and content.
   - Append a new section: `## 🔄 Incremental Update ({timestamp_str})` at the bottom of the report (before the Sources table).
   - Write a concise list of new findings, updates, and added technical details under this section.
   - Update the 'Sources Scraped' table at the very end to include any newly scraped sources.
2. If there are no new findings or details, return the [PREVIOUS REPORT] completely unchanged.
3. Write only the Markdown report itself, no wrapping conversational text. Ensure it is clean, comprehensive, and detailed.
"""
    else:
        prompt = f"""Analyze the scraped web content below and generate a deep-dive research report.

User's Original Query: {query}
Specific Information Needed/Focus: {spec_topic}

Scraped Data:
{context_str}

Please synthesize the scraped data to write a detailed, highly structured Markdown report.
Make sure to:
1. Write a professional title and a compelling Executive Summary.
2. Structure the body systematically into three distinct perspective sections:
   - `### 🛠️ Technical Architecture & Core Mechanisms`: Code structures, technical designs, systems design, and core mechanisms.
   - `### 📊 Feasibility & Resource Constraints`: Pricing, operational overhead, hardware/RAM limits, speed, and latency.
   - `### 🛡️ Operational, Legal & Safety Perspectives`: Privacy concerns, compliance/terms boundaries, security, and usage protocols.
3. Cite sources dynamically using Markdown links pointing to the exact source URLs from the Scraped Data.
4. Add a 'Key Takeaways' section.
5. Create a 'Sources Scraped' Markdown table at the end showing the Title and URL of all sources.
6. Write only the Markdown report itself, no wrapping conversational text. Ensure it is clean, comprehensive, and detailed.
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

def synthesize_topics(scraped_data: List[Dict[str, Any]], query: str, spec_topic: str, previous_report: Optional[str] = None) -> str:
    """
    Orchestrates the synthesis step. Automatically routes to the selected AI provider based on 
    config priority (Gemini -> OpenAI -> Claude) if key is present, with multi-provider failover.
    Falls back to local synthesis only if all configured third-party LLM API calls fail or are missing.
    Supports incremental updates via previous_report.
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
        return generate_local_summary(scraped_data, query, spec_topic, previous_report=previous_report)
        
    errors = []
    for provider_name in attempt_order:
        info = providers_info[provider_name]
        logger.info("Routing synthesis to %s...", info["name"])
        try:
            return info["fn"](scraped_data, query, spec_topic, info["key"], raise_on_error=True, previous_report=previous_report)
        except Exception as e:
            err_msg = f"{info['name']} failed: {str(e)}"
            errors.append(err_msg)
            logger.warning("%s. Trying next available provider...", err_msg)
            
    if errors:
        fallback_msg = "\n\n> [!WARNING]\n> All configured AI providers failed during synthesis:\n"
        for err in errors:
            fallback_msg += f"> * {err}\n"
        fallback_msg += "> Falling back to local/rule-based synthesis.\n\n"
        return fallback_msg + generate_local_summary(scraped_data, query, spec_topic, previous_report=previous_report)
        
    logger.warning("No third-party LLM API keys found. Falling back to local keyword synthesis...")
    return generate_local_summary(scraped_data, query, spec_topic, previous_report=previous_report)

def generate_gemini_grounding_search(query: str, spec_topic: str, api_key: str) -> Dict[str, Any]:
    """
    Executes a direct HTTP request to the Gemini API with Google Search Grounding enabled.
    This lets the AI search Google directly, reason on real-time findings, and return a report.
    Returns a dict with "report" and "queries".
    """
    llm_governor.wait_for_token()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""You are a professional research assistant. Perform a real-time web search and generate a highly detailed, structured Markdown research report.

Search Query: {query}
Focus Area & Specific Questions: {spec_topic}

Make sure to:
1. Write a professional title and a compelling Executive Summary.
2. Structure the body systematically into three distinct perspective sections:
   - `### 🛠️ Technical Architecture & Core Mechanisms`: Code structures, technical designs, systems design, and core mechanisms.
   - `### 📊 Feasibility & Resource Constraints`: Pricing, operational overhead, hardware/RAM limits, speed, and latency.
   - `### 🛡️ Operational, Legal & Safety Perspectives`: Privacy concerns, compliance/terms boundaries, security, and usage protocols.
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


