import warnings
try:
    from requests.exceptions import RequestsDependencyWarning
    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except ImportError:
    pass

import os
import sys
import time
import datetime
import glob
import hashlib
from typing import List, Dict, Any, Tuple, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.live import Live
from rich.align import Align
from rich.text import Text
from rich.markdown import Markdown

# Local module imports
import scraper
import analyzer
import notifier
import config_manager
import utils

console = Console()
logger = utils.setup_logging()

BANNER_TEXT = """
    ███████╗ ██████╗  ██████╗  █████╗  ██╗        ██╗  ██╗ █████╗ ██████╗ ██╗   ██╗███████╗███████╗████████╗
    ██╔════╝██╔═══██╗██╔════╝ ██╔══██╗ ██║        ██║  ██║██╔══██╗██╔══██╗██║   ██║██╔════╝██╔════╝╚══██╔══╝
    █████╗  ██║   ██║██║      ███████║ ██║        ███████║███████║██████╔╝██║   ██║█████╗  ███████╗   ██║   
    ██╔══╝  ██║   ██║██║      ██╔══██║ ██║        ██╔══██║██╔══██║██╔══██╗╚██╗ ██╔╝██╔══╝  ╚════██║   ██║   
    ██║     ╚██████╔╝╚██████╗ ██║  ██║ ███████╗   ██║  ██║██║  ██║██║  ██║ ╚████╔╝ ███████╗███████║   ██║   
    ╚═╝      ╚═════╝  ╚═════╝ ╚═╝  ╚═╝ ╚══════╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚══════╝   ╚═╝
    
                                       Search • Scrape • Store • Notify
"""



def show_banner():
    """Prints the application banner in high definition styling."""
    gradient_text = Text(BANNER_TEXT)
    gradient_text.stylize("bold cyan")
    banner_panel = Panel(
        Align.center(gradient_text),
        border_style="bright_blue",
        subtitle="v1.4.0 • Query Decomposition, STORM Synthesis, Incremental Living Logs, & Document Exporters"
    )
    console.print(banner_panel)

