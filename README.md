```text
░██████████                                 ░██    ░██     ░██                                                         ░██    
░██                                         ░██    ░██     ░██                                                         ░██    
░██         ░███████   ░███████   ░██████   ░██    ░██     ░██  ░██████   ░██░████ ░██    ░██  ░███████   ░███████  ░████████ 
░█████████ ░██    ░██ ░██    ░██       ░██  ░██    ░██████████       ░██  ░███     ░██    ░██ ░██    ░██ ░██           ░██    
░██        ░██    ░██ ░██         ░███████  ░██    ░██     ░██  ░███████  ░██       ░██  ░██  ░█████████  ░███████     ░██    
░██        ░██    ░██ ░██    ░██ ░██   ░██  ░██    ░██     ░██ ░██   ░██  ░██        ░██░██   ░██               ░██    ░██    
░██         ░███████   ░███████   ░█████░██ ░██    ░██     ░██  ░█████░██ ░██         ░███     ░███████   ░███████      ░████
```

# Focal Harvest

Allows you to conduct clean web research, scrape search engine results or any custom URL, perform rule-based text synthesis, or use the advanced AI capabilities with Gemini, to generate reports accessible within your terminal, and even send automatic notifications to Discord or Telegram.

---

## Capabilities Overview

1. ***Interactive Guided Setup***: Let the CLI lead you through setting up your search query, focusing your research, and selecting your sources.

2. ***Flexible Search & Scraping Methods***: Choose your scraping method from:
    - **AI Search Grounding**: Unleash Gemini's Google Search tool to scrape the live web, analyze the results, and write the report—all without touching a local HTML file.
    - **Tavily Search API**: Integrate advanced AI-optimized search results for superior query handling.
    - **DuckDuckGo**: Leverage free HTML crawl-based searching if others aren't available.
3. ***Advanced Text Extraction & Boilerplate Removal***: Efficiently sanitize HTML by stripping away navigation bars, headers, footers, forms, scripts, and styles to isolate key headers and paragraphs.

4. ***Flexible Text Synthesis Engine***:

    - **Local Extractive Summarizer**: Utilizes intelligent ranking based on sentence density, query keyword relevance, and position within the text—no API keys required!
    - **AI-Powered Synthesizer**: Integrates directly with Google Gemini (Gemini 1.5 Flash), OpenAI (GPT-4o-mini), and Anthropic Claude (Claude 3.5 Sonnet) via simple HTTP POST requests to summarize your findings, supporting an API key for enhanced capabilities.

5. ***Versatile Notification System***:

    - **Real-time Terminal Output**: Display your formatted Markdown reports directly in your terminal with the help of the Rich library.
    - **Local Exporting** : Save your synthesised reports as .md files and the raw scraped text as .json files to a well-organized reports/ directory.
    - **Discord Webhooks** : Post formatted embed cards with execution details and summary snippets to your Discord channel.
    - **Telegram Alerts** : Push concise summary alerts to your Telegram channel using a dedicated bot.
6. ***Built-in Scheduler***: Set up recurring scraping jobs to monitor topics at specified intervals, ensuring you're always up-to-date.
7. ***Local Report History Browser***: Easily revisit, read, and search your previously generated reports directly within the application—no need to leave your terminal!

---

## Architecture Breakdown

The project is neatly organized into modular Python files:

* ***[requirements.txt]()***: Python external package dependencies.
* ***[main.py]()***: The main interactive interface that handles menu navigation, scheduling, and orchestrates the workflow.
* ***[scraper.py]()***: Manages web requests, directs traffic between search methods (Tavily/DuckDuckGo), and performs the HTML text extraction.
* ***[analyzer.py]()***: Houses the local extractive text ranking algorithm and the logic for integrating with various AI providers.
* ***[notifier.py]()***: Contains functionality for exporting reports, rendering them in the terminal using Rich, and sending out notifications via Discord and Telegram webhooks.
* ***[config_manager.py]()***: Responsible for saving and loading user configurations and API keys, typically stored in `config.json` or as environment variables.


---

## Installation and Setup

### Step 1: Install Dependencies

Ensure you have Python 3.12 or higher installed on your system. Open your terminal in the project's root directory and run the following command:

```bash
pip install -r requirements.txt
```

### Step 2: Configure Credentials (Optional)

You have two primary methods for setting up your API keys and notification settings:
- ***In-App Configuration*** : After launching the CLI, navigate to menu option 3 to set your keys, choose your preferred AI provider, and configure notification hooks.
- ***Environment Variables*** : Alternatively, set standard environment parameters or define them in your environment:
  - `GEMINI_API_KEY`: Your Gemini API key.
  - `OPENAI_API_KEY`: Your OpenAI API key.
  - `ANTHROPIC_API_KEY`: Your Anthropic API key.
  - `TAVILY_API_KEY`: Your Tavily API key (upgrades search performance).
  - `DISCORD_WEBHOOK_URL`: A Discord channel webhook URL.
  - `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: Telegram bot API credentials.
---

## How to Use

Launch the main interactive application from your terminal by executing:

```bash
python main.py
```

## Main Navigation Menu

Upon launching, you'll be presented with the following options:

1.  ***Run Scraper & Notifier*** *(Single Deep-Dive Run)* : This will initiate a single, comprehensive scrape of your chosen topic or URL. It then generates a detailed Markdown report, saves the raw data as JSON, and sends out notifications to your configured channels.
2.  ***Start Automation*** *(Recurring Scheduled Scrapes)* : Begin a continuous monitoring process that scrapes your topic at a user-defined interval (minutes or hours) and notifies you of any significant changes or updates.
3.  ***Configure API Keys & Settings*** : Access a sub-menu to input and save your API keys, set the maximum number of results for searches, and manage your notification webhook URLs.
4.  ***Browse Saved Reports History*** : Explore all your previously generated reports. The app will render the Markdown in your terminal for easy reading and searching.

5.  ***Exit*** : Gracefully terminate the application.

---

## Output format

All generated reports are stored in a `reports/` directory within the project. Each report consists of two files:
*   `reports/report<queryslug>_<timestamp>.md`: The synthesized deep-dive research summary, formatted for readability.
*   `reports/rawdata<queryslug><timestamp>.json`: A backup file containing the complete raw scraped page titles, URLs, and textual content.
