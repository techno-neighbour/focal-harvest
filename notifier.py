import os
import json
import datetime
import requests
from typing import List, Dict, Any
import utils
logger = utils.setup_logging()
from rich.console import Console
from rich.markdown import Markdown

console = Console()

def save_report_to_files(query: str, spec_topic: str, markdown_content: str, scraped_data: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Saves the final report as a Markdown file and the raw scraped data as a JSON file
    in a local 'reports' directory.
    """
    # Create reports directory if it doesn't exist
    os.makedirs("reports", exist_ok=True)
    
    # Generate slug for filename
    safe_query = "".join([c if c.isalnum() else "_" for c in query.lower()[:30]])
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    md_filename = f"reports/report_{safe_query}_{timestamp}.md"
    json_filename = f"reports/raw_data_{safe_query}_{timestamp}.json"
    
    logger.info("Saving generated report to files: '%s' and '%s'", md_filename, json_filename)
    
    # Save Markdown report
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        
    # Save raw JSON metadata and content
    json_payload = {
        "query": query,
        "special_topic": spec_topic,
        "timestamp": timestamp,
        "sources_scraped": scraped_data
    }
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, indent=2, ensure_ascii=False)
        
    return {
        "markdown_path": md_filename,
        "json_path": json_filename
    }

def print_to_console(markdown_content: str) -> None:
    """Renders the Markdown report beautifully on the terminal using Rich."""
    console.print("\n" + "="*80)
    console.print(Markdown(markdown_content))
    console.print("="*80 + "\n")

def send_discord_webhook(webhook_url: str, query: str, spec_topic: str, markdown_content: str, md_filepath: str) -> bool:
    """Sends a summary of the report to a Discord Webhook channel."""
    if not webhook_url:
        return False
        
    logger.info("Attempting to dispatch Discord Webhook alert for query: '%s'", query)
    # Build clean snippet from executive summary or markdown
    summary_snippet = ""
    lines = markdown_content.splitlines()
    exec_idx = -1
    for i, line in enumerate(lines):
        if "## Executive Summary" in line:
            exec_idx = i
            break
            
    if exec_idx != -1:
        snippet_lines = []
        for line in lines[exec_idx+1:]:
            if line.startswith("##"): # stop at next section
                break
            if line.strip():
                snippet_lines.append(line.strip())
        summary_snippet = "\n".join(snippet_lines[:5])
        
    if not summary_snippet:
        summary_snippet = markdown_content[:500] + "..."
        
    payload = {
        "embeds": [
            {
                "title": f"🌐 Web Scraper Deep Dive: {query}",
                "description": f"**Focus Area:** {spec_topic}\n\n**Executive Summary Snippet:**\n{summary_snippet}",
                "color": 3066993, # Nice green/teal color code
                "fields": [
                    {
                        "name": "💾 Local File Saved",
                        "value": f"`{md_filepath}`",
                        "inline": False
                    }
                ],
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        ]
    }
    
    try:
        res = utils.safe_request("post", webhook_url, json=payload, timeout=10)
        success = res.status_code in (200, 204)
        if success:
            logger.info("Successfully dispatched Discord webhook alert.")
        else:
            logger.error("Discord webhook delivery failed with HTTP status code: %d", res.status_code)
        return success
    except Exception as e:
        logger.error("Exception sending Discord webhook notification: %s", str(e))
        console.print(f"[bold red]Failed to send Discord webhook: {str(e)}[/bold red]")
        return False

def send_telegram_notification(token: str, chat_id: str, query: str, spec_topic: str, markdown_content: str) -> bool:
    """Sends a formatted summary text notification to a Telegram Chat."""
    if not token or not chat_id:
        return False
        
    logger.info("Attempting to dispatch Telegram sendMessage payload for query: '%s'", query)
    message = f"**🌐 Web Scraper Deep Dive Report**\n\n"
    message += f"**Query:** {query}\n"
    message += f"**Focus Area:** {spec_topic}\n\n"
    
    # Append first few lines of report text
    clean_report = markdown_content.replace("# ", "").replace("## ", "").replace("**", "")
    message += clean_report[:1000] + "...\n\n_Full report saved locally._"
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        res = utils.safe_request("post", url, json=payload, timeout=10)
        success = res.status_code == 200
        if success:
            logger.info("Successfully dispatched Telegram notification alert.")
        else:
            logger.error("Telegram notification delivery failed with HTTP status code: %d", res.status_code)
        return success
    except Exception as e:
        logger.error("Exception sending Telegram notification: %s", str(e))
        console.print(f"[bold red]Failed to send Telegram notification: {str(e)}[/bold red]")
        return False

def dispatch_notifications(
    query: str, 
    spec_topic: str, 
    markdown_content: str, 
    scraped_data: List[Dict[str, Any]], 
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Saves report files and dispatches notifications via console, discord, and telegram 
    based on config options.
    """
    logger.info("Starting report notification dispatch router...")
    saved_paths = save_report_to_files(query, spec_topic, markdown_content, scraped_data)
    
    results = {
        "saved_paths": saved_paths,
        "console": True,
        "discord": False,
        "telegram": False
    }
    
    # Always print to console
    print_to_console(markdown_content)
    
    # Send Discord notification if configured
    discord_webhook = config.get("discord_webhook") or os.environ.get("DISCORD_WEBHOOK_URL")
    if discord_webhook:
        results["discord"] = send_discord_webhook(discord_webhook, query, spec_topic, markdown_content, saved_paths["markdown_path"])
        
    # Send Telegram notification if configured
    tg_token = config.get("telegram_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = config.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat_id:
        results["telegram"] = send_telegram_notification(tg_token, tg_chat_id, query, spec_topic, markdown_content)
        
    logger.info("Notification dispatch router complete. Output paths: %s", json.dumps(saved_paths))
    return results
