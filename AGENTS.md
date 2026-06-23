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
