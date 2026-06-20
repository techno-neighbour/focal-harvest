import os
import json
from typing import Dict, Any

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "openai_api_key": "",
    "anthropic_api_key": "",
    "tavily_api_key": "",
    "preferred_provider": "local",  # local, gemini, openai, anthropic
    "search_engine": "duckduckgo",  # duckduckgo, tavily, ai_grounding
    "discord_webhook": "",
    "telegram_token": "",
    "telegram_chat_id": "",
    "default_max_results": 5,
    "saved_searches": []
}



def load_config() -> Dict[str, Any]:
    """Loads configuration from config.json and merges with environment variables."""
    config = DEFAULT_CONFIG.copy()
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception:
            pass
            
    # Overlay environment variables if present
    if os.environ.get("GEMINI_API_KEY"):
        config["gemini_api_key"] = os.environ.get("GEMINI_API_KEY")
        if config["preferred_provider"] == "local":
            config["preferred_provider"] = "gemini"
            
    if os.environ.get("OPENAI_API_KEY"):
        config["openai_api_key"] = os.environ.get("OPENAI_API_KEY")
        if config["preferred_provider"] == "local":
            config["preferred_provider"] = "openai"
            
    if os.environ.get("ANTHROPIC_API_KEY"):
        config["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY")
        if config["preferred_provider"] == "local":
            config["preferred_provider"] = "anthropic"
            
    if os.environ.get("TAVILY_API_KEY"):
        config["tavily_api_key"] = os.environ.get("TAVILY_API_KEY")
        
    if os.environ.get("DISCORD_WEBHOOK_URL"):
        config["discord_webhook"] = os.environ.get("DISCORD_WEBHOOK_URL")
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        config["telegram_token"] = os.environ.get("TELEGRAM_BOT_TOKEN")
    if os.environ.get("TELEGRAM_CHAT_ID"):
        config["telegram_chat_id"] = os.environ.get("TELEGRAM_CHAT_ID")
        
    return config



def save_config(config: Dict[str, Any]) -> bool:
    """Saves configuration to config.json."""
    try:
        # Strip environment variables or save them cleanly
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

def add_saved_search(query: str, spec_topic: str) -> None:
    """Helper to save a search configuration for quick loading later."""
    config = load_config()
    search_item = {"query": query, "spec_topic": spec_topic}
    if search_item not in config["saved_searches"]:
        config["saved_searches"].append(search_item)
        save_config(config)
