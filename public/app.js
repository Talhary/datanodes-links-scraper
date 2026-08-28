/**
 * DataNodes Pro Link Extractor - Client Application
 */

(function () {
    // State
    const state = {
        ws: null,
        isConnected: false,
        isRunning: false,
        items: [],
        workers: [],
        logs: [],
        activeFilter: 'all',
        autoScrollLogs: true,
        elapsedTimer: null,
        startTime: 0
    };

    // DOM Elements
    const elements = {
        wsStatusBadge: document.getElementById('wsStatusBadge'),
        wsStatusText: document.getElementById('wsStatusText'),
        linksTextarea: document.getElementById('linksTextarea'),
        lineCountBadge: document.getElementById('lineCountBadge'),
        fileUploadInput: document.getElementById('fileUploadInput'),
        btnClearInput: document.getElementById('btnClearInput'),
        workersSlider: document.getElementById('workersSlider'),
        workersCountBadge: document.getElementById('workersCountBadge'),
        headlessToggle: document.getElementById('headlessToggle'),
        btnStartExtract: document.getElementById('btnStartExtract'),
        btnStopExtract: document.getElementById('btnStopExtract'),
        
        // Metrics
        statTotal: document.getElementById('statTotal'),
        statSuccess: document.getElementById('statSuccess'),
        statFailed: document.getElementById('statFailed'),
        statRate: document.getElementById('statRate'),
        statElapsed: document.getElementById('statElapsed'),
        statSpeed: document.getElementById('statSpeed'),
        globalProgressBar: document.getElementById('globalProgressBar'),
        activeWorkersBadge: document.getElementById('activeWorkersBadge'),
        workersGrid: document.getElementById('workersGrid'),

        // Tabs & Toolbars
        tabBtnResults: document.getElementById('tabBtnResults'),
        tabBtnLogs: document.getElementById('tabBtnLogs'),
        resultsTab: document.getElementById('resultsTab'),
        logsTab: document.getElementById('logsTab'),
        resultsCountBadge: document.getElementById('resultsCountBadge'),
        logsCountBadge: document.getElementById('logsCountBadge'),
        resultsToolbar: document.getElementById('resultsToolbar'),
        logsToolbar: document.getElementById('logsToolbar'),
        resultsEmptyState: document.getElementById('resultsEmptyState'),
        resultsList: document.getElementById('resultsList'),
        terminalContainer: document.getElementById('terminalContainer'),
        terminalLogs: document.getElementById('terminalLogs'),
        autoScrollLogsToggle: document.getElementById('autoScrollLogsToggle'),
        btnClearLogs: document.getElementById('btnClearLogs'),
        btnCopyAll: document.getElementById('btnCopyAll'),
        btnExportTxt: document.getElementById('btnExportTxt'),
        btnExportIdm: document.getElementById('btnExportIdm'),
        btnExportJson: document.getElementById('btnExportJson'),
        toastContainer: document.getElementById('toastContainer')
    };

    // Initialize Application
    function init() {
        setupWebSocket();
        setupEventListeners();
        renderWorkerSlots(parseInt(elements.workersSlider.value, 10));
        updateLinkCount();
    }

    // WebSocket Management
    function setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        try {
            state.ws = new WebSocket(wsUrl);

            state.ws.onopen = () => {
                state.isConnected = true;
                elements.wsStatusBadge.className = 'status-indicator connected';
                elements.wsStatusText.textContent = 'Connected';
                addTerminalLog({ text: 'WebSocket connected to DataNodes backend.', level: 'system' });
            };

            state.ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    handleServerMessage(msg);
                } catch (e) {
                    console.error('Error parsing WebSocket message:', e);
                }
            };

            state.ws.onclose = () => {
                state.isConnected = false;
                elements.wsStatusBadge.className = 'status-indicator disconnected';
                elements.wsStatusText.textContent = 'Reconnecting...';
                setTimeout(setupWebSocket, 2000);
            };

            state.ws.onerror = () => {
                state.ws.close();
            };
        } catch (err) {
            console.error('WebSocket connection error:', err);
            setTimeout(setupWebSocket, 3000);
        }
    }

    // Message Router
    function handleServerMessage(msg) {
        switch (msg.type) {
            case 'init':
            case 'status_update':
                updateFullStatus(msg.data);
                break;
            case 'job_started':
                state.isRunning = true;
                setControlsRunning(true);
                updateFullStatus(msg.data);
                showToast('Extraction job started!', 'success');
                startElapsedTimer();
                break;
            case 'job_completed':
                state.isRunning = false;
                setControlsRunning(false);
                updateFullStatus(msg.data);
                stopElapsedTimer();
                showToast(`Extraction complete! (${msg.data.successful}/${msg.data.total} succeeded)`, 'success');
                break;
            case 'job_stopped':
                state.isRunning = false;
                setControlsRunning(false);
                updateFullStatus(msg.data);
                stopElapsedTimer();
                showToast('Extraction job stopped.', 'error');
                break;
            case 'item_updated':
                updateSingleItem(msg.item);
                break;
            case 'log':
                addTerminalLog(msg);
                break;
            case 'status':
                updateWorkerStage(msg);
                break;
        }
    }

    // Update Full Status
    function updateFullStatus(data) {
        if (!data) return;

        state.isRunning = !!data.isRunning;
        setControlsRunning(state.isRunning);

        state.items = data.items || [];
        elements.statTotal.textContent = data.total || 0;
        elements.statSuccess.textContent = data.successful || 0;
        elements.statFailed.textContent = data.failed || 0;
        elements.statRate.textContent = `${data.successRate || 0}%`;
        elements.statSpeed.textContent = data.speed || '0.0';

        if (data.total > 0) {
            const pct = Math.round((data.completed / data.total) * 100);
            elements.globalProgressBar.style.width = `${pct}%`;
        } else {
            elements.globalProgressBar.style.width = '0%';
        }

        // Workers
        if (data.workers && data.workers.length > 0) {
            state.workers = data.workers;
            const activeCount = data.workers.filter(w => w.isBusy).length;
            elements.activeWorkersBadge.textContent = `${activeCount} / ${data.workers.length} active`;
            renderWorkerCards(data.workers);
        }

        renderResultsList();
    }

    function updateSingleItem(item) {
        const idx = state.items.findIndex(i => i.id === item.id);
        if (idx !== -1) {
            state.items[idx] = item;
        } else {
            state.items.push(item);
        }
        renderResultsList();
    }

    function updateWorkerStage(data) {
        const workerCard = document.getElementById(`workerCard-${data.worker}`);
        if (!workerCard) return;

        const stagePill = workerCard.querySelector('.worker-stage-pill');
        const stepDesc = workerCard.querySelector('.worker-step-desc');
        const linkInfo = workerCard.querySelector('.worker-link-info');

        if (stagePill) {
            stagePill.className = `worker-stage-pill ${data.stage || 'idle'}`;
            stagePill.textContent = (data.stage || 'idle').replace('_', ' ');
        }
        if (stepDesc) {
            stepDesc.textContent = data.step || '';
        }
        if (data.link && linkInfo) {
            linkInfo.textContent = data.link.split('/').pop() || data.link;
        }
    }

    // Render Worker Slot Placeholders / Cards
    function renderWorkerSlots(count) {
        elements.workersGrid.innerHTML = '';
        for (let i = 1; i <= count; i++) {
            const card = document.createElement('div');
            card.id = `workerCard-${i}`;
            card.className = 'worker-card';
            card.innerHTML = `
                <div class="worker-header">
                    <span class="worker-title">Worker ${i}</span>
                    <span class="worker-port">:${9220 + i}</span>
                </div>
                <div class="worker-stage-pill idle">Idle</div>
                <div class="worker-step-desc" style="font-size: 0.75rem; color: var(--text-secondary);">Ready</div>
                <div class="worker-link-info">Waiting for queue...</div>
            `;
            elements.workersGrid.appendChild(card);
        }
    }

    function renderWorkerCards(workers) {
        elements.workersGrid.innerHTML = '';
        workers.forEach(w => {
            const card = document.createElement('div');
            card.id = `workerCard-${w.id}`;
            card.className = `worker-card ${w.isBusy ? 'active' : ''}`;
            
            const stageClass = w.stage || 'idle';
            const displayStage = stageClass.replace('_', ' ');
            const filename = w.currentLink ? (w.currentLink.split('/').pop() || w.currentLink) : 'Waiting for queue...';

            card.innerHTML = `
                <div class="worker-header">
                    <span class="worker-title">Worker ${w.id}</span>
                    <span class="worker-port">:${w.port}</span>
                </div>
                <div class="worker-stage-pill ${stageClass}">${displayStage}</div>
                <div class="worker-step-desc" style="font-size: 0.75rem; color: var(--text-secondary);">${w.step || 'Idle'}</div>
                <div class="worker-link-info" title="${w.currentLink || ''}">${filename}</div>
            `;
            elements.workersGrid.appendChild(card);
        });
    }

    // Render Results List
    function renderResultsList() {
        const filtered = state.items.filter(item => {
            if (state.activeFilter === 'success') return item.status === 'success';
            if (state.activeFilter === 'failed') return item.status === 'failed';
            return true;
        });

        elements.resultsCountBadge.textContent = state.items.filter(i => i.status === 'success').length;

        if (state.items.length === 0) {
            elements.resultsEmptyState.style.display = 'flex';
            elements.resultsList.style.display = 'none';
            return;
        }

        elements.resultsEmptyState.style.display = 'none';
        elements.resultsList.style.display = 'flex';
        elements.resultsList.innerHTML = '';

        filtered.forEach((item, index) => {
            const row = document.createElement('div');
            row.className = 'result-item';

            const extractedMarkup = item.extractedUrl 
                ? `<a href="${item.extractedUrl}" target="_blank" class="item-extracted" title="${item.extractedUrl}">${item.extractedUrl}</a>`
                : (item.error ? `<span class="item-error">${item.error}</span>` : `<span style="color: var(--text-muted); font-size: 0.78rem;">Extracting direct link...</span>`);

            const copyBtnMarkup = item.extractedUrl ? `
                <button class="btn-icon-action btn-copy-single" data-url="${item.extractedUrl}" title="Copy direct URL">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                </button>
            ` : '';

            row.innerHTML = `
                <span class="item-index">#${item.id + 1}</span>
                <div class="item-details">
                    <div class="item-name" title="${item.originalUrl}">${item.filename}</div>
                    ${extractedMarkup}
                </div>
                <div class="item-meta">
                    <span class="status-badge ${item.status}">${item.status}</span>
                    ${item.timeTaken ? `<span style="font-size: 0.72rem; color: var(--text-muted);">${item.timeTaken}s</span>` : ''}
                    ${copyBtnMarkup}
                </div>
            `;
            elements.resultsList.appendChild(row);
        });

        // Attach single copy listeners
        elements.resultsList.querySelectorAll('.btn-copy-single').forEach(btn => {
            btn.addEventListener('click', () => {
                const url = btn.getAttribute('data-url');
                if (url) copyToClipboard(url, 'Direct download link copied!');
            });
        });
    }

    // Terminal Logging
    function addTerminalLog(log) {
        state.logs.push(log);
        elements.logsCountBadge.textContent = state.logs.length;

        const line = document.createElement('div');
        const level = log.level || 'info';
        line.className = `log-line ${level}`;

        const ts = new Date(log.timestamp || Date.now()).toLocaleTimeString();
        const workerTag = log.worker > 0 ? `<span class="log-worker">[Worker ${log.worker}]</span>` : '';
        
        line.innerHTML = `<span class="log-ts">[${ts}]</span>${workerTag} ${escapeHtml(log.text || '')}`;
        elements.terminalLogs.appendChild(line);

        if (state.autoScrollLogs) {
            elements.terminalContainer.scrollTop = elements.terminalContainer.scrollHeight;
        }
    }

    // Event Listeners
    function setupEventListeners() {
        // Textarea Link Count
        elements.linksTextarea.addEventListener('input', updateLinkCount);

        // Clear Links
        elements.btnClearInput.addEventListener('click', () => {
            elements.linksTextarea.value = '';
            updateLinkCount();
        });

        // File Import
        elements.fileUploadInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (evt) => {
                elements.linksTextarea.value = evt.target.result;
                updateLinkCount();
                showToast(`Loaded links from ${file.name}`, 'success');
            };
            reader.readAsText(file);
        });

        // Workers Slider (1-5, max 5)
        elements.workersSlider.addEventListener('input', (e) => {
            const val = parseInt(e.target.value, 10);
            elements.workersCountBadge.textContent = `${val} Browser${val > 1 ? 's' : ''}`;
            if (!state.isRunning) {
                renderWorkerSlots(val);
            }
        });

        // Start Extraction
        elements.btnStartExtract.addEventListener('click', startExtraction);

        // Stop Extraction
        elements.btnStopExtract.addEventListener('click', stopExtraction);

        // Tabs Navigation
        elements.tabBtnResults.addEventListener('click', () => switchTab('results'));
        elements.tabBtnLogs.addEventListener('click', () => switchTab('logs'));

        // Results Filter Pills
        document.querySelectorAll('.filter-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                state.activeFilter = pill.getAttribute('data-filter');
                renderResultsList();
            });
        });

        // Auto Scroll Toggle
        elements.autoScrollLogsToggle.addEventListener('change', (e) => {
            state.autoScrollLogs = e.target.checked;
        });

        // Clear Logs
        elements.btnClearLogs.addEventListener('click', () => {
            elements.terminalLogs.innerHTML = '';
            state.logs = [];
            elements.logsCountBadge.textContent = '0';
        });

        // Export Actions
        elements.btnCopyAll.addEventListener('click', copyAllLinks);
        elements.btnExportTxt.addEventListener('click', () => window.open('/api/export/txt', '_blank'));
        elements.btnExportIdm.addEventListener('click', () => window.open('/api/export/idm', '_blank'));
        elements.btnExportJson.addEventListener('click', () => window.open('/api/export/json', '_blank'));
    }

    function updateLinkCount() {
        const text = elements.linksTextarea.value.trim();
        const count = text ? text.split('\n').filter(s => s.trim().length > 0).length : 0;
        elements.lineCountBadge.textContent = `${count} link${count !== 1 ? 's' : ''} detected`;
    }

    async function startExtraction() {
        const raw = elements.linksTextarea.value.trim();
        const links = raw.split('\n').map(s => s.trim()).filter(Boolean);

        if (links.length === 0) {
            showToast('Please enter at least one DataNodes link.', 'error');
            return;
        }

        const workers = parseInt(elements.workersSlider.value, 10) || 3;
        const headless = elements.headlessToggle.checked;

        elements.btnStartExtract.disabled = true;
        elements.btnStartExtract.innerHTML = '<span class="spinner"></span> Starting...';

        try {
            const resp = await fetch('/api/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ links, workers, headless })
            });
            const res = await resp.json();

            if (!resp.ok) {
                throw new Error(res.detail || 'Failed to start extraction');
            }

            state.isRunning = true;
            setControlsRunning(true);
        } catch (err) {
            showToast(err.message, 'error');
            setControlsRunning(false);
        }
    }

    async function stopExtraction() {
        elements.btnStopExtract.disabled = true;
        try {
            await fetch('/api/stop', { method: 'POST' });
            showToast('Stopping workers...', 'info');
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function setControlsRunning(isRunning) {
        elements.btnStartExtract.disabled = isRunning;
        elements.btnStopExtract.disabled = !isRunning;
        elements.workersSlider.disabled = isRunning;
        elements.headlessToggle.disabled = isRunning;

        if (isRunning) {
            elements.btnStartExtract.innerHTML = `
                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                <span>Extracting...</span>
            `;
        } else {
            elements.btnStartExtract.innerHTML = `
                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                <span>Start Extraction</span>
            `;
        }
    }

    function switchTab(tab) {
        if (tab === 'results') {
            elements.tabBtnResults.classList.add('active');
            elements.tabBtnLogs.classList.remove('active');
            elements.resultsTab.classList.add('active');
            elements.logsTab.classList.remove('active');
            elements.resultsToolbar.style.display = 'flex';
            elements.logsToolbar.style.display = 'none';
        } else {
            elements.tabBtnLogs.classList.add('active');
            elements.tabBtnResults.classList.remove('active');
            elements.logsTab.classList.add('active');
            elements.resultsTab.classList.remove('active');
            elements.resultsToolbar.style.display = 'none';
            elements.logsToolbar.style.display = 'flex';
        }
    }

    function copyAllLinks() {
        const directUrls = state.items
            .filter(i => i.status === 'success' && i.extractedUrl)
            .map(i => i.extractedUrl);

        if (directUrls.length === 0) {
            showToast('No extracted links to copy yet.', 'error');
            return;
        }

        copyToClipboard(directUrls.join('\n'), `Copied ${directUrls.length} extracted link(s) to clipboard!`);
    }

    function copyToClipboard(text, successMessage) {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(() => {
                showToast(successMessage || 'Copied to clipboard!', 'success');
            }).catch(() => fallbackCopy(text, successMessage));
        } else {
            fallbackCopy(text, successMessage);
        }
    }

    function fallbackCopy(text, successMessage) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            showToast(successMessage || 'Copied to clipboard!', 'success');
        } catch (e) {
            showToast('Failed to copy to clipboard', 'error');
        }
        document.body.removeChild(ta);
    }

    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
        elements.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    function startElapsedTimer() {
        stopElapsedTimer();
        state.startTime = Date.now();
        state.elapsedTimer = setInterval(() => {
            const elapsedSec = Math.floor((Date.now() - state.startTime) / 1000);
            const m = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
            const s = String(elapsedSec % 60).padStart(2, '0');
            elements.statElapsed.textContent = `${m}:${s}`;
        }, 1000);
    }

    function stopElapsedTimer() {
        if (state.elapsedTimer) {
            clearInterval(state.elapsedTimer);
            state.elapsedTimer = null;
        }
    }

    function escapeHtml(str) {
        return (str || '').replace(/[&<>'"]/g, tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag));
    }

    // Boot
    document.addEventListener('DOMContentLoaded', init);
})();
