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
from typing import List, Dict, Any

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

console = Console()

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
        subtitle="V1.0.0 • Local extractive summarizer & AI Engine ready"
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
        
        console.print(table)
        console.print("[cyan]Choose a setting to modify (1-10), or type [bold green]back[/bold green] to return to the main menu.[/cyan]")
        
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
        
        reports_dir = "reports"
        if not os.path.exists(reports_dir):
            console.print("[yellow]No reports directory found. Run a scraper session first![/yellow]")
            Prompt.ask("Press Enter to go back")
            break
            
        md_files = glob.glob(os.path.join(reports_dir, "*.md"))
        if not md_files:
            console.print("[yellow]No saved reports (*.md) found in reports/ directory.[/yellow]")
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

def execute_scrape_flow(query: str, spec_topic: str, urls: List[str], config: Dict[str, Any]) -> str:
    """Core logic to search, scrape, analyze, and notify."""
    search_engine = config.get("search_engine", "duckduckgo")
    gemini_key = config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    
    # ─── PATH A: AI SEARCH GROUNDING ──────────────────────────────────────────
    if search_engine == "ai_grounding" and not urls:
        if not gemini_key:
            console.print("[yellow]⚠ Warning: AI Search Grounding requires a Gemini API Key. Falling back to local crawler...[/yellow]")
        else:
            with console.status("[bold cyan]Google AI Search Grounding (Live)...[/bold cyan]"):
                res = analyzer.generate_gemini_grounding_search(query, spec_topic, gemini_key)
                
            if res["success"]:
                console.print(f"[green]✔ AI Grounding search complete![/green]")
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
                    
                return res["report"]
            else:
                console.print(f"[red]❌ AI Search Grounding failed: {res['error']}. Falling back to normal crawler...[/red]")

    # ─── PATH B: NORMAL SCRAping and CRAWLING ─────────────────────────────────
    scraped_data = []
    
    # Phase 1: Search engine query if no explicit URLs provided
    if not urls:
        max_res = config.get("default_max_results", 5)
        tavily_key = config.get("tavily_api_key") or os.environ.get("TAVILY_API_KEY")
        engine_name = "Tavily Search API" if (search_engine == "tavily" and tavily_key) else "DuckDuckGo"
        
        with console.status(f"[bold cyan]Searching {engine_name} for: '{query}'...[/bold cyan]"):
            if engine_name == "Tavily Search API":
                search_results = scraper.search_tavily(query, tavily_key, max_results=max_res)
            else:
                search_results = scraper.search_duckduckgo(query, max_results=max_res)
            
        if not search_results:
            console.print("[bold red]❌ No search results found. Check connection or try another topic.[/bold red]")
            return ""
            
        console.print(f"[green]✔ Found {len(search_results)} search results via {engine_name}.[/green]")
        target_urls = [r["url"] for r in search_results]
    else:
        target_urls = urls
        search_results = [{"title": f"Manual URL {i+1}", "url": url, "snippet": ""} for i, url in enumerate(urls)]
        
    # Phase 2: Scrape URLs
    with console.status("[bold cyan]Fetching and parsing target websites...[/bold cyan]") as status:
        scraped_count = [0]

        def update_status(url: str):
            scraped_count[0] += 1
            status.update(f"[bold cyan]({scraped_count[0]}/{len(target_urls)}) Finished Scraping: {url[:60]}...[/bold cyan]")

        scraped_data = scraper.scrape_urls_concurrently(target_urls, timeout=15, status_callback=update_status)
            
    # Print scraping summary
    table = Table(title="📊 Scraping Completion Status", border_style="cyan")
    table.add_column("No.", style="yellow")
    table.add_column("URL Target", style="white")
    table.add_column("Status", style="green")
    table.add_column("Content Length", style="magenta")
    
    for idx, data in enumerate(scraped_data):
        success_str = "[green]SUCCESS[/green]" if data["success"] else f"[red]FAILED ({data.get('error')})[/red]"
        char_count = len(data.get("raw_text", ""))
        table.add_row(str(idx + 1), data["url"][:60] + "...", success_str, f"{char_count} chars")
        
    console.print(table)
    
    if not any(d["success"] for d in scraped_data):
        console.print("[bold red]❌ Failed to retrieve content from any of the target sites.[/bold red]")
        return ""
        
    # Phase 3: Synthesis & Analysis
    with console.status("[bold cyan]Analyzing web content and synthesizing report...[/bold cyan]"):
        report = analyzer.synthesize_topics(scraped_data, query, spec_topic)
        
    # Phase 4: Dispatch Notifications and save files
    with console.status("[bold cyan]Saving report and dispatching notification triggers...[/bold cyan]"):
        dispatch_res = notifier.dispatch_notifications(query, spec_topic, report, scraped_data, config)
        
    console.print(f"[bold green]✔ Saved Markdown Report to: {dispatch_res['saved_paths']['markdown_path']}[/bold green]")
    console.print(f"[bold green]✔ Saved Raw Data JSON to: {dispatch_res['saved_paths']['json_path']}[/bold green]")
    
    if dispatch_res["discord"]:
        console.print("[green]✔ Discord webhook alert dispatched successfully![/green]")
    if dispatch_res["telegram"]:
        console.print("[green]✔ Telegram notification dispatched successfully![/green]")
        
    return report

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
        
    console.print(f"\n[bold yellow]📅 Starting automation loop...[/bold yellow]")
    console.print(f"Monitor Topic: [cyan]'{query}'[/cyan]")
    console.print(f"Interval: [cyan]{interval_sec / 60:.1f} minutes[/cyan]")
    console.print("[bold red]Press Ctrl+C to terminate the automation loop at any time.[/bold red]\n")
    
    run_count = 0
    try:
        while True:
            run_count += 1
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            console.print(f"[bold cyan]🔄 [{timestamp}] Launching automated scrape run #{run_count}...[/bold cyan]")
            
            try:
                execute_scrape_flow(query, spec_topic, [], config)
                console.print(f"[green]✔ Run #{run_count} finished successfully at {time.strftime('%H:%M:%S')}.[/green]")
            except Exception as e:
                console.print(f"[red]❌ Error occurred during run #{run_count}: {str(e)}[/red]")
                
            console.print(f"[dim]Waiting {interval_sec / 60:.1f} minutes before next run. Press Ctrl+C to exit.[/dim]\n")
            
            # Sleep in small blocks to allow responsive keyboard interrupts
            slept = 0
            while slept < interval_sec:
                time.sleep(1)
                slept += 1
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠ Automation scheduler halted by user. Returning to main menu.[/bold yellow]")
        time.sleep(2)

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
            table.add_row("3.", "⚙️ Configure API Keys & Settings")
            table.add_row("4.", "📁 Browse Saved Reports History")
            table.add_row("5.", "❌ Exit")
            
            menu_panel = Panel(
                table,
                title="[bold green]Main Navigation Menu[/bold green]",
                border_style="green",
                padding=(1, 1)
            )
            console.print(menu_panel)
            
            choice = Prompt.ask("Choose an option (1-5)", choices=["1", "2", "3", "4", "5"], default="1")
            
            if choice == "1":
                single_scrape_menu()
            elif choice == "2":
                scheduler_menu()
            elif choice == "3":
                configure_settings_menu()
            elif choice == "4":
                browse_reports_menu()
            elif choice == "5":
                console.print("\n[bold green]Thank you for using Automated Web Scraper & Notifier. Goodbye![/bold green]\n")
                break
        except KeyboardInterrupt:
            console.print("\n[bold green]Exiting application...[/bold green]\n")
            break

if __name__ == "__main__":
    main()
