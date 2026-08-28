/**
 * Puppeteer Scraper for DataNodes (and similar file hosts)
 * Connects over Chrome DevTools Protocol (CDP) to a stealth SeleniumBase browser session.
 */

const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

// Blocked ad networks and tracking URLs for network-level blocking
const BLOCKED_AD_PATTERNS = [
    '*dlproxy.uk*', '*dlproxy.com*', '*dlproxy.net*', '*dlproxy*', // Prevent browser streaming of direct downloads
    '*doubleclick.net*', '*googlesyndication.com*', '*google-analytics.com*', '*googleadservices.com*',
    '*adservice.google.*', '*pagead2.googlesyndication.com*', '*adnxs.com*', '*ads.pubmatic.com*',
    '*rubiconproject.com*', '*openx.net*', '*smartadserver.com*', '*casalemedia.com*',
    '*bidswitch.net*', '*amazon-adsystem.com*', '*moatads.com*', '*criteo.com*', '*criteo.net*',
    '*scorecardresearch.com*', '*outbrain.com*', '*taboola.com*', '*mgid.com*', '*revcontent.com*',
    '*popads.net*', '*popcash.net*', '*propellerads.com*', '*exoclick.com*', '*adcash.com*',
    '*adsterra.com*', '*onclickbright.com*', '*monetag.com*', '*hilltopads.com*', '*clickadu.com*',
    '*trafficjunky.*', '*juicyads.*', '*yllix.com*', '*ad-maven.com*', '*ad-delivery.net*',
    '*adtrue.com*', '*tsyndicate.com*', '*clicksor.com*', '*vidoomy.com*', '*teads.tv*',
    '*gumgum.com*', '*zergnet.com*', '*nativeads.com*', '*adpushup.com*', '*ezoic.net*',
    '*media.net*', '*adblade.com*', '*richaudience.com*', '*setupad.com*', '*admanmedia.com*',
    '*trafficstars.com*', '*ero-advertising.com*', '*plugrush.com*', '*adxad.com*',
    '*adplexity.com*', '*bidgear.com*', '*evadav.com*', '*rollerads.com*', '*clickaine.com*',
    '*pushground.com*', '*richpush.com*', '*notix.co*', '*propellerclick.com*', '*propu.sh*',
    '*clckhubs.com*', '*onclickmega.com*', '*syndication.exoclick.com*', '*main.exoclick.com*',
    '*adskeeper.co.uk*', '*adskeeper.com*', '*adkernel.com*', '*adoperator.com*',
    '*hotjar.com*', '*clarity.ms*', '*yandex.metrika*', '*statcounter.com*', '*histats.com*',
    '*/ads.js*', '*/ad.js*', '*/ads/*', '*/popunder*', '*/popunder.js*', '*/punder.js*',
    '*/adbanner*', '*/ad_banner*', '*/adserver*', '*/advertisement*', '*/vast.xml*',
    '*/show_ads.js*', '*/pagead/*'
];

