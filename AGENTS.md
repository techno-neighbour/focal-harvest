## 📇 Project Dossier & Maintainer Guardrails

### Core Project Description
`focal-harvest` is an open-source, CLI-based OSINT web scraping and AI research automation tool. It serves as an interactive CLI research assistant that scrapes, sanitizes, and synthesizes web content locally or via Gemini/OpenAI/Claude, with Discord/Telegram alerts & built-in automation.

### 🛠️ The Author's 5 Strict Criteria
Every architectural proposal and code modification must align with the maintainer's core philosophies. Any pull request breaking these guardrails will be rejected:
1. **Lightweight Footprint**: The application must remain tiny in size, install rapidly, and have a minimal disk space footprint. 
2. **Strictly CLI/TUI Only**: The entire program must run, update, and display natively inside a shell. Web-based GUIs or local REST APIs are completely banned.
3. **Low Hardware Requirements**: It must run effortlessly on low-end student laptops. It cannot require heavy multi-core CPUs, high RAM overhead, or a dedicated GPU.
4. **No Local AI Models**: Multi-gigabyte open-source models (like Ollama, Llama, or local embedding models) cannot be downloaded or executed on the machine.
5. **Strictly NO SQL Databases**: Complex database servers (PostgreSQL, MongoDB) or relational database languages/ORMs (SQLite, SQLAlchemy) are banned. The project data layer must remain transparent, single-folder, and easy for a student to inspect by double-clicking a file.