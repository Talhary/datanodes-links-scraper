# DataNodes Link Extractor Pro 🚀

High-performance direct download link extractor for **DataNodes** (`datanodes.to`). Built with a hybrid **SeleniumBase CDP + Node.js Puppeteer** architecture, featuring an interactive Web UI dashboard, real-time WebSocket telemetry, and automated Cloudflare Turnstile bypass.

---

## 🚀 Quick Start (Local)

### 1. Windows (One-Click Launcher)
Simply run the included batch script:
```bat
.\run.bat
```
The launcher will automatically:
1. Initialize the Python virtual environment (`venv`).
2. Verify and install any missing Python and Node.js dependencies.
3. Start the FastAPI server and open `http://localhost:8000`.

### 2. Manual Installation

#### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **Google Chrome** installed on your system

#### Setup
```bash
# 1. Create and activate Python virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 2. Install Python packages
pip install -r requirements.txt

# 3. Install Node packages
npm install

# 4. Start the server
python server.py
```

Open your browser and navigate to:
👉 **`http://localhost:8000`**

---

## ⚠️ Important: Headless Mode Notice

> [!WARNING]
> **Headless Mode (`headless=True`) is currently not working.**
> 
> Cloudflare Turnstile anti-bot detection on DataNodes detects and blocks headless Chrome browser sessions. 
> 
> - **Default Setting**: Headless mode is set to **`False`** (headed / visible browser window).
> - **Contributions Welcome**: If you have a working solution or stealth bypass that enables `headless=True` to pass Cloudflare Turnstile reliably, please feel free to fix it and **submit a Pull Request (PR)**!

---

## 🌟 Key Features

- **Automated Cloudflare Turnstile Bypass**: Uses low-level CDP hardware mouse events, human-like motion trajectories, and child-frame DOM traversal to solve Turnstile challenges automatically.
- **Hybrid Stealth Engine**: Combines **SeleniumBase UC/CDP Mode** for bot-detection evasion with **Node.js Puppeteer** for high-throughput DOM manipulation and CDP request interception.
- **Deep Network Interception**: Captures direct download tokens and CDN endpoints (`dlproxy`, signature URLs) directly from Chrome DevTools Protocol network streams without waiting for secondary countdown redirects.
- **In-Page Ad & Upsell Immunity**: Pre-injects DOM mutation hooks and ad-blocking rules that prevent popups, rogue tabs, and accidental redirects to premium upsell pages.
- **Multi-Worker Concurrency**: Run multiple parallel browser instances simultaneously (1 to 5) with real-time worker status cards and live streaming logs.
- **Interactive Web UI**: Modern dark-mode dashboard at `http://localhost:8000` with link queues, live progress bars, terminal logs, and one-click clipboard export.
- **Direct Link Persistence**: Extracted direct download links are streamed live to the UI and automatically persisted to `extracted_links.txt`.

---

## 🖥️ Web UI Dashboard

1. **Input Links**: Paste DataNodes URLs into the input textarea (or load from `links.txt`).
2. **Configure Workers**: Select the number of concurrent browser instances (1–5) and toggle **Headless Mode** (default: `False` / Visible).
3. **Start Extraction**: Click **Start Extraction**. Watch the live terminal logs and worker status cards in real-time.
4. **Copy / Save Results**: Extracted direct links will appear in the output box and are automatically appended to `extracted_links.txt`.

---

## 📁 Architecture Overview

```
DataNodes/
├── server.py              # FastAPI + WebSocket backend & API endpoints
├── manager.py             # Multi-browser SeleniumBase CDP orchestrator
├── puppeteer_worker.js    # Node.js CDP worker (Turnstile solver, adblocker, link extractor)
├── public/                # Web UI dashboard frontend (HTML, CSS, JS)
├── requirements.txt       # Python dependencies (SeleniumBase, FastAPI, Uvicorn, etc.)
├── package.json           # Node.js dependencies (puppeteer-core)
├── links.txt              # Input file for batch URL extraction
├── extracted_links.txt    # Output file where captured direct links are saved
└── run.bat                # One-click Windows launcher
```

---

## 🔌 API & WebSocket Reference

### HTTP Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/status` | Get current extraction job state, active workers, and progress. |
| `POST` | `/api/extract` | Start a new extraction job (`{ links: [...], workers: 3, headless: false }`). |
| `POST` | `/api/stop` | Terminate all active workers and stop the extraction job. |
| `GET` | `/api/extracted` | Retrieve list of all successfully extracted direct links. |
| `GET` | `/api/health` | Health check endpoint. |

### WebSocket Endpoint

- **URL**: `ws://localhost:8000/ws`
- **Events**: Streams JSON payloads for real-time `status`, `progress`, `worker_status`, `log`, and `complete` events.

---

## 🤝 Contributing

Contributions, bug fixes, and improvements are welcome! If you can fix headless mode execution or enhance bypass reliability:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/headless-fix`)
3. Commit your changes (`git commit -m "Fix headless mode Turnstile bypass"`)
4. Push to the branch (`git push origin feature/headless-fix`)
5. Open a **Pull Request**