// In-page interceptor and ad-blocker script injected on new document
const INTERCEPTOR_SCRIPT = `
(() => {
    if (window.__scraper_interceptor_installed) return;
    window.__scraper_interceptor_installed = true;
    window.__intercepted_download_url = null;
    window.__all_intercepted_urls = [];

    // 1. Anti-Adblock evasion globals
    try {
        window.canRunAds = true;
        window.isAdBlockActive = false;
        window.adblock = false;
        window.fuckAdBlock = undefined;
        window.BlockAdBlock = undefined;
        window.google_ad_client = "ca-pub-1234567890";
        window.adsbygoogle = window.adsbygoogle || [];
        window.adsbygoogle.push = function() { return 1; };
        window.ga = window.ga || function() {};
        window.gtag = window.gtag || function() {};
        window.popns = window.popns || {};
    } catch(e) {}

    // 2. Suppress dialogs & notifications
    try {
        window.alert = function() { console.log('[AdBlock] Suppressed alert'); };
        window.confirm = function() { console.log('[AdBlock] Suppressed confirm'); return true; };
        window.prompt = function() { console.log('[AdBlock] Suppressed prompt'); return null; };
        if (window.Notification) {
            window.Notification.requestPermission = () => Promise.resolve('denied');
            try { Object.defineProperty(window.Notification, 'permission', { get: () => 'denied' }); } catch(e) {}
        }
    } catch(e) {}

    // 3. Ad-blocking CSS
    function injectAdBlockStyles() {
        if (document.getElementById('__scraper_adblock_css')) return;
        const style = document.createElement('style');
        style.id = '__scraper_adblock_css';
        style.textContent = \`
            iframe[src*="ad"]:not([src*="cloudflare"]):not([src*="turnstile"]):not([src*="cdn-cgi"]):not([src*="challenge"]),
            iframe[src*="pop"]:not([src*="cloudflare"]):not([src*="turnstile"]):not([src*="cdn-cgi"]):not([src*="challenge"]),
            iframe[src*="banner"]:not([src*="cloudflare"]):not([src*="turnstile"]):not([src*="cdn-cgi"]):not([src*="challenge"]),
            iframe[src*="doubleclick"], iframe[src*="googlesyndication"], iframe[src*="googleadservices"],
            iframe[id*="ad_"]:not([id*="turnstile"]):not([id*="cf-"]), iframe[id*="google_ads"],
            .ad, .ads, .advert, .advertisement, .ad-box, .ad-container, .ad-banner,
            .ad-placement, .ad-wrapper, .ad-slot, .banner-ad, .sponsor, .sponsored,
            .pop-up, .pop-under, .popup-overlay, .overlay-ad, .floating-ad,
            .interstitial, .push-notification-modal, .notification-prompt,
            [id^="ad-"], [id^="ad_"], [id*="-ad-"], [id*="_ad_"],
            [class^="ad-"], [class^="ad_"], [class*="-ad-"], [class*="_ad_"],
            div[style*="z-index: 2147483647"], div[style*="z-index: 999999"],
            #adblock-warning, .adblock-notice, .adblock-overlay {
                display: none !important;
                visibility: hidden !important;
                opacity: 0 !important;
                pointer-events: none !important;
                width: 0 !important;
                height: 0 !important;
            }
        \`;
        (document.head || document.documentElement).appendChild(style);
    }
    try { injectAdBlockStyles(); } catch(e) {}
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectAdBlockStyles);
    }

    // 4. Download URL extractor & parser
    function isDownloadCdnUrl(url) {
        if (!url || typeof url !== 'string') return false;
        return (url.includes('dlproxy') || url.includes('sig=') || url.includes('sig%3D')) && !url.includes('turnstile') && !url.includes('challenge');
    }

    function extractAndStore(data, sourceUrl) {
        if (!data) return;
        let candidate = null;
        if (typeof data === 'object') {
            if (data.url) candidate = data.url;
            else if (data.download_url) candidate = data.download_url;
            else if (data.link) candidate = data.link;
            else if (data.data && data.data.url) candidate = data.data.url;
            else {
                for (const k of Object.keys(data)) {
                    const v = data[k];
                    if (typeof v === 'string' && (v.includes('dlproxy') || v.includes('sig%3D') || v.includes('sig='))) {
                        candidate = v;
                        break;
                    }
                }
            }
        } else if (typeof data === 'string') {
            try {
                const j = JSON.parse(data);
                if (j && j.url) candidate = j.url;
            } catch(e) {}
            if (!candidate && (data.includes('dlproxy') || data.includes('sig%3D') || data.includes('sig='))) {
                const m = data.match(/https?(?::|%3A)(?:\\/|%2F){2}[^\\s"'>]+/i);
                if (m) candidate = m[0];
            }
        }

        if (!candidate && sourceUrl && isDownloadCdnUrl(sourceUrl)) {
            candidate = sourceUrl;
        }

        if (candidate && typeof candidate === 'string') {
            let decoded = candidate;
            try { decoded = decodeURIComponent(candidate); } catch(e) {}
            if (decoded.startsWith('http') && isDownloadCdnUrl(decoded)) {
                window.__intercepted_download_url = decoded;
                console.log('[Puppeteer Interceptor Captured URL]:', decoded);
            }
        }
    }

    // 5. Hook Fetch & XHR
    const originalFetch = window.fetch;
    window.fetch = async function (...args) {
        const response = await originalFetch.apply(this, args);
        try {
            const clone = response.clone();
            clone.text().then(bodyText => {
                let parsed = bodyText;
                try { parsed = JSON.parse(bodyText); } catch (e) {}
                extractAndStore(parsed, args[0]);
            }).catch(() => {});
        } catch (e) {}
        return response;
    };

    const OriginalXHR = window.XMLHttpRequest;
    window.XMLHttpRequest = function () {
        const xhr = new OriginalXHR();
        const originalOpen = xhr.open;
        xhr.open = function (method, url, ...rest) {
            this._interceptedUrl = url;
            return originalOpen.apply(this, [method, url, ...rest]);
        };

        const originalSend = xhr.send;
        xhr.send = function (...args) {
            this.addEventListener('load', function () {
                let parsed = this.responseText;
                try { parsed = JSON.parse(this.responseText); } catch (e) {}
                extractAndStore(parsed, this._interceptedUrl || this.responseURL);
            });
            return originalSend.apply(this, args);
        };
        return xhr;
    };

    // 6. Hook window.open & anchor clicks
    window.open = function (url) {
        if (url && typeof url === 'string') {
            extractAndStore(url, url);
        }
        return null;
    };

    const origAnchorClick = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function () {
        if (this.href) {
            extractAndStore(this.href, this.href);
            if (isDownloadCdnUrl(this.href)) return; // prevent browser download streaming
        }
        return origAnchorClick.apply(this, arguments);
    };

    document.addEventListener('click', (e) => {
        const a = e.target.closest('a');
        if (a && a.href && isDownloadCdnUrl(a.href)) {
            extractAndStore(a.href, a.href);
            e.preventDefault();
            e.stopPropagation();
        }
    }, true);
})();
`;

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function isValidDownloadUrl(url, originalLink) {
    if (!url || typeof url !== 'string') return false;
    let decoded = decodeURIComponent(url).trim();
    if (!decoded.startsWith('http')) return false;

    // Filter out static assets
    if (/\.(js|css|woff2?|ttf|png|jpg|jpeg|gif|svg|ico|json|html)(\?.*)?$/i.test(decoded)) {
        return false;
    }

    const clean = decoded.replace(/\/+$/, '');
    const cleanOrig = originalLink ? originalLink.replace(/\/+$/, '') : '';
    if (clean === cleanOrig || clean === 'https://datanodes.to/download' || clean === 'https://datanodes.to') {
        return false;
    }

    // Direct dlproxy CDN tunnel URL
    if (decoded.includes('dlproxy') && (decoded.includes('/download/') || decoded.includes('sig='))) {
        return true;
    }

    // Signature link on CDN
    if ((decoded.includes('?sig=') || decoded.includes('&sig=')) && !decoded.includes('cloudflare.com') && !decoded.includes('google.com')) {
        return true;
    }

    try {
        const parsed = new URL(decoded);
        if (parsed.hostname && parsed.hostname.includes('dlproxy')) {
            return true;
        }
    } catch(e) {}

    return false;
}

