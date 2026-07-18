# 📚 Focal Harvest: Project Explainer & Walkthrough

This document provides a detailed walkthrough of the **Focal Harvest** project. It outlines the core mechanics of the application and demonstrates how each of the 4 menu options operates using a concrete research example: **"Gemini 1.5 Flash vs Gemini 1.5 Pro"**.


---

## 🔍 Example Scenario Details

To illustrate the application's capabilities, we will use the following research settings:
* **Search Query**: `Gemini 1.5 Flash vs Gemini 1.5 Pro`
* **Focus Area (Specific Details)**: `Compare context window size, token pricing, response latency, and recommended developer use cases.`

---

## 🛠️ Menu Walkthrough

When you start the application (`python main.py`), you are greeted by the main navigation console:

```
+-------------------------------------------------------------+
|                     MAIN NAVIGATION MENU                     |
+-------------------------------------------------------------+
| 1. Run Scraper & Notifier (Single deep-dive run)            |
| 2. Start Automation (Recurring scheduled scrapes)           |
| 3. Configure API Keys & Settings                            |
| 4. Browse Saved Reports History                             |
| 5. Exit                                                     |
+-------------------------------------------------------------+
```

Here is a step-by-step breakdown of how each option processes our example topic.

---

### 1️⃣ Option 1: Run Scraper & Notifier (Single Deep-Dive Run)

This option performs a real-time web search (or direct website crawl), parses retrieved text, scores relevant sections, and exports structured reports.

#### Step-by-Step Flow:
1. **Selection**: Select `1` in the main menu.
2. **Query Inputs**:
   * *Query*: `Gemini 1.5 Flash vs Gemini 1.5 Pro`
   * *Focus*: `Compare context window size, token pricing, response latency, and recommended developer use cases.`
3. **Source Method**: Prompt: *Do you want to provide manual target URL(s)? [y/N]*. Choose **`N`** to search the web automatically.
4. **Processing**:
   * **Phase 1: Search Engine Scraping**: Connects to the search interface and fetches the top results.
   * **Phase 2: Content Parsing**: Requests and scrapes target sites (e.g. Google Cloud Blogs, developer forums, tech documentation), removing boilerplate tags.
   * **Phase 3: Synthesis & Analysis**: Combines text blocks. Scores sentences using keyword density matching and document weightings.
   * **Phase 4: Exporters & Notifications**: Saves files to `reports/`, renders the report on the terminal, and fires notifications.

#### What the Saved Report Look Like:
Below is an example of the resulting Markdown report (`reports/report_gemini_1_5_flash_vs_gemini_1_20260621.md`):

```markdown
# Deep Dive Report: Gemini 1.5 Flash vs Gemini 1.5 Pro
**Focus Area:** Compare context window size, token pricing, response latency, and recommended developer use cases.

## Executive Summary
- Gemini 1.5 Pro is Google's mid-size multimodal model, optimized for complex reasoning, planning, and coding tasks. *(Source: Google Developers)*
- Gemini 1.5 Flash is a high-speed, lightweight model engineered for high volume, lower latency, and cost-efficiency at scale. *(Source: Google Cloud)*
- Both models feature a native 1-million token context window, with 1.5 Pro scaling up to 2 million tokens for select enterprise workloads. *(Source: TechCrunch Blog)*
- Gemini 1.5 Flash is priced significantly lower than Pro, making it ideal for summarization, chat agents, and extraction. *(Source: GeeksforGeeks)*

## Key Insights & Detailed Synthesis

### Findings from [Google Developer Documentation](https://ai.google.dev/)
- 1.5 Flash pricing: $0.075 / 1M input tokens (under 128k context length).
- 1.5 Pro pricing: $1.25 / 1M input tokens (under 128k context length).
- Flash exhibits up to 3x faster time-to-first-token compared to Pro, suitable for live chats.

### Findings from [Google Cloud Blog](https://cloud.google.com/blog/)
- Use Gemini 1.5 Pro for multi-turn conversational coding, complex reasoning on audio/video files, and cross-file repository analysis.
- Use Gemini 1.5 Flash for high-frequency extraction, video captioning, and routing tasks.

## Sources Scraped
| No. | Source Title | URL | Status |
|---|---|---|---|
| 1 | Google Gemini Developer Documentation | https://ai.google.dev/ | Success |
| 2 | Google Cloud Model Guides | https://cloud.google.com/ | Success |
| 3 | TechCrunch: Gemini 1.5 Flash Announcement | https://techcrunch.com/ | Success |
```

