# DataNodes & FileKeeper Pro Link Extractor 🚀

High-performance direct download link extractor for **DataNodes** (`datanodes.to`) and **FileKeeper** (`filekeeper.net`). Built with a dual-engine architecture: a hybrid **SeleniumBase CDP + Node.js Puppeteer** pipeline for automated Cloudflare Turnstile bypass on DataNodes, alongside an ultra-fast **Direct HTTP Handshake Resolver** for FileKeeper.

---

## 🚀 Quick Start (Local)

### 1. Windows (One-Click Launcher)
Simply double-click or run the included batch script:
```bat
.\run.bat
```
The launcher will automatically:
1. Detect Python, Node.js & Google Chrome (and auto-install them if missing).
2. Initialize the Python virtual environment (`venv`).
3. Verify and install all Python (`requirements.txt`) and Node.js (`package.json`) dependencies.
4. Launch the FastAPI server and open `http://localhost:8000` in your default browser.

---

### 2. Manual Installation

#### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **Google Chrome** installed on your system

#### Setup Steps
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

### 3. Docker Compose Deployment 🐳

For containerized environments or Linux servers, use Docker Compose:

```bash
# 1. Build and start the container in detached mode
docker compose up -d --build

# 2. Monitor live application logs
docker compose logs -f

# 3. Stop the container
docker compose down
```

The Web UI dashboard will be available at:
👉 **`http://localhost:8000`**

---

## ⚡ FileKeeper Direct Links Scraper & Resolver

FileKeeper (`filekeeper.net`) sharing links lead to intermediate HTML landing pages. The integrated FileKeeper subsystem programmatically simulates the free-tier download handshake, bypassing landing pages, ad scripts, and countdown timers to obtain high-speed CDN streaming URLs (e.g., direct endpoints on `dlproxy.uk` or high-port edge servers like `:8443`) in milliseconds without requiring a browser session.

```mermaid
sequenceDiagram
    autonumber
    actor Client as User / Web UI / REST API
    participant API as FastAPI Backend (/api/resolve-links)
    participant FK as FileKeeper Engine (filekeeper.py)
    participant Host as FileKeeper Server (filekeeper.net)
    participant CDN as FileKeeper Direct CDN Node

    Client->>API: POST /api/resolve-links (or /api/extract)
    API->>FK: resolve_filekeeper_urls_bulk(urls)
    Note over FK: Extract File ID ([a-zA-Z0-9]+)<br/>Check not already resolved (dlproxy.uk / :8443)
    FK->>Host: POST /download (redirect: manual)<br/>Body: op=download2&id={id}&method_free=Free+download&down_direct=1<br/>Cookie: lang=english; file_code={id}
    Host-->>FK: HTTP 302 Found (Location: https://s12.filekeeper.net:8443/...)
    Note over FK: Intercept Location Header
    FK-->>API: Direct CDN URLs
    API-->>Client: { original, resolved, success: true }
    Client->>CDN: Stream / Download File Directly
```

### Key FileKeeper Handshake Parameters:
- **Endpoint**: `https://filekeeper.net/download`
- **Payload**: `op=download2&id=<fileId>&rand=&referer=&method_free=Free+download&down_direct=1`
- **Headers**:
  - `Cookie: lang=english; file_code=<fileId>`
  - `Referer: https://filekeeper.net/download`
  - `Connection: close` (Manual HTTP 302 redirect interception)

---

## ⚠️ Important: Headless Mode Notice (DataNodes)

> [!WARNING]
> **Headless Mode (`headless=True`) is currently not working for DataNodes.**
> 
> Cloudflare Turnstile anti-bot detection on DataNodes detects and blocks headless Chrome browser sessions. 
> 
> - **Default Setting**: Headless mode is set to **`False`** (headed / visible browser window).
> - **FileKeeper Links**: Unaffected by headless settings as they resolve via direct HTTP handshakes.
> - **Contributions Welcome**: If you have a working solution or stealth bypass that enables `headless=True` to pass Cloudflare Turnstile reliably on DataNodes, please feel free to fix it and **submit a Pull Request (PR)**!

---

## 🌟 Key Features

- **Dual-Engine Architecture**:
  - **DataNodes Engine**: Hybrid **SeleniumBase UC/CDP Mode** + **Node.js Puppeteer** with automated Cloudflare Turnstile bypass and CDP network stream interception.
  - **FileKeeper Engine**: Ultra-fast direct HTTP 302 resolver that extracts direct CDN URLs (`dlproxy.uk`, `:8443`) in milliseconds.