def configure_settings_menu():
    """Displays and edits configuration settings."""
    config = config_manager.load_config()
    
    while True:
        console.clear()
        show_banner()
        
        # Display current settings
        table = Table(title="⚙️ Current Application Settings", border_style="cyan")
        table.add_column("No.", style="cyan", justify="center")
        table.add_column("Setting Key", style="yellow")
        table.add_column("Current Value", style="white")
        
        gemini_masked = "•" * 15 if config.get("gemini_api_key") else "[red]Not Set[/red]"
        openai_masked = "•" * 15 if config.get("openai_api_key") else "[red]Not Set[/red]"
        anthropic_masked = "•" * 15 if config.get("anthropic_api_key") else "[red]Not Set[/red]"
        tavily_masked = "•" * 15 if config.get("tavily_api_key") else "[red]Not Set (Falls back to DuckDuckGo)[/red]"
        
        provider = config.get("preferred_provider", "local").upper()
        if provider == "LOCAL":
            provider_colored = "[green]LOCAL (Extractive Scoring)[/green]"
        else:
            provider_colored = f"[bold green]{provider}[/bold green]"
            
        search_engine = config.get("search_engine", "duckduckgo").upper()
        if search_engine == "DUCKDUCKGO":
            search_colored = "[green]DUCKDUCKGO (HTML Scraping)[/green]"
        elif search_engine == "TAVILY":
            search_colored = "[green]TAVILY (AI Developer Search)[/green]"
        elif search_engine == "AI_GROUNDING":
            search_colored = "[bold green]AI GROUNDING (Gemini Search tool)[/bold green]"
        else:
            search_colored = f"[white]{search_engine}[/white]"
            
        discord_masked = config.get("discord_webhook")[:25] + "..." if config.get("discord_webhook") else "[yellow]Not Set[/yellow]"
        tg_token_masked = "•" * 15 if config.get("telegram_token") else "[yellow]Not Set[/yellow]"
        tg_chat_masked = config.get("telegram_chat_id") if config.get("telegram_chat_id") else "[yellow]Not Set[/yellow]"
        ua_masked = config.get("custom_user_agent")[:25] + "..." if config.get("custom_user_agent") else "[yellow]Not Set (Auto-detects Edge/Chrome)[/yellow]"
        
        auto_extract_status = "[green]Enabled[/green]" if config.get("auto_extract_cookies", False) else "[yellow]Disabled[/yellow]"
        browser_src_val = config.get("browser_source", "any").upper()
        cookie_map_count = len(config.get("universal_cookies", {}))
        cookie_map_status = f"[green]{cookie_map_count} domain(s) configured[/green]" if cookie_map_count > 0 else "[yellow]None[/yellow]"
        
        table.add_row("1", "Gemini API Key", gemini_masked)
        table.add_row("2", "OpenAI API Key", openai_masked)
        table.add_row("3", "Anthropic Claude API Key", anthropic_masked)
        table.add_row("4", "Tavily Search API Key", tavily_masked)
        table.add_row("5", "Preferred AI Provider", provider_colored)
        table.add_row("6", "Web Search Method", search_colored)
        table.add_row("7", "Discord Webhook URL", discord_masked)
        table.add_row("8", "Telegram Bot Token", tg_token_masked)
        table.add_row("9", "Telegram Chat ID", tg_chat_masked)
        table.add_row("10", "Default Search Max Results", str(config.get("default_max_results", 5)))
        table.add_row("11", "Custom User-Agent", ua_masked)
        table.add_row("12", "Auto-Extract Cookies", auto_extract_status)
        table.add_row("13", "Target Browser Source", browser_src_val)
        table.add_row("14", "Configure Universal Cookie Map", cookie_map_status)
        table.add_row("15", "Research Depth Mode", config.get("research_depth", "quick").upper())
        
        console.print(table)
        console.print("[cyan]Choose a setting to modify (1-15), or type [bold green]back[/bold green] to return to the main menu.[/cyan]")
        
        choice = Prompt.ask("Your selection", default="back")
        if choice.lower() == "back":
            break
            
        if choice == "1":
            key = Prompt.ask("Enter Gemini API Key (leave empty to clear)", password=True)
            config["gemini_api_key"] = key
        elif choice == "2":
            key = Prompt.ask("Enter OpenAI API Key (leave empty to clear)", password=True)
            config["openai_api_key"] = key
        elif choice == "3":
            key = Prompt.ask("Enter Anthropic Claude API Key (leave empty to clear)", password=True)
            config["anthropic_api_key"] = key
        elif choice == "4":
            key = Prompt.ask("Enter Tavily Search API Key (leave empty to clear)", password=True)
            config["tavily_api_key"] = key
        elif choice == "5":
            prov = Prompt.ask("Choose Preferred Provider (local, gemini, openai, anthropic)", choices=["local", "gemini", "openai", "anthropic"], default=config.get("preferred_provider", "local"))
            config["preferred_provider"] = prov
        elif choice == "6":
            se = Prompt.ask("Choose Search Engine (duckduckgo, tavily, ai_grounding)", choices=["duckduckgo", "tavily", "ai_grounding"], default=config.get("search_engine", "duckduckgo"))
            config["search_engine"] = se
        elif choice == "7":
            webhook = Prompt.ask("Enter Discord Webhook URL (leave empty to clear)")
            config["discord_webhook"] = webhook
        elif choice == "8":
            token = Prompt.ask("Enter Telegram Bot Token (leave empty to clear)", password=True)
            config["telegram_token"] = token
        elif choice == "9":
            chat_id = Prompt.ask("Enter Telegram Chat ID (leave empty to clear)")
            config["telegram_chat_id"] = chat_id
        elif choice == "10":
            max_r = Prompt.ask("Enter Default Max Results (1-10)", default="5")
            try:
                config["default_max_results"] = int(max_r)
            except ValueError:
                console.print("[red]Invalid number.[/red]")
                time.sleep(1)
                continue
        elif choice == "11":
            ua = Prompt.ask("Enter Custom User-Agent (leave empty to clear)")
            config["custom_user_agent"] = ua
        elif choice == "12":
            try:
                import rookiepy
                rookiepy_installed = True
            except ImportError:
                rookiepy_installed = False
                
            if not rookiepy_installed:
                console.print("\n[bold yellow]⚠ Warning: 'rookiepy' library is not installed.[/bold yellow]")
                console.print("Automated cookie extraction requires this library to decrypt local browser database files.")
                confirm = Prompt.ask("Would you like to try installing it automatically now? (y/n)", choices=["y", "n"], default="y")
                if confirm.lower() == "y":
                    console.print("[cyan]Running 'python -m pip install rookiepy'...[/cyan]")
                    os.system("python -m pip install rookiepy")
                    try:
                        import rookiepy
                        rookiepy_installed = True
                        console.print("[bold green]rookiepy installed successfully![/bold green]")
                        time.sleep(1)
                    except ImportError:
                        console.print("[red]Failed to install rookiepy automatically. Please run 'pip install rookiepy' in your terminal manually.[/red]")
                        time.sleep(3)
                        continue
                else:
                    continue
            
            if rookiepy_installed:
                auto_val = config.get("auto_extract_cookies", False)
                console.print("\n[bold red]⚠ WARNING:[/bold red] Enabling automatic cookie extraction will decrypt cookies from your local browser profile directories.")
                console.print("This is safe, but on some systems with strict corporate monitors, it can trigger heuristic antivirus warnings.")
                toggle = Prompt.ask("Enable auto-extraction?", choices=["yes", "no"], default="yes" if not auto_val else "no")
                config["auto_extract_cookies"] = (toggle == "yes")
        elif choice == "13":
            bs = Prompt.ask("Choose Browser Source for extraction (any, chrome, edge, firefox, brave)", choices=["any", "chrome", "edge", "firefox", "brave"], default=config.get("browser_source", "any"))
            config["browser_source"] = bs
        elif choice == "14":
            while True:
                console.clear()
                show_banner()
                universal_cookies = config.get("universal_cookies", {})
                
                table_cookies = Table(title="🌐 Universal Cookie Map", border_style="cyan")
                table_cookies.add_column("No.", style="cyan", justify="center")
                table_cookies.add_column("Domain", style="yellow")
                table_cookies.add_column("Cookie Value", style="white")
                
                domains = sorted(list(universal_cookies.keys()))
                for idx, dom in enumerate(domains):
                    val_masked = "•" * 15 if universal_cookies[dom] else "[red]Empty[/red]"
                    table_cookies.add_row(str(idx + 1), dom, val_masked)
                    
                console.print(table_cookies)
                console.print("[cyan]Select a domain number to edit/delete, type [bold green]add[/bold green] to configure a new domain, or type [bold green]back[/bold green] to return.[/cyan]")
                
                cookie_choice = Prompt.ask("Your selection", default="back")
                if cookie_choice.lower() == "back":
                    break
                elif cookie_choice.lower() == "add":
                    new_dom = Prompt.ask("Enter Domain Name (e.g. facebook.com, linkedin.com)").strip().lower()
                    if new_dom:
                        console.print("\n[bold red]⚠ WARNING:[/bold red] Using session cookies violates Terms of Service and can result in account suspension.")
                        new_cookie = Prompt.ask("Enter Cookie Value (e.g. c_user=...;)", password=True)
                        universal_cookies[new_dom] = new_cookie
                        config["universal_cookies"] = universal_cookies
                        config_manager.save_config(config)
                        console.print(f"[bold green]Added cookie for {new_dom} successfully![/bold green]")
                        time.sleep(1)
                else:
                    try:
                        val = int(cookie_choice)
                        if 1 <= val <= len(domains):
                            selected_dom = domains[val - 1]
                            console.print(f"\n[bold yellow]Selected Domain:[/bold yellow] {selected_dom}")
                            action = Prompt.ask("Choose action (edit, delete, back)", choices=["edit", "delete", "back"], default="edit")
                            if action == "edit":
                                console.print("\n[bold red]⚠ WARNING:[/bold red] Using session cookies violates Terms of Service.")
                                new_cookie = Prompt.ask("Enter new Cookie Value", password=True)
                                universal_cookies[selected_dom] = new_cookie
                                config["universal_cookies"] = universal_cookies
                                config_manager.save_config(config)
                                console.print(f"[bold green]Updated cookie for {selected_dom} successfully![/bold green]")
                                time.sleep(1)
                            elif action == "delete":
                                del universal_cookies[selected_dom]
                                config["universal_cookies"] = universal_cookies
                                config_manager.save_config(config)
                                console.print(f"[bold green]Deleted cookie for {selected_dom} successfully![/bold green]")
                                time.sleep(1)
                        else:
                            console.print("[red]Invalid domain number.[/red]")
                            time.sleep(1)
                    except ValueError:
                        console.print("[red]Please enter a valid choice.[/red]")
                        time.sleep(1)
            # Skip standard saved confirmation because it was handled inside the loop
            continue
        elif choice == "15":
            depth = Prompt.ask("Choose Research Depth (quick, deep)", choices=["quick", "deep"], default=config.get("research_depth", "quick"))
            config["research_depth"] = depth
        else:
            console.print("[red]Invalid choice.[/red]")
            time.sleep(1)
            continue
            
        config_manager.save_config(config)
        console.print("[bold green]Settings saved successfully![/bold green]")
        time.sleep(1.5)