---

### 2️⃣ Option 2: Start Automation (Recurring Scheduled Scrapes)

This option turns the terminal into a monitoring daemon. It executes the scraper periodically to track updates on your topic and sends notifications to Discord or Telegram.

#### Step-by-Step Flow:
1. **Selection**: Select `2` in the main menu.
2. **Inputs**:
   * *Query*: `Gemini 1.5 Flash vs Gemini 1.5 Pro`
   * *Focus*: `Check for price drops, context increases, or version updates.`
   * *Interval*: Enter `15` (runs every 15 minutes).
3. **Execution**:
   * The program starts a persistent sleep cycle loop.
   * Prints: `🔄 [2026-06-21 00:15:00] Launching automated scrape run #1...`
   * Crawls search results, synthesizes the latest report, overrides or saves the file, and triggers webhooks.
   * Prints: `✔ Run #1 finished successfully at 00:15:10.`
   * Prints: `Waiting 15.0 minutes before next run. Press Ctrl+C to exit.`
   * Every 15 minutes, it repeats the process to ensure you are notified immediately of any online changes or news.

---

### 3️⃣ Option 3: Configure API Keys & Settings

This option lets you manage your API keys, preferred AI model, and notification webhooks without editing files manually.

#### Step-by-Step Flow:
1. **Selection**: Select `3` in the main menu.
2. **Interactive Configuration**:
   * **Gemini API Key** (Option `1`): Paste your Gemini key to use Gemini 1.5 Flash for reports or AI Grounding.
   * **OpenAI API Key** (Option `2`): Paste your OpenAI key to use models like `gpt-4o-mini` for reports.
   * **Anthropic Claude API Key** (Option `3`): Paste your Claude key to use models like `claude-3-5-sonnet` for reports.
   * **Tavily Search API Key** (Option `4`): Paste your Tavily API Key for high-fidelity developer search queries.
   * **Preferred AI Provider** (Option `5`): Select your default synthesis engine choice (`local`, `gemini`, `openai`, or `anthropic`).
   * **Web Search Method** (Option `6`): Select your search technique:
     - `duckduckgo`: Static HTML search parsing (offline & free).
     - `tavily`: AI-optimized developer search.
     - `ai_grounding`: **AI Search Grounding mode**. Tells the Gemini API to search Google live inside the LLM, synthesize the report directly, and cite grounded sources (skips local crawling entirely!).
   * **Discord Webhook URL** (Option `7`): Enter a Discord channel webhook URL to automatically push embedded updates.
   * **Telegram Bot Token & Chat ID** (Options `8` and `9`): Set Telegram bot credentials.
   * **Default Search Max Results** (Option `10`): Choose how many search result links to fetch (1-10, default is 5).
   * **Custom User-Agent** (Option `11`): Enter a custom User-Agent to override default values.
   * **Auto-Extract Cookies** (Option `12`): Enable automated decryption of session cookies from local browser profiles (Chrome/Edge/Firefox).
   * **Target Browser Source** (Option `13`): Set which local browser to search for cookies (Chrome, Edge, Firefox, Brave, or any).
   * **Configure Universal Cookie Map** (Option `14`): Enter custom cookie strings mapped to specific domains to bypass login walls.
3. **Persistence**: Saves configuration parameters directly to `config.json` in your workspace directory. They are automatically loaded the next time you boot the program.




---

### 4️⃣ Option 4: Browse Saved Reports History

This option lets you review past search results and read reports without opening a separate text editor.

