## 📇 Project Dossier & Maintainer Guardrails

### Core Project Description
`focal-harvest` is an open-source, CLI-based OSINT web scraping and AI research automation tool. It serves as an interactive CLI research assistant that scrapes, sanitizes, and synthesizes web content locally or via Gemini/OpenAI/Claude, with Discord/Telegram alerts & built-in automation.

### 🛠️ The Author's 5 Strict Criteria
Every single code adjustment must fit perfectly within these non-negotiable boundaries set by the author:
1. **Lightweight Footprint**: The application folder must remain small (a few megabytes) and install quickly.
2. **Strictly CLI/TUI Only**: The entire program must run, update, and display natively inside a terminal shell. Web-based frontends (React) or local REST API backends (FastAPI) are entirely banned.
3. **Low Hardware Requirements**: It must run effortlessly on low-end student laptops without hogging heavy multi-core CPUs, maxing out RAM, or requiring a dedicated GPU.
4. **No Local AI Models**: Multi-gigabyte open-source models (like Ollama, Llama, or local embedding models) cannot be downloaded or run locally on the machine.
5. **Strictly NO SQL Databases**: Complex database engines (PostgreSQL, MongoDB) or relational database code setups (SQLite, SQLAlchemy) are completely banned. The data layer must remain transparent, single-folder, and easily readable simply by double-clicking a standard text file.

### 🌐 Web Scraping & Wayback Cache Retrieval Rules
To ensure high-fidelity scrapes and resilient fallbacks, all plugins and crawler modules must follow these standards:
1. **Wayback Availability API Querying**: Always query the Wayback Machine Availability API (`https://archive.org/wayback/available?url=...`) before requesting cached content. This dynamically identifies the latest archived snapshot returning status `200`, preventing redirect loops (e.g., `302` redirects to verification pages) or empty oldest captures (the `2id_` year 2000 trap).
2. **Raw HTML Playback Conversion**: Always rewrite standard Wayback playback URLs (e.g. `/web/{timestamp}/`) to the raw text content identifier `id_` format (e.g. `/web/{timestamp}id_/`) to avoid script injection overlays.
3. **No Domain Rewrites Prior to Wayback Queries**: Keep URL querying generic. Do not pre-emptively rewrite subdomains (like `old.reddit.com`) before the Wayback Availability check; many subdomains do not have recent captures archived under them.
4. **Adaptive Custom DOM Parsers**: Custom plugin parsers must be robust against layout changes. For example, the Reddit plugin must support both `old.reddit.com` layout markup and `www.reddit.com` Redesign markup to capture complete comment trees regardless of which snapshot Wayback serves.
5. **Immediate Failure Bubbling**: Plugins must return `success: False` immediately upon finding blockages or missing core content, triggering the Wayback fallback instead of treating a blank SPA skeleton as a successful scrape.
6. **Targeted Media Regex Pre-Checks**: When matching links for specific media sub-extractors (e.g. YouTube video ID regex), verify the URL domain (e.g., `youtube.com` or `youtu.be`) first before executing API connections, preventing false-positive collisions on long slug-paths (like Quora question segments).
7. **Compliant Bot Identification**: For corporate and government databases that mandate scraper disclosure (like `sec.gov`), supply compliant bot user agents (`BotName contact@domain.com`) in request headers rather than randomized desktop browser strings to cooperate with their terms and avoid automatic HTTP 403 blocks.
8. **LLM Synthesis Error Propagation**: All third-party AI summary methods must support an optional `raise_on_error: bool = False` parameter to bubble up network or key authentication failures to the orchestrator, enabling multi-provider failover recovery before dropping to local synthesis.