def browse_reports_menu():
    """Menu to browse, view, and read saved markdown reports directly in the terminal."""
    while True:
        console.clear()
        show_banner()
        
        reports_dir = os.path.join("reports", "markdown")
        os.makedirs(reports_dir, exist_ok=True)
        os.makedirs(os.path.join("reports", "json"), exist_ok=True)
        os.makedirs(os.path.join("reports", "pdf"), exist_ok=True)
        os.makedirs(os.path.join("reports", "docx"), exist_ok=True)
        
        # Auto-migrate legacy files directly under reports/ into subfolders
        if os.path.exists("reports"):
            for legacy_md in glob.glob(os.path.join("reports", "*.md")):
                try:
                    os.rename(legacy_md, os.path.join(reports_dir, os.path.basename(legacy_md)))
                except Exception:
                    pass
            for legacy_json in glob.glob(os.path.join("reports", "*.json")):
                try:
                    os.rename(legacy_json, os.path.join("reports", "json", os.path.basename(legacy_json)))
                except Exception:
                    pass
            
        md_files = glob.glob(os.path.join(reports_dir, "*.md"))
        if not md_files:
            console.print("[yellow]No saved reports (*.md) found in reports/markdown/ directory.[/yellow]")
            Prompt.ask("Press Enter to go back")
            break
            
        # Sort files by last modified time (newest first)
        md_files.sort(key=os.path.getmtime, reverse=True)
        
        table = Table(title="📁 Generated Reports History", border_style="cyan")
        table.add_column("No.", style="yellow", justify="center")
        table.add_column("Filename", style="white")
        table.add_column("Created At", style="green")
        table.add_column("Size", style="magenta")
        
        for idx, filepath in enumerate(md_files):
            filename = os.path.basename(filepath)
            mtime = os.path.getmtime(filepath)
            created_at = datetime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
            size_kb = f"{os.path.getsize(filepath) / 1024:.1f} KB"
            table.add_row(str(idx + 1), filename, created_at, size_kb)
            
        console.print(table)
        console.print("[cyan]Enter report number to read it, or type [bold green]back[/bold green] to return.[/cyan]")
        
        choice = Prompt.ask("Your selection", default="back")
        if choice.lower() == "back":
            break
            
        try:
            val = int(choice)
            if 1 <= val <= len(md_files):
                selected_file = md_files[val - 1]
                with open(selected_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                console.clear()
                console.print(Panel(f"[bold yellow]Reading File:[/bold yellow] {os.path.basename(selected_file)}", border_style="yellow"))
                console.print(Markdown(content))
                console.print("\n" + "="*80)
                Prompt.ask("Press Enter to return to reports list")
            else:
                console.print("[red]Invalid report number.[/red]")
                time.sleep(1)
        except ValueError:
            console.print("[red]Please enter a valid number or 'back'.[/red]")
            time.sleep(1)

def calculate_scraped_hash(scraped_data: List[Dict[str, Any]]) -> str:
    """
    Generates a unique MD5 hash representing the current scraped data content and URLs.
    """
    # Filter only successful scrapes and sort by URL to ensure stable order
    valid_data = sorted([d for d in scraped_data if d.get("success")], key=lambda x: x["url"])
    fingerprint_parts = []
    for d in valid_data:
        fingerprint_parts.append(d["url"])
        fingerprint_parts.append(d.get("raw_text", ""))
    
    fingerprint_str = "||".join(fingerprint_parts)
    return hashlib.md5(fingerprint_str.encode("utf-8")).hexdigest()

def execute_scrape_flow(
    query: str, 
    spec_topic: str, 
    urls: List[str], 
    config: Dict[str, Any], 
    previous_hash: Optional[str] = None,
    previous_report_path: Optional[str] = None
) -> Tuple[Optional[str], str, Optional[str]]:
    """Core logic to search, scrape, analyze, and notify."""
    logger.info("Initializing scrape flow execution for query: '%s', focus: '%s'", query, spec_topic)
    search_engine = config.get("search_engine", "duckduckgo")
    gemini_key = config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    
    # ─── PATH A: AI SEARCH GROUNDING ──────────────────────────────────────────
    if search_engine == "ai_grounding" and not urls:
        if not gemini_key:
            console.print("[yellow]⚠ Warning: AI Search Grounding requires a Gemini API Key. Falling back to local crawler...[/yellow]")
        else:
            logger.info("Triggering Path A: AI Search Grounding search...")
            with console.status("[bold cyan]Google AI Search Grounding (Live)...[/bold cyan]"):
                res = analyzer.generate_gemini_grounding_search(query, spec_topic, gemini_key)
                
            if res["success"]:
                console.print(f"[green]✔ AI Grounding search complete![/green]")
                logger.info("AI Search Grounding successful. Caching response report.")
                if res["queries"]:
                    console.print(f"[dim]Search queries executed: {', '.join(res['queries'])}[/dim]")
                
                # Dispatch Notifications and save files
                with console.status("[bold cyan]Saving report and dispatching notification triggers...[/bold cyan]"):
                    scraped_data_mock = [{"url": f"Google Search: {q}", "title": q, "success": True, "raw_text": "Grounding Source"} for q in res["queries"]]
                    dispatch_res = notifier.dispatch_notifications(query, spec_topic, res["report"], scraped_data_mock, config)
                    
                console.print(f"[bold green]✔ Saved Markdown Report to: {dispatch_res['saved_paths']['markdown_path']}[/bold green]")
                console.print(f"[bold green]✔ Saved Raw Data JSON to: {dispatch_res['saved_paths']['json_path']}[/bold green]")
                
                if dispatch_res["discord"]:
                    console.print("[green]✔ Discord webhook alert dispatched successfully![/green]")
                if dispatch_res["telegram"]:
                    console.print("[green]✔ Telegram notification dispatched successfully![/green]")
                    
                return res["report"], "", dispatch_res['saved_paths']['markdown_path']
            else:
                logger.error("AI Search Grounding failed: %s. Falling back to normal crawler.", res.get('error'))
                console.print(f"[red]❌ AI Search Grounding failed: {res['error']}. Falling back to normal crawler...[/red]")

    # ─── PATH B: NORMAL SCRAping and CRAWLING ─────────────────────────────────
    scraped_data = []
    
    # Phase 1: Search engine query if no explicit URLs provided
    if not urls:
        max_res = config.get("default_max_results", 5)
        tavily_key = config.get("tavily_api_key") or os.environ.get("TAVILY_API_KEY")
        engine_name = "Tavily Search API" if (search_engine == "tavily" and tavily_key) else "DuckDuckGo"
        
        # Check research depth config
        research_depth = config.get("research_depth", "quick")
        search_results = []
        seen_urls = set()
        
        if research_depth == "deep":
            sub_queries = utils.decompose_query_locally(query)
            console.print(f"\n[bold cyan]🔍 Deep Research Mode: Decomposed query into {len(sub_queries)} search aspects:[/bold cyan]")
            for sq in sub_queries:
                console.print(f"  • [yellow]{sq}[/yellow]")
            console.print("")
            
            # Query for a slightly smaller candidate pool size per query, and aggregate
            candidate_pool_size = max(3, max_res)
            
            for idx, sq in enumerate(sub_queries):
                if idx > 0:
                    # Rate limiting precaution sleep between sub-queries
                    time.sleep(1.0)
                with console.status(f"[bold cyan]({idx+1}/{len(sub_queries)}) Searching {engine_name} for: '{sq}'...[/bold cyan]"):
                    if engine_name == "Tavily Search API":
                        res = scraper.search_tavily(sq, tavily_key, max_results=candidate_pool_size)
                    else:
                        res = scraper.search_duckduckgo(sq, max_results=candidate_pool_size)
                if res:
                    for item in res:
                        url = item["url"]
                        if url not in seen_urls:
                            seen_urls.add(url)
                            search_results.append(item)
        else:
            # Default quick mode: single query
            candidate_pool_size = max_res * 3
            with console.status(f"[bold cyan]Searching {engine_name} for: '{query}'...[/bold cyan]"):
                if engine_name == "Tavily Search API":
                    search_results = scraper.search_tavily(query, tavily_key, max_results=candidate_pool_size)
                else:
                    search_results = scraper.search_duckduckgo(query, max_results=candidate_pool_size)
            
        if not search_results:
            logger.warning("No search results returned from search query.")
            console.print("[bold red]❌ No search results found. Check connection or try another topic.[/bold red]")
            return "", ""
            
        console.print(f"[green]✔ Found {len(search_results)} unique candidate search results via {engine_name}.[/green]")
        target_urls = [r["url"] for r in search_results]
    else:
        logger.info("Explicit URL list passed to execution flow: %s", str(urls))
        target_urls = urls
        search_results = [{"title": f"Manual URL {i+1}", "url": url, "snippet": ""} for i, url in enumerate(urls)]
        
    # Phase 2: Scrape URLs
    logger.info("Proceeding to Phase 2: Crawler scraping on %d target URLs.", len(target_urls))
    with console.status("[bold cyan]Fetching and parsing target websites...[/bold cyan]") as status:
        scraped_count = [0]

        def update_status(url: str):
            scraped_count[0] += 1
            status.update(f"[bold cyan]({scraped_count[0]} scraped) Finished: {url[:60]}...[/bold cyan]")

        target_count = len(target_urls) if urls else max_res
        scraped_data = scraper.scrape_urls_adaptive(search_results, target_count=target_count, timeout=15, status_callback=update_status)
            
    # Print scraping summary
    table = Table(title="📊 Scraping Completion Status", border_style="cyan")
    table.add_column("No.", style="yellow")
    table.add_column("URL Target", style="white")
    table.add_column("Status", style="green")
    table.add_column("Content Length", style="magenta")
    
    for idx, data in enumerate(scraped_data):
        if not data["success"]:
            success_str = f"[red]FAILED ({data.get('error')})[/red]"
        elif data.get("cached"):
            success_str = "[cyan]SUCCESS (CACHED)[/cyan]"
        else:
            success_str = "[green]SUCCESS (LIVE)[/green]"
            
        char_count = len(data.get("raw_text", ""))
        table.add_row(str(idx + 1), data["url"][:60] + "...", success_str, f"{char_count} chars")
        
    console.print(table)
    
    if not any(d["success"] for d in scraped_data):
        logger.warning("Crawler was unable to scrape text from any of the candidate URLs.")
        console.print("[bold red]❌ Failed to retrieve content from any of the target sites.[/bold red]")
        return "", ""
        
    # Calculate state hash to check for incremental changes
    current_hash = calculate_scraped_hash(scraped_data)
    logger.info("Calculated current scraped content hash: %s", current_hash)
    
    if previous_hash is not None and current_hash == previous_hash:
        logger.info("Incremental check: Current scraped content matches previous run hash (%s). Skipping LLM generation.", current_hash)
        return None, current_hash, previous_report_path
        
    # Phase 3: Synthesis & Analysis
    logger.info("Proceeding to Phase 3: LLM Synthesis and Analysis.")
    previous_report_content = None
    if previous_report_path and os.path.exists(previous_report_path):
        try:
            with open(previous_report_path, "r", encoding="utf-8") as f:
                previous_report_content = f.read()
        except Exception as e:
            logger.warning("Failed to read previous report for incremental update: %s", str(e))
            
    with console.status("[bold cyan]Analyzing web content and synthesizing report...[/bold cyan]"):
        report = analyzer.synthesize_topics(scraped_data, query, spec_topic, previous_report=previous_report_content)
        
    # Phase 4: Dispatch Notifications and save files
    logger.info("Proceeding to Phase 4: Notification dispatch and report saving.")
    with console.status("[bold cyan]Saving report and dispatching notification triggers...[/bold cyan]"):
        dispatch_res = notifier.dispatch_notifications(query, spec_topic, report, scraped_data, config, previous_report_path=previous_report_path)
        
    console.print(f"[bold green]✔ Saved Markdown Report to: {dispatch_res['saved_paths']['markdown_path']}[/bold green]")
    console.print(f"[bold green]✔ Saved Raw Data JSON to: {dispatch_res['saved_paths']['json_path']}[/bold green]")
    if dispatch_res['saved_paths'].get('pdf_path'):
        console.print(f"[bold green]✔ Saved PDF Document to: {dispatch_res['saved_paths']['pdf_path']}[/bold green]")
    if dispatch_res['saved_paths'].get('docx_path'):
        console.print(f"[bold green]✔ Saved Word (DOCX) Document to: {dispatch_res['saved_paths']['docx_path']}[/bold green]")
    
    if dispatch_res["discord"]:
        console.print("[green]✔ Discord webhook alert dispatched successfully![/green]")
    if dispatch_res["telegram"]:
        console.print("[green]✔ Telegram notification dispatched successfully![/green]")
        
    return report, current_hash, dispatch_res['saved_paths']['markdown_path']

def single_scrape_menu():
    """Handles the user inputs to trigger a single scrape and deep dive run."""
    config = config_manager.load_config()
    
    console.clear()
    show_banner()
    console.print("[bold green]=== Run Deep-Dive Scraper ===[/bold green]\n")
    
    # 1. Ask about Saved Searches
    saved_searches = config.get("saved_searches", [])
    query = ""
    spec_topic = ""
    
    if saved_searches:
        load_saved = Confirm.ask("Would you like to load a previously saved search configuration?")
        if load_saved:
            table = Table(title="💾 Saved Search Presets", border_style="cyan")
            table.add_column("No.", style="yellow", justify="center")
            table.add_column("Query", style="white")
            table.add_column("Focus Area", style="green")
            
            for idx, item in enumerate(saved_searches):
                table.add_row(str(idx + 1), item["query"], item["spec_topic"])
                
            console.print(table)
            preset_idx = Prompt.ask("Choose preset index", default="1")
            try:
                val = int(preset_idx)
                if 1 <= val <= len(saved_searches):
                    query = saved_searches[val - 1]["query"]
                    spec_topic = saved_searches[val - 1]["spec_topic"]
                    console.print(f"[green]Loaded preset: '{query}' -> '{spec_topic}'[/green]\n")
            except ValueError:
                console.print("[red]Invalid index, entering details manually...[/red]\n")
                
    if not query:
        query = Prompt.ask("🔍 What topic or query would you like to search and scrape?")
        spec_topic = Prompt.ask("🎯 Describe the specific details, answers, or data you are looking for")
        
    # 2. Ask about manual URL inputs vs Search
    url_input_confirm = Confirm.ask("Do you want to provide manual target URL(s) to scrape directly instead of web search?", default=False)
    urls = []
    if url_input_confirm:
        urls_str = Prompt.ask("Enter URL(s) separated by commas or spaces")
        urls = [u.strip() for u in urls_str.replace(",", " ").split() if u.strip().startswith("http")]
        if not urls:
            console.print("[red]No valid URLs found, reverting to web search mode.[/red]")
            
    # Run the core flow
    execute_scrape_flow(query, spec_topic, urls, config)
    
    # Option to save search configuration
    if not saved_searches or {"query": query, "spec_topic": spec_topic} not in saved_searches:
        save_preset = Confirm.ask("Save this search configuration as a preset for the future?", default=True)
        if save_preset:
            config_manager.add_saved_search(query, spec_topic)
            console.print("[green]Saved to presets![/green]")
            
    Prompt.ask("\nPress Enter to return to main menu")

def scheduler_menu():
    """Enables automated recurring scrapers directly within the terminal loop."""
    config = config_manager.load_config()
    
    console.clear()
    show_banner()
    console.print("[bold green]=== Schedule Recurring Scrapes (Automated Loop) ===[/bold green]\n")
    
    query = Prompt.ask("🔍 What topic/query would you like to monitor?")
    spec_topic = Prompt.ask("🎯 Focus Area (specific answers/details needed)")
    
    interval_m = Prompt.ask("⏱️ Enter loop interval duration in MINUTES", default="15")
    try:
        interval_sec = max(30, int(interval_m) * 60) # minimum 30 seconds to prevent spam
    except ValueError:
        console.print("[red]Invalid integer. Defaulting to 15 minutes.[/red]")
        interval_sec = 15 * 60
        
    logger.info("Scheduler configured: query='%s', focus='%s', interval=%.2f minutes", query, spec_topic, interval_sec / 60)
    console.print(f"\n[bold yellow]📅 Starting automation loop...[/bold yellow]")
    console.print(f"Monitor Topic: [cyan]'{query}'[/cyan]")
    console.print(f"Interval: [cyan]{interval_sec / 60:.1f} minutes[/cyan]")
    console.print("[bold red]Press Ctrl+C to terminate the automation loop at any time.[/bold red]\n")
    
    run_count = 0
    last_run_hashes = {}
    last_run_paths = {}
    query_key = f"{query}||{spec_topic}"
    try:
        while True:
            run_count += 1
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            logger.info("Scheduler: Launching automated run #%d for key '%s'", run_count, query_key)
            console.print(f"[bold cyan]🔄 [{timestamp}] Launching automated scrape run #{run_count}...[/bold cyan]")
            
            try:
                prev_hash = last_run_hashes.get(query_key)
                prev_path = last_run_paths.get(query_key)
                report, new_hash, report_path = execute_scrape_flow(query, spec_topic, [], config, previous_hash=prev_hash, previous_report_path=prev_path)
                last_run_hashes[query_key] = new_hash
                if report_path:
                    last_run_paths[query_key] = report_path
                
                if report is None:
                    logger.info("Scheduler: Run #%d complete. No new content changes detected. Webhooks bypassed.", run_count)
                    console.print(f"[yellow]✔ Run #{run_count} complete. No new changes detected. Skipping report generation & notifications.[/yellow]")
                else:
                    logger.info("Scheduler: Run #%d complete. New changes detected. Webhooks dispatched.", run_count)
                    console.print(f"[green]✔ Run #{run_count} finished successfully at {time.strftime('%H:%M:%S')}.[/green]")
            except Exception as e:
                logger.error("Scheduler exception during run #%d: %s", run_count, str(e))
                console.print(f"[red]❌ Error occurred during run #{run_count}: {str(e)}[/red]")
                
            logger.info("Scheduler entering idle sleep state for %.2f minutes...", interval_sec / 60)
            console.print(f"[dim]Waiting {interval_sec / 60:.1f} minutes before next run. Press Ctrl+C to exit.[/dim]\n")
            
            # Sleep in small blocks to allow responsive keyboard interrupts
            slept = 0
            while slept < interval_sec:
                time.sleep(1)
                slept += 1
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠ Automation scheduler halted by user. Returning to main menu.[/bold yellow]")
        time.sleep(2)

def sitemap_scanner_menu():
    """Menu to scan a domain's XML sitemap for public URLs and optionally scrape them."""
    console.clear()
    show_banner()
    console.print("[bold green]=== XML Sitemap Scanner & Crawl ===[/bold green]\n")
    
    domain = Prompt.ask("🌐 Enter domain name to scan (e.g., netflixtechblog.com)")
    domain = domain.strip().lower()
    
    # Strip protocol prefix if user typed it
    if domain.startswith("http://"):
        domain = domain[7:]
    elif domain.startswith("https://"):
        domain = domain[8:]
    if "/" in domain:
        domain = domain.split("/")[0]
        
    config = config_manager.load_config()
    max_urls = config.get("default_max_results", 5)
    
    with console.status(f"[bold cyan]Scanning sitemaps on '{domain}'...[/bold cyan]"):
        urls = scraper.scan_sitemap_urls(domain, max_urls=max_urls * 3)
        
    if not urls:
        console.print(f"[bold red]❌ No public URLs found in sitemaps for domain: {domain}[/bold red]")
        Prompt.ask("\nPress Enter to return to main menu")
        return
        
    console.print(f"[green]✔ Discovered {len(urls)} public URLs in sitemaps![/green]\n")
    
    table = Table(title=f"🌐 Sitemap URLs on {domain}", border_style="cyan")
    table.add_column("No.", style="yellow", justify="center")
    table.add_column("URL Target", style="white")
    
    for idx, url in enumerate(urls[:max_urls]):
        table.add_row(str(idx + 1), url)
    console.print(table)
    
    if len(urls) > max_urls:
        console.print(f"[dim]... and {len(urls) - max_urls} more URLs found.[/dim]\n")
        
    scrape_now = Confirm.ask(f"Would you like to fetch and analyze the top {min(len(urls), max_urls)} URLs now?", default=True)
    if scrape_now:
        spec_topic = Prompt.ask("🎯 Describe specific details or topic you are researching from these pages")
        target_urls = urls[:max_urls]
        
        # Invoke core execute_scrape_flow using our sitemap URLs directly!
        execute_scrape_flow(f"Sitemap: {domain}", spec_topic, target_urls, config)
        
    Prompt.ask("\nPress Enter to return to main menu")

def main():
    """Main application loop."""
    while True:
        try:
            console.clear()
            show_banner()
            
            table = Table(box=None, padding=(0, 2), show_header=False)
            table.add_column("Option", style="cyan bold")
            table.add_column("Description", style="white")
            
            table.add_row("1.", "🔍 Run Scraper & Notifier (Single deep-dive run)")
            table.add_row("2.", "⏱️ Start Automation (Recurring scheduled scrapes)")
            table.add_row("3.", "🌐 Scan XML Sitemap (Domain URL extraction)")
            table.add_row("4.", "⚙️ Configure API Keys & Settings")
            table.add_row("5.", "📁 Browse Saved Reports History")
            table.add_row("6.", "❌ Exit")
            
            menu_panel = Panel(
                table,
                title="[bold green]Main Navigation Menu[/bold green]",
                border_style="green",
                padding=(1, 1)
            )
            console.print(menu_panel)
            
            choice = Prompt.ask("Choose an option (1-6)", choices=["1", "2", "3", "4", "5", "6"], default="1")
            
            if choice == "1":
                single_scrape_menu()
            elif choice == "2":
                scheduler_menu()
            elif choice == "3":
                sitemap_scanner_menu()
            elif choice == "4":
                configure_settings_menu()
            elif choice == "5":
                browse_reports_menu()
            elif choice == "6":
                console.print("\n[bold green]Thank you for using Automated Web Scraper & Notifier. Goodbye![/bold green]\n")
                break
        except KeyboardInterrupt:
            console.print("\n[bold green]Exiting application...[/bold green]\n")
            break

if __name__ == "__main__":
    main()
