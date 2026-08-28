# ===================================================================
# Dockerfile - DataNodes Pro Link Extractor
# Multi-runtime: Python 3.11 + Node.js 22 + Google Chrome + Xvfb
# ===================================================================

FROM python:3.11-slim-bookworm

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000 \
    HEADLESS=false

# Install OS libraries, Xvfb, fonts, Node.js 22, and Google Chrome Stable
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gnupg \
    ca-certificates \
    xvfb \
    xauth \
    dbus-x11 \
    procps \
    dumb-init \
    fonts-liberation \
    fonts-noto-color-emoji \
    fontconfig \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libxext6 \
    libxrender1 \
    libglib2.0-0 \
    libasound2 \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Node dependencies
COPY package*.json ./
RUN npm install --omit=dev

# Copy application files
COPY puppeteer_worker.js manager.py server.py ./
COPY public/ ./public/

# Expose Web Interface & WebSocket port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=20s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

# Start server wrapped in dumb-init
ENTRYPOINT ["dumb-init", "--"]
CMD ["python", "server.py"]