/**
 * Cloudflare Turnstile Solver for Puppeteer
 */
async function solveTurnstileIfPresent(page, log) {
    try {
        const status = await page.evaluate(() => {
            // Check if already solved
            const tokenInputs = Array.from(document.querySelectorAll('input[name*="turnstile"], input[name="cf-turnstile-response"], [name="cf_challenge_response"]'));
            for (const inp of tokenInputs) {
                if (inp.value && inp.value.trim().length > 10) {
                    return { status: 'solved' };
                }
            }

            // Check for Turnstile iframe
            const iframes = Array.from(document.querySelectorAll('iframe'));
            for (const iframe of iframes) {
                const src = (iframe.src || '').toLowerCase();
                const id = (iframe.id || '').toLowerCase();
                const name = (iframe.name || '').toLowerCase();
                const parentCls = (iframe.parentElement ? iframe.parentElement.className || '' : '').toLowerCase();

                const isCf = src.includes('turnstile') || src.includes('challenge') || src.includes('cloudflare') ||
                             src.includes('cdn-cgi') || id.includes('cf-') || name.includes('cf-') ||
                             parentCls.includes('cf-turnstile') || parentCls.includes('turnstile');

                if (isCf) {
                    try { iframe.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' }); } catch(e) {}
                    const rect = iframe.getBoundingClientRect();
                    return {
                        status: 'unsolved',
                        rect: {
                            left: Math.round(rect.left),
                            top: Math.round(rect.top),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        }
                    };
                }
            }

            // Check turnstile container
            const container = document.querySelector('.cf-turnstile, #turnstile-wrapper, [class*="turnstile"], #challenge-stage');
            if (container) {
                try { container.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' }); } catch(e) {}
                const rect = container.getBoundingClientRect();
                return {
                    status: 'container_only',
                    rect: {
                        left: Math.round(rect.left),
                        top: Math.round(rect.top),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    }
                };
            }

            return { status: 'not_found' };
        });

        if (!status || status.status === 'not_found') return false;
        if (status.status === 'solved') return true;

        const rect = status.rect || { left: 0, top: 0, width: 300, height: 65 };
        const clickX = Math.max(10, rect.left + Math.min(35, Math.max(25, Math.floor(rect.width * 0.12))));
        const clickY = Math.max(10, rect.top + Math.max(20, Math.floor(rect.height / 2)));

        if (log) log(`[Puppeteer] Turnstile detected at (${clickX}, ${clickY}), clicking...`);

        // Perform hardware mouse click via Puppeteer CDP Input
        await page.mouse.move(clickX, clickY);
        await sleep(50);
        await page.mouse.down({ button: 'left' });
        await sleep(70);
        await page.mouse.up({ button: 'left' });
        await sleep(200);

        return true;
    } catch(err) {
        return false;
    }
}

/**
 * Click Step 1 Free Download button
 */
async function clickFreeDownloadButton(page) {
    try {
        const clicked = await page.evaluate(() => {
            // Purge ad overlays
            const overlays = Array.from(document.querySelectorAll('div[style*="position: fixed"], div[style*="position: absolute"]'));
            for (const ov of overlays) {
                const z = parseInt(window.getComputedStyle(ov).zIndex) || 0;
                if (z > 999 && ov.children.length === 0) {
                    try { ov.remove(); } catch(e) {}
                }
            }

            const candidates = Array.from(document.querySelectorAll('button, a, input[type="button"], input[type="submit"], input[type="image"]'));
            for (const el of candidates) {
                const text = (el.innerText || el.value || el.textContent || '').trim().toLowerCase();
                const id = (el.id || '').toLowerCase();
                const name = (el.name || '').toLowerCase();
                const cls = (el.className || '').toLowerCase();

                if (text.includes('free download') || text === 'free' || text === 'slow download' ||
                    id === 'method_free' || name === 'method_free' || cls.includes('btn-free')) {
                    
                    try { el.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' }); } catch(e) {}
                    el.click();
                    if (el.form) {
                        try { el.form.requestSubmit ? el.form.requestSubmit(el) : el.form.submit(); } catch(e) {}
                    }
                    return true;
                }
            }
            return false;
        });

        if (clicked) return true;

        // Fallback selectors
        const selectors = ['#method_free', 'input[name="method_free"]', 'button.btn-free'];
        for (const sel of selectors) {
            const el = await page.$(sel);
            if (el) {
                await el.click();
                return true;
            }
        }
    } catch (e) {}
    return false;
}

/**
 * Click Step 2 Download / Create Link button or submit form
 */
async function clickStep2DownloadButton(page) {
    try {
        const result = await page.evaluate(() => {
            const bodyText = document.body ? document.body.innerText : '';
            const waitMatch = bodyText.match(/wait\s+(\d+)\s+sec/i) || bodyText.match(/starting in\s+(\d+)/i) || bodyText.match(/(\d+)\s+seconds/i);
            if (waitMatch && parseInt(waitMatch[1]) > 0) {
                return { status: 'countdown', seconds: parseInt(waitMatch[1]) };
            }

            const candidates = Array.from(document.querySelectorAll('button, a, input[type="button"], input[type="submit"], input[type="image"]'));
            for (const el of candidates) {
                const text = (el.innerText || el.value || el.textContent || '').trim();
                const textLower = text.toLowerCase();
                const id = (el.id || '').toLowerCase();
                const name = (el.name || '').toLowerCase();
                const cls = (el.className || '').toLowerCase();

                if (textLower === 'free download' || id === 'method_free' || name === 'method_free') continue;
                if (textLower.includes('premium') || textLower.includes('high speed') || id.includes('premium')) continue;

                const isDownloadBtn = id.includes('download') || id.includes('btn_dl') || name.includes('download') ||
                    cls.includes('download') || cls.includes('btn_dl') ||
                    /^(download|create download link|direct download|download now|get link|generate link|download file)$/i.test(text) ||
                    (textLower.includes('download') && !textLower.includes('turbo'));

                if (isDownloadBtn && !el.disabled && el.offsetParent !== null) {
                    try { el.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' }); } catch(e) {}
                    el.click();
                    if (el.form) {
                        try { el.form.requestSubmit ? el.form.requestSubmit(el) : el.form.submit(); } catch(e) {}
                    }
                    return { status: 'clicked', text: text };
                }
            }

            // Fallback: If form with op=download2 exists and has turnstile response, submit form directly
            const form = document.querySelector('form[name="F1"], form[action*="download"], form');
            if (form) {
                const op = form.querySelector('input[name="op"]');
                if (op && op.value === 'download2') {
                    try { form.requestSubmit ? form.requestSubmit() : form.submit(); return { status: 'form_submitted' }; } catch(e) {}
                }
            }

            return { status: 'not_found' };
        });

        if (result && (result.status === 'clicked' || result.status === 'form_submitted')) return true;

        // Fallback selectors
        const selectors = ['#btn_dl', 'button[name*="down"]', 'input[name*="down"]'];
        for (const sel of selectors) {
            const el = await page.$(sel);
            if (el) {
                await el.click();
                return true;
            }
        }
    } catch (e) {}
    return false;
}

/**
 * Scrape a single link using Puppeteer connected over CDP
 */
async function scrapeLinkWithPuppeteer(browser, link, options = {}) {
    const log = options.log || console.log;
    const maxRetries = options.maxRetries || 3;
    const filename = link.split('/').pop() || link;

    let retryCount = 0;
    while (retryCount < maxRetries) {
        let page = null;
        let cdp = null;
        let capturedDirectUrl = null;

        try {
            log(`[Puppeteer] Processing: ${filename} (Attempt ${retryCount + 1}/${maxRetries})`);

            const pages = await browser.pages();
            page = pages[0] || await browser.newPage();

            // Set up CDP session
            cdp = await page.createCDPSession();
            try {
                await cdp.send('Network.enable');
                await cdp.send('Network.setBlockedURLs', { urls: BLOCKED_AD_PATTERNS });
                await cdp.send('Page.setDownloadBehavior', { behavior: 'deny' });
                await cdp.send('Browser.setDownloadBehavior', { behavior: 'deny' });
            } catch(e) {}

            // Real-time CDP Network Listener for instant URL extraction
            cdp.on('Network.requestWillBeSent', (event) => {
                const reqUrl = event.request ? event.request.url : '';
                if (isValidDownloadUrl(reqUrl, link)) {
                    capturedDirectUrl = decodeURIComponent(reqUrl);
                    log(`[Puppeteer CDP Event] Caught direct download URL: ${capturedDirectUrl}`);
                }
            });

            page.on('request', (req) => {
                const reqUrl = req.url();
                if (isValidDownloadUrl(reqUrl, link)) {
                    capturedDirectUrl = decodeURIComponent(reqUrl);
                    log(`[Puppeteer Request] Caught direct download URL: ${capturedDirectUrl}`);
                }
            });

            page.on('framenavigated', (frame) => {
                const frameUrl = frame.url();
                if (isValidDownloadUrl(frameUrl, link)) {
                    capturedDirectUrl = decodeURIComponent(frameUrl);
                    log(`[Puppeteer Navigation] Caught direct download URL: ${capturedDirectUrl}`);
                }
            });

            // Pre-inject interceptor script before page JS executes
            await page.evaluateOnNewDocument(INTERCEPTOR_SCRIPT);

            // Navigate to link
            await page.goto(link, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});

            // Inject interceptor into active DOM as well
            await page.evaluate(INTERCEPTOR_SCRIPT).catch(() => {});

            // Check for Bad Gateway / Error 502
            const bodyContent = await page.evaluate(() => document.body ? document.body.innerText : '');
            if (bodyContent.includes('Bad Gateway') || bodyContent.includes('Error 502')) {
                log(`[Puppeteer] Server error 502/Bad Gateway, retrying...`);
                await sleep(2000);
                retryCount++;
                continue;
            }

            if (bodyContent.includes('File not found') || bodyContent.includes('File was deleted')) {
                throw new Error('File not found on server');
            }

            // Step 1: Handle Turnstile and click Free Download button
            let buttonClicked = false;
            for (let i = 0; i < 30; i++) {
                if (capturedDirectUrl) break;

                await solveTurnstileIfPresent(page, log);

                if (await clickFreeDownloadButton(page)) {
                    buttonClicked = true;
                    log(`[Puppeteer] -> Clicked Free Download button.`);
                    break;
                }
                await sleep(1000);
            }

            if (!buttonClicked && !capturedDirectUrl) {
                const alreadyOnStep2 = await page.evaluate(() => {
                    const t = document.body ? document.body.innerText : '';
                    return t.includes('Starting in') || t.includes('Starts automatically') || t.includes('Download') || location.href.includes('/download');
                });
                if (!alreadyOnStep2) {
                    throw new Error('Timeout waiting for Free Download button');
                }
            }

            // Step 2: Wait for countdown / verification and capture direct download URL
            log(`[Puppeteer] Waiting for countdown / captcha and capturing download URL...`);
            let downloadUrl = capturedDirectUrl;

            for (let tick = 0; tick < 60; tick++) {
                if (capturedDirectUrl) {
                    downloadUrl = capturedDirectUrl;
                    break;
                }

                // Re-evaluate interceptor
                await page.evaluate(INTERCEPTOR_SCRIPT).catch(() => {});

                // 1. Check window.__intercepted_download_url
                const captured = await page.evaluate(() => window.__intercepted_download_url || null);
                if (captured && isValidDownloadUrl(captured, link)) {
                    downloadUrl = decodeURIComponent(captured);
                    break;
                }

                // 2. Check current URL
                const currentUrl = page.url();
                if (isValidDownloadUrl(currentUrl, link)) {
                    downloadUrl = decodeURIComponent(currentUrl);
                    break;
                }

                // 3. Solve Turnstile if present on Step 2
                await solveTurnstileIfPresent(page, log);

                // 4. Click final Download / Create Link button or submit form
                await clickStep2DownloadButton(page);

                // 5. Check direct download links in DOM
                const directLink = await page.evaluate(() => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    for (const a of links) {
                        const h = a.href || '';
                        if (h.includes('dlproxy') || h.includes('?sig=') || h.includes('&sig=')) return h;
                    }
                    return null;
                });
                if (directLink && isValidDownloadUrl(directLink, link)) {
                    downloadUrl = decodeURIComponent(directLink);
                    break;
                }

                await sleep(1000);
            }

            if (!downloadUrl && capturedDirectUrl) {
                downloadUrl = capturedDirectUrl;
            }

            if (downloadUrl && isValidDownloadUrl(downloadUrl, link)) {
                log(`[Puppeteer] SUCCESS! Captured download URL: ${downloadUrl}`);
                return { success: true, url: downloadUrl, error: null };
            }

            retryCount++;
            if (retryCount < maxRetries) {
                log(`[Puppeteer] URL not captured, retrying (${retryCount}/${maxRetries})...`);
                await sleep(2000);
            }
        } catch (err) {
            log(`[Puppeteer] Error: ${err.message}`);
            if (err.message.includes('File not found')) {
                return { success: false, url: null, error: err.message };
            }
            retryCount++;
            if (retryCount < maxRetries) {
                await sleep(2000);
            } else {
                return { success: false, url: null, error: err.message };
            }
        }
    }

    return { success: false, url: null, error: 'Max retries reached' };
}

/**
 * Main Runner function
 */
async function main() {
    const args = process.argv.slice(2);
    let endpointUrl = 'http://127.0.0.1:9222';
    let targetLink = null;
    let inputFile = 'links.txt';
    let outputFile = 'output.txt';

    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--cdp' || args[i] === '--endpoint') {
            endpointUrl = args[++i];
        } else if (args[i] === '--link') {
            targetLink = args[++i];
        } else if (args[i] === '--input') {
            inputFile = args[++i];
        } else if (args[i] === '--output') {
            outputFile = args[++i];
        } else if (args[i].startsWith('http://') || args[i].startsWith('https://') || args[i].startsWith('ws://')) {
            if (args[i].includes('127.0.0.1') || args[i].includes('localhost')) {
                endpointUrl = args[i];
            } else {
                targetLink = args[i];
            }
        }
    }

    console.log('='.repeat(60));
    console.log('        PUPPETEER CDP SCRAPER & EXTRACTOR');
    console.log('='.repeat(60));
    console.log(`Connecting to CDP endpoint: ${endpointUrl}`);

    const browser = await puppeteer.connect({
        browserURL: endpointUrl.startsWith('ws') ? undefined : endpointUrl,
        browserWSEndpoint: endpointUrl.startsWith('ws') ? endpointUrl : undefined,
        defaultViewport: null
    });

    // Auto-close any rogue popup tabs created by aggressive ads
    browser.on('targetcreated', async (target) => {
        try {
            if (target.type() === 'page') {
                const newPage = await target.page();
                if (newPage) {
                    const url = newPage.url();
                    if (url !== 'about:blank' && !url.includes('datanodes.to') && !url.includes('dlproxy')) {
                        console.log(`[Puppeteer] Auto-closing rogue popup page: ${url}`);
                        await newPage.close().catch(() => {});
                    }
                }
            }
        } catch(e) {}
    });

    let links = [];
    if (targetLink) {
        links = [targetLink];
    } else if (fs.existsSync(inputFile)) {
        links = fs.readFileSync(inputFile, 'utf-8').split('\n').map(s => s.trim()).filter(Boolean);
    }

    if (links.length === 0) {
        console.error(`No links provided or found in ${inputFile}`);
        await browser.disconnect();
        process.exit(1);
    }

    console.log(`Loaded ${links.length} link(s) to process.`);
    const results = [];

    for (let i = 0; i < links.length; i++) {
        const link = links[i];
        console.log(`\n[${i + 1}/${links.length}] Starting: ${link}`);
        const result = await scrapeLinkWithPuppeteer(browser, link);
        if (result.success) {
            results.push(result.url);
        } else {
            results.push(`# Failed: ${link} (${result.error})`);
        }

        // Save progress to output file
        fs.writeFileSync(outputFile, results.filter(Boolean).join('\n') + '\n', 'utf-8');
    }

    console.log('\n' + '='.repeat(60));
    console.log('                 EXTRACTION COMPLETE');
    console.log('='.repeat(60));
    console.log(`Total Processed: ${links.length}`);
    console.log(`Saved output to: ${outputFile}`);
    console.log('Results:');
    results.forEach((r, idx) => console.log(`  [${idx + 1}] ${r}`));

    await browser.disconnect();
}

if (require.main === module) {
    main().catch(err => {
        console.error('Fatal Scraper Error:', err);
        process.exit(1);
    });
}

module.exports = {
    scrapeLinkWithPuppeteer,
    solveTurnstileIfPresent,
    clickFreeDownloadButton,
    clickStep2DownloadButton,
    isValidDownloadUrl,
    BLOCKED_AD_PATTERNS,
    INTERCEPTOR_SCRIPT
};