- **Deep Network Interception**: Captures direct download tokens and CDN endpoints directly without waiting for secondary countdown redirects.
- **In-Page Ad & Upsell Immunity**: Pre-injects DOM mutation hooks and ad-blocking rules preventing popups and rogue redirects.
- **Multi-Worker Concurrency**: Run up to 5 concurrent browser workers for DataNodes with live streaming telemetry.
- **Interactive Web UI**: Modern dark-mode dashboard with smart URL detection, live progress bars, terminal logs, and one-click clipboard export (`Ctrl + Enter` shortcut supported).
- **Direct Link Persistence**: Extracted direct download links are streamed live to the UI and automatically appended to `extracted_links.txt`.
- **Multi-Format Export**: Export results to `.txt`, IDM (`.txt`), or JSON.

---

## 🖥️ Web UI Dashboard

1. **Input Links**: Paste DataNodes or FileKeeper URLs into the input textarea (or load from `links.txt`).
2. **Keyboard Shortcut**: Press **`Ctrl + Enter`** to trigger extraction instantly.
3. **Configure Workers**: Select the number of concurrent browser instances (1–5) and toggle **Headless Mode** (default: `False` / Visible).
4. **Start Extraction**: Click **Start Extraction**. FileKeeper links resolve immediately, while DataNodes links are processed by stealth browser workers.
5. **Copy / Save Results**: Extracted direct links will appear in the output box and are automatically appended to `extracted_links.txt`.

---

## 📁 Architecture Overview

```
DataNodes/
├── server.py              # FastAPI + WebSocket backend & REST API endpoints
├── filekeeper.py          # Fast HTTP FileKeeper direct link resolver
├── manager.py             # Multi-browser SeleniumBase CDP orchestrator & job manager
├── puppeteer_worker.js    # Node.js CDP worker (Turnstile solver, adblocker, link extractor)
├── public/                # Modern Web UI dashboard (HTML, CSS, JS)
├── Dockerfile             # Multi-stage container definition (Python + Node.js + Chrome)
├── docker-compose.yml     # Container orchestration specification
├── requirements.txt       # Python dependencies (SeleniumBase, FastAPI, Uvicorn, etc.)
├── package.json           # Node.js dependencies (puppeteer-core)
├── links.txt              # Input file for batch URL extraction
├── extracted_links.txt    # Output file where captured direct links are saved
└── run.bat                # One-click Windows launcher with auto-dependency installer
```

---

## 🔌 API & WebSocket Reference

### HTTP Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/resolve-links` | Bulk FileKeeper direct link resolution (`{ "urls": [...] }`). |
| `POST` | `/api/extract` | Start unified batch extraction job (`{ "links": [...], "workers": 3, "headless": false }`). |
| `GET` | `/api/status` | Get current extraction job state, active workers, and progress. |
| `POST` | `/api/stop` | Terminate all active workers and stop the extraction job. |
| `GET` | `/api/export/{fmt}` | Export resolved links (`txt`, `idm`, `json`). |
| `GET` | `/api/health` | Health check endpoint. |

#### Bulk Resolve Example (`POST /api/resolve-links`)

**Request**:
```json
{
  "urls": [
    "https://filekeeper.net/abc12345",
    "https://filekeeper.net/xyz98765"
  ]
}
```

**Response (HTTP 200 OK)**:
```json
{
  "results": [
    {
      "original": "https://filekeeper.net/abc12345",
      "resolved": "https://s12.filekeeper.net:8443/d/abc12345/sample_video.mp4",
      "success": true,
      "filename": "sample_video.mp4"
    },
    {
      "original": "https://filekeeper.net/xyz98765",
      "resolved": "https://filekeeper.net/xyz98765",
      "success": false,
      "error": "HTTP 200: No direct 302 location header returned by FileKeeper."
    }
  ]
}
```

### WebSocket Endpoint

- **URL**: `ws://localhost:8000/ws`
- **Events**: Streams JSON payloads for real-time `status`, `progress`, `worker_status`, `item_updated`, `log`, and `job_completed` events.

---

## 🤝 Contributing

Contributions, bug fixes, and improvements are welcome! If you can fix headless mode execution on DataNodes or enhance bypass reliability:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/headless-fix`)
3. Commit your changes (`git commit -m "Fix headless mode Turnstile bypass"`)
4. Push to the branch (`git push origin feature/headless-fix`)
5. Open a **Pull Request**