#### Step-by-Step Flow:
1. **Selection**: Select `4` in the main menu.
2. **File Scanning**: The program scans the local `reports/` folder and builds a neat table of saved `.md` files.
3. **Rendering**:
   * Select the index number of the report you want to read.
   * The console uses **Rich Markdown Rendering** to output beautiful colored headings, bullet points, code blocks, and source links directly into the terminal window.
   * Press Enter to return to the history table.

---

## 💡 Summary of System Core Loop

```
┌──────────────────────────────────────────────────────────┐
│                   User starts main.py                    │
└────────────────────────────┬─────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [ Option 1 / Option 2 ]           [ Option 3 / Option 4 ]
            │                                 │
            ▼                                 ▼
┌───────────────────────┐          ┌───────────────────────┐
│  Search DuckDuckGo &  │          │ Read/Write config.json│
│   Scrape HTML pages   │          │  or view past reports │
└───────────┬───────────┘          └───────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────┐
│     Analyzer Synthesis (Local OR AI: Gemini/Open/Claude) │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│  Notifier Exports (JSON/MD) & Dispatches Webhooks/Alerts │
└──────────────────────────────────────────────────────────┘
```

---

## 🍪 Cookie Troubleshooting & Anti-Bot Bypass

When scraping sites with heavy login walls or anti-bot shields (like Reddit, Quora, or LinkedIn), importing session cookies is highly effective. Focal Harvest supports three ways of using cookies:
1. **Unified `cookies.txt` File (Highly Recommended)**: Export your browser cookies using an extension like *EditThisCookie* (using the Netscape format), and save the file to `config/cookies.txt`. This is ignored by git and provides a complete cookie jar, which is mandatory for bypassing Quora login walls.
2. **Universal Cookie Map (Option 14)**: Paste specific domain-to-cookie-string mappings directly in the Settings menu, which parses them from `config.json`.
3. **Automated Extraction (Option 12)**: Automatically extracts active cookies from your local browser (Chrome/Edge/Firefox) profiles at runtime.

### 🌟 Conditional User-Agent Routing
To avoid Cloudflare's bot-detection firewalls:
* **With Cookies**: If a session cookie is supplied (via `cookies.txt` or the map), the client automatically routes using a **standard Chrome browser User-Agent**. This makes the connection look like a real, logged-in user and prevents the bot/cookie mismatch block.
* **Without Cookies (Guest)**: If no cookies are set, the scraper overrides the User-Agent to **`Discordbot/2.0 (+https://discordapp.com)`**. This triggers Quora/social preview bypasses, retrieving the fully pre-rendered static HTML with hundreds of posts/answers without requiring a login!

### ⚠️ Operational Caveats for Automated Extraction (Option 12)

#### 1. Antivirus / Antimalware Alerts
* **Why it happens**: Local security monitors (like Windows Defender) flag python scripts that decrypt local browser credential databases because infostealers/malware use the exact same file access APIs.
* **The Solution**: 
  * Add your script folder to your local Antivirus exclusions/whitelist.
  * Avoid compiling the scraper to a single standalone `.exe` using PyInstaller.
  * Alternatively, fall back to the manual `config/cookies.txt` file which doesn't access any protected system files.

#### 2. Database Locking
* **Why it happens**: SQLite databases only support a single write lock. If your browser (Chrome/Edge/Firefox) is active, it locks the database file, preventing `rookiepy` from reading it.
* **The Solution**: 
  * Ensure you close the browser completely before running the TUI scraper.
  * Or, manually export the cookies as a Netscape-format text file and save it to `config/cookies.txt`.

#### 3. Portability Failures (Headless / VMs)
* **Why it happens**: Cloud VMs (AWS, Docker containers, GitHub Actions) do not run desktop environments and do not contain Chrome/Firefox profiles to extract from.
* **The Solution**:
  * Keep `Auto-Extract Cookies` disabled in production.
  * Manually drop your cookies in `config/cookies.txt` or paste them under the **Universal Cookie Map** (Option 14) in the settings menu, which parses them statically from `config.json` without searching the host machine.
