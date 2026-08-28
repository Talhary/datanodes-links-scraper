import os
import sys
import time
import shutil
import tempfile
import multiprocessing as mp
from urllib.parse import urlparse, unquote
from datetime import datetime
from seleniumbase import SB
from selenium.webdriver.common.action_chains import ActionChains

# Rich library components for terminal UI
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

# Force UTF-8 encoding on Windows to prevent console charmap crashes
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

#--------------[Constants]----------------
INPUT_FILE = "links.txt"
OUTPUT_FILE = "output.txt"
NUM_WORKERS = 3  # Number of parallel browser instances

CHROME_PATHS = [
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files/Google/Chrome Beta/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome Beta/Application/chrome.exe"
]

# Check if Chrome is installed in the default locations
BROWSER_PATH = None
for path in CHROME_PATHS:
    if os.path.exists(path):    
        BROWSER_PATH = path
        break

#--------------[Ad Blocker & Network Filter Rules]--------------
BLOCKED_AD_URLS = [
    # Prevent browser streaming of direct downloads
    "*dlproxy.uk*", "*dlproxy.com*", "*dlproxy.net*", "*dlproxy*",
    # Ad Networks & Exchanges
    "*doubleclick.net*", "*googlesyndication.com*", "*google-analytics.com*", "*googleadservices.com*",
    "*adservice.google.*", "*pagead2.googlesyndication.com*", "*adnxs.com*", "*ads.pubmatic.com*",
    "*rubiconproject.com*", "*openx.net*", "*smartadserver.com*", "*casalemedia.com*",
    "*bidswitch.net*", "*amazon-adsystem.com*", "*moatads.com*", "*criteo.com*", "*criteo.net*",
    "*scorecardresearch.com*", "*outbrain.com*", "*taboola.com*", "*mgid.com*", "*revcontent.com*",
    "*yandex.ru/ads*", "*an.yandex.ru*", "*adfox.ru*", "*zemanta.com*", "*sharethrough.com*",
    "*yieldmo.com*", "*triplelift.com*", "*infolinks.com*", "*sovrn.com*", "*exponential.com*",
    "*conversantmedia.com*", "*lijit.com*", "*sonobi.com*", "*undertone.com*", "*contextweb.com*",
    # Aggressive Popunder, Push & Redirect Networks
    "*popads.net*", "*popcash.net*", "*propellerads.com*", "*exoclick.com*", "*adcash.com*",
    "*adsterra.com*", "*onclickbright.com*", "*monetag.com*", "*hilltopads.com*", "*clickadu.com*",
    "*trafficjunky.*", "*juicyads.*", "*yllix.com*", "*ad-maven.com*", "*ad-delivery.net*",
    "*adtrue.com*", "*tsyndicate.com*", "*clicksor.com*", "*vidoomy.com*", "*teads.tv*",
    "*gumgum.com*", "*zergnet.com*", "*nativeads.com*", "*adpushup.com*", "*ezoic.net*",
    "*media.net*", "*adblade.com*", "*richaudience.com*", "*setupad.com*", "*admanmedia.com*",
    "*trafficstars.com*", "*ero-advertising.com*", "*plugrush.com*", "*adxad.com*",
    "*adplexity.com*", "*bidgear.com*", "*evadav.com*", "*rollerads.com*", "*clickaine.com*",
    "*pushground.com*", "*richpush.com*", "*notix.co*", "*propellerclick.com*", "*propu.sh*",
    "*clckhubs.com*", "*onclickmega.com*", "*syndication.exoclick.com*", "*main.exoclick.com*",
    "*adskeeper.co.uk*", "*adskeeper.com*", "*adkernel.com*", "*adoperator.com*",
    # Tracking & Analytics Beacons
    "*hotjar.com*", "*clarity.ms*", "*yandex.metrika*", "*statcounter.com*", "*histats.com*",
    "*quantserve.com*", "*chartbeat.com*", "*optimizely.com*", "*crazyegg.com*",
    "*mouseflow.com*", "*luckyorange.com*", "*inspectlet.com*", "*clicky.com*",
    # Coin miners & crypto drainers
    "*coinhive.com*", "*coin-hive.com*", "*crypto-loot.com*", "*jsecoin.com*",
    # Generic Ad URLs
    "*/ads.js*", "*/ad.js*", "*/ads/*", "*/popunder*", "*/popunder.js*", "*/punder.js*",
    "*/adbanner*", "*/ad_banner*", "*/adserver*", "*/advertisement*", "*/vast.xml*",
    "*//*/ad-delivery/*", "*/show_ads.js*", "*/pagead/*"
]

# ---------------------------------------------------------------------------
# INTERCEPTOR & AD-BLOCKER SCRIPT
#
# 1. Blocks and suppresses all ad networks, popups, popunders, and overlays.
# 2. Bypasses anti-adblock detection scripts.
# 3. Intercepts Fetch API, XHR, window.open, and clicks to capture download link.
# ---------------------------------------------------------------------------
INTERCEPTOR_SCRIPT = r"""
(() => {
    if (window.__scraper_interceptor_installed) return;
    window.__scraper_interceptor_installed = true;
    window.__intercepted_download_url = null;
    window.__all_intercepted_urls = [];

    // ==========================================
    // 1. ANTI-ADBLOCK EVASION & DUMMY GLOBALS
    // ==========================================
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

    // ==========================================
    // 2. SUPPRESS POPUP DIALOGS & NOTIFICATIONS
    // ==========================================
    try {
        window.alert = function() { console.log('[AdBlock] Suppressed alert dialog'); };
        window.confirm = function() { console.log('[AdBlock] Suppressed confirm dialog'); return true; };
        window.prompt = function() { console.log('[AdBlock] Suppressed prompt dialog'); return null; };
        if (window.Notification) {
            window.Notification.requestPermission = () => Promise.resolve('denied');
            try {
                Object.defineProperty(window.Notification, 'permission', { get: () => 'denied' });
            } catch(e) {}
        }
        if (navigator.permissions && navigator.permissions.query) {
            const origQuery = navigator.permissions.query;
            navigator.permissions.query = (params) => {
                if (params && params.name === 'notifications') {
                    return Promise.resolve({ state: 'denied', onchange: null });
                }
                return origQuery.call(navigator.permissions, params);
            };
        }
    } catch(e) {}

    // ==========================================
    // 3. INJECT COMPREHENSIVE AD-BLOCKING CSS
    // ==========================================
    function injectAdBlockStyles() {
        if (document.getElementById('__scraper_adblock_css')) return;
        const style = document.createElement('style');
        style.id = '__scraper_adblock_css';
        style.textContent = `
            /* Ad iframes - preserving Cloudflare Turnstile & challenge frames */
            iframe[src*="ad"]:not([src*="cloudflare"]):not([src*="turnstile"]):not([src*="cdn-cgi"]):not([src*="challenge"]),
            iframe[src*="pop"]:not([src*="cloudflare"]):not([src*="turnstile"]):not([src*="cdn-cgi"]):not([src*="challenge"]),
            iframe[src*="banner"]:not([src*="cloudflare"]):not([src*="turnstile"]):not([src*="cdn-cgi"]):not([src*="challenge"]),
            iframe[src*="doubleclick"],
            iframe[src*="googlesyndication"],
            iframe[src*="googleadservices"],
            iframe[id*="ad_"]:not([id*="turnstile"]):not([id*="cf-"]),
            iframe[id*="google_ads"],
            /* Ad elements, containers, floating ads, modals, push prompts */
            .ad, .ads, .advert, .advertisement, .ad-box, .ad-container, .ad-banner,
            .ad-placement, .ad-wrapper, .ad-slot, .banner-ad, .sponsor, .sponsored,
            .pop-up, .pop-under, .popup-overlay, .overlay-ad, .floating-ad,
            .interstitial, .push-notification-modal, .notification-prompt,
            [id^="ad-"], [id^="ad_"], [id*="-ad-"], [id*="_ad_"],
            [class^="ad-"], [class^="ad_"], [class*="-ad-"], [class*="_ad_"],
            [class*="banner"]:not([class*="banner-main"]):not([class*="hero"]),
            [id*="banner"]:not([id*="banner-main"]),
            [class*="sponsored"], [id*="sponsored"],
            [data-ad], [data-ad-unit], [data-ad-slot], [data-ad-client],
            div[style*="z-index: 2147483647"],
            div[style*="z-index: 999999"],
            #adblock-warning, .adblock-notice, .adblock-overlay {
                display: none !important;
                visibility: hidden !important;
                opacity: 0 !important;
                pointer-events: none !important;
                width: 0 !important;
                height: 0 !important;
                max-width: 0 !important;
                max-height: 0 !important;
                clip: rect(0, 0, 0, 0) !important;
            }
        `;
        (document.head || document.documentElement).appendChild(style);
    }
    try { injectAdBlockStyles(); } catch(e) {}
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectAdBlockStyles);
    }

    // ==========================================
    // 4. CONTINUOUS AD & OVERLAY PURGER
    // ==========================================
    function purgeAdArtifacts() {
        try {
            // Remove transparent / high z-index clickjack overlays
            const overlays = document.querySelectorAll('div[style*="position: fixed"], div[style*="position: absolute"]');
            for (const ov of overlays) {
                const z = parseInt(window.getComputedStyle(ov).zIndex) || 0;
                if (z >= 999 && ov.children.length === 0) {
                    ov.remove();
                }
            }
            // Remove ad iframes
            const iframes = document.querySelectorAll('iframe');
            for (const ifr of iframes) {
                const s = (ifr.src || '').toLowerCase();
                const isCf = s.includes('cloudflare') || s.includes('turnstile') || s.includes('cdn-cgi') || s.includes('challenge');
                if (!isCf && (s.includes('ad') || s.includes('pop') || s.includes('doubleclick') || s.includes('banner') || s.includes('promo'))) {
                    ifr.remove();
                }
            }
            // Ensure body scrolling is not locked by ad overlays
            if (document.body && window.getComputedStyle(document.body).overflow === 'hidden') {
                document.body.style.setProperty('overflow', 'auto', 'important');
            }
        } catch(e) {}
    }

    try {
        const observer = new MutationObserver(() => {
            purgeAdArtifacts();
            injectAdBlockStyles();
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });
    } catch(e) {}

    // ==========================================
    // 5. DIRECT DOWNLOAD URL EXTRACTOR
    // ==========================================
    function isDownloadCdnUrl(url) {
        if (!url || typeof url !== 'string') return false;
        return url.includes('dlproxy') || url.includes('sig=') || url.includes('sig%3D');
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
                const m = data.match(/https?(?::|%3A)(?:\/|%2F){2}[^\s"'>]+/i);
                if (m) candidate = m[0];
            }
        }

        if (!candidate && sourceUrl && (sourceUrl.includes('dlproxy') || sourceUrl.includes('sig='))) {
            candidate = sourceUrl;
        }

        if (candidate && typeof candidate === 'string') {
            let decoded = candidate;
            try { decoded = decodeURIComponent(candidate); } catch(e) {}
            if (decoded.startsWith('http')) {
                window.__intercepted_download_url = decoded;
                console.log('[Scraper Captured Final URL]:', decoded);
            }
        }
    }

    // ==========================================
    // 6. NETWORK API HOOKS (FETCH & XHR)
    // ==========================================
    const originalFetch = window.fetch;
    window.fetch = async function (...args) {
        const response = await originalFetch.apply(this, args);
        try {
            const clone = response.clone();
            clone.text().then(bodyText => {
                let parsedBody = bodyText;
                try { parsedBody = JSON.parse(bodyText); } catch (e) {}
                extractAndStore(parsedBody, args[0]);
            }).catch(err => {});
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
                let parsedBody = this.responseText;
                try { parsedBody = JSON.parse(this.responseText); } catch (e) {}
                extractAndStore(parsedBody, this._interceptedUrl || this.responseURL);
            });
            return originalSend.apply(this, args);
        };
        return xhr;
    };

    // ==========================================
    // 7. WINDOW.OPEN & POPUP / POPUNDER BLOCKER
    // ==========================================
    const originalOpen = window.open;
    window.open = function (url, ...rest) {
        if (url && typeof url === 'string') {
            extractAndStore(url, url);
            if (isDownloadCdnUrl(url)) {
                return null; // Block popup download
            }
        }
        // Block all ad popups/popunders
        console.log('[AdBlock] Blocked window.open popup:', url);
        return null;
    };

    // ==========================================
    // 8. ANCHOR & USER CLICK INTERCEPTORS
    // ==========================================
    const origAnchorClick = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function () {
        if (this.href) {
            extractAndStore(this.href, this.href);
            if (isDownloadCdnUrl(this.href)) {
                return; // BLOCK CHROME FROM STARTING THE FILE DOWNLOAD
            }
        }
        return origAnchorClick.apply(this, arguments);
    };

    document.addEventListener('click', (e) => {
        const a = e.target.closest('a');
        if (a && a.href && isDownloadCdnUrl(a.href)) {
            extractAndStore(a.href, a.href);
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
        }
    }, true);
})();
"""

# JS snippet that reads the captured URL strictly from the active page memory
READ_URL_JS = """
(() => {
    return window.__intercepted_download_url || null;
})();
"""

# JS snippet to clear stored URL (between links)
CLEAR_URL_JS = """
(() => {
    window.__intercepted_download_url = null;
    window.__scraper_interceptor_installed = false;
    try { localStorage.clear(); sessionStorage.clear(); } catch(e) {}
})();
"""


def is_valid_download_url(url: str, original_link: str) -> bool:
    """Strict validation: only accept actual CDN tunnel / dlproxy URLs."""
    if not url or not isinstance(url, str):
        return False
    url = unquote(url).strip()
    if not url.startswith("http"):
        return False

    # Reject page-level URLs
    clean = url.rstrip("/")
    if clean in (original_link.rstrip("/"), "https://datanodes.to/download", "https://datanodes.to"):
        return False

    # Accept known CDN patterns
    if "dlproxy" in url:
        return True
    if "?sig=" in url or "&sig=" in url:
        return True

    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "datanodes.to" and ("/download/" in parsed.path or len(parsed.path) > 10):
        return True

    return False


# JS snippet to cancel any active download inside chrome://downloads via Shadow DOM
CANCEL_DOWNLOADS_JS = """
(() => {
    try {
        const manager = document.querySelector('downloads-manager');
        if (!manager || !manager.shadowRoot) return;
        const items = manager.shadowRoot.querySelectorAll('downloads-item');
        items.forEach(item => {
            if (item.shadowRoot) {
                const cancelBtn = item.shadowRoot.querySelector('#cancel');
                if (cancelBtn && !cancelBtn.hidden && !cancelBtn.disabled) {
                    cancelBtn.click();
                }
                const pauseBtn = item.shadowRoot.querySelector('#pause');
                if (pauseBtn && !pauseBtn.hidden && !pauseBtn.disabled) {
                    pauseBtn.click();
                }
            }
        });
    } catch(e) {}
})();
"""


def cancel_active_downloads(sb):
    """Navigates to chrome://downloads/ and cancels any in-progress downloads via Shadow DOM."""
    try:
        sb.open("chrome://downloads/")
        time.sleep(0.3)
        sb.execute_script(CANCEL_DOWNLOADS_JS)
        time.sleep(0.2)
        sb.open("about:blank")
    except Exception:
        try:
            sb.open("about:blank")
        except Exception:
            pass


#--------------[Helper Click & Captcha Functions]--------------
def solve_turnstile_if_present(sb, worker_id, log):
    """
    Multi-layered solver for Cloudflare Turnstile:
    1. Checks if already solved (token populated in input).
    2. Uses CDP Input.dispatchMouseEvent at exact checkbox viewport coordinates.
    3. Uses Selenium ActionChains offset click on Turnstile iframe.
    4. Switches into iframe and attempts direct DOM/Shadow-DOM click.
    5. Falls back to SeleniumBase uc_gui_click_captcha.
    """
    try:
        # Step A: Check Turnstile status in DOM
        status_info = sb.execute_script("""
        (() => {
            // 1. Check if already solved
            const tokenInputs = Array.from(document.querySelectorAll('input[name*="turnstile"], input[name="cf-turnstile-response"], [name="cf_challenge_response"]'));
            for (const inp of tokenInputs) {
                if (inp.value && inp.value.trim().length > 10) {
                    return { status: "solved" };
                }
            }

            // 2. Look for Turnstile iframe
            const iframes = Array.from(document.querySelectorAll('iframe'));
            for (let i = 0; i < iframes.length; i++) {
                const iframe = iframes[i];
                const src = (iframe.src || '').toLowerCase();
                const id = (iframe.id || '').toLowerCase();
                const name = (iframe.name || '').toLowerCase();
                const parentCls = (iframe.parentElement ? iframe.parentElement.className || '' : '').toLowerCase();

                const isCf = src.includes('turnstile') || src.includes('challenge') || src.includes('cloudflare') ||
                             src.includes('cdn-cgi') || id.includes('cf-') || name.includes('cf-') ||
                             parentCls.includes('cf-turnstile') || parentCls.includes('turnstile');

                if (isCf) {
                    try {
                        iframe.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
                    } catch(e) {}
                    const rect = iframe.getBoundingClientRect();
                    return {
                        status: "unsolved",
                        rect: {
                            left: Math.round(rect.left),
                            top: Math.round(rect.top),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        }
                    };
                }
            }

            // 3. Check container without loaded iframe
            const container = document.querySelector('.cf-turnstile, #turnstile-wrapper, [class*="turnstile"], #challenge-stage');
            if (container) {
                try {
                    container.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
                } catch(e) {}
                const rect = container.getBoundingClientRect();
                return {
                    status: "container_only",
                    rect: {
                        left: Math.round(rect.left),
                        top: Math.round(rect.top),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    }
                };
            }

            return { status: "not_found" };
        })();
        """)

        if not status_info or status_info.get("status") == "not_found":
            return False

        if status_info.get("status") == "solved":
            return True

        rect = status_info.get("rect", {})
        left = rect.get("left", 0)
        top = rect.get("top", 0)
        width = rect.get("width", 300)
        height = rect.get("height", 65)

        # The Turnstile checkbox is located on the left (~25-35px from left edge) and vertically centered
        click_x = max(10, left + min(35, max(25, int(width * 0.12))))
        click_y = max(10, top + max(20, int(height / 2)))

        log(f"[Worker {worker_id}]   Turnstile detected (pos: {click_x},{click_y}), solving...", "dim")

        # Layer 1: CDP Mouse Events (trusted hardware input directly to Chrome)
        try:
            sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                "type": "mouseMoved",
                "x": int(click_x),
                "y": int(click_y)
            })
            time.sleep(0.04)
            sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                "type": "mousePressed",
                "x": int(click_x),
                "y": int(click_y),
                "button": "left",
                "clickCount": 1
            })
            time.sleep(0.06)
            sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                "type": "mouseReleased",
                "x": int(click_x),
                "y": int(click_y),
                "button": "left",
                "clickCount": 1
            })
            time.sleep(0.15)
        except Exception:
            pass

        # Layer 2: Selenium ActionChains offset click
        try:
            iframes = sb.driver.find_elements("tag name", "iframe")
            for iframe in iframes:
                src = iframe.get_attribute("src") or ""
                if any(k in src.lower() for k in ["turnstile", "challenge", "cloudflare", "cdn-cgi"]):
                    actions = ActionChains(sb.driver)
                    actions.move_to_element_with_offset(iframe, 30, int(iframe.size.get("height", 60) / 2))
                    actions.click()
                    actions.perform()
                    break
        except Exception:
            pass

        # Layer 3: Switch into iframe and click checkbox / shadow root elements
        try:
            iframes = sb.driver.find_elements("tag name", "iframe")
            for iframe in iframes:
                src = iframe.get_attribute("src") or ""
                if any(k in src.lower() for k in ["turnstile", "challenge", "cloudflare", "cdn-cgi"]):
                    try:
                        sb.driver.switch_to.frame(iframe)
                        sb.execute_script("""
                        (() => {
                            const targets = [
                                document.querySelector('input[type="checkbox"]'),
                                document.querySelector('.ctp-checkbox-label'),
                                document.querySelector('#challenge-stage'),
                                document.querySelector('label'),
                                document.querySelector('body > div')
                            ];
                            for (const t of targets) {
                                if (t) { t.click(); return; }
                            }
                            const all = document.querySelectorAll('*');
                            for (const el of all) {
                                if (el.shadowRoot) {
                                    const cb = el.shadowRoot.querySelector('input[type="checkbox"], label, .ctp-checkbox-label, #challenge-stage, div');
                                    if (cb) { cb.click(); return; }
                                }
                            }
                        })();
                        """)
                    finally:
                        sb.driver.switch_to.default_content()
                    break
        except Exception:
            try:
                sb.driver.switch_to.default_content()
            except Exception:
                pass

        # Layer 4: Fallback to SeleniumBase uc_gui_click_captcha
        try:
            sb.uc_gui_click_captcha()
        except Exception:
            pass

        return True
    except Exception:
        return False


def click_free_download_button(sb, worker_id, log):
    """Robust multi-strategy clicker for Step 1 Free Download button."""
    try:
        clicked = sb.execute_script("""
        (() => {
            // Remove blocking transparent ad overlays if present
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

                    // If it's a form input, also trigger form submission as fallback
                    if (el.form) {
                        try { el.form.requestSubmit ? el.form.requestSubmit(el) : el.form.submit(); } catch(e) {}
                    }
                    return true;
                }
            }
            return false;
        })();
        """)
        if clicked:
            return True
    except Exception:
        pass

    # SeleniumBase locator fallback
    selectors = [
        '#method_free',
        'input[name="method_free"]',
        'button:contains("Free Download")',
        'a:contains("Free Download")',
        'input[value*="Free Download"]',
        'button:contains("Free")',
        'a:contains("Free")'
    ]
    for sel in selectors:
        try:
            if sb.is_element_visible(sel):
                sb.uc_click(sel)
                return True
        except Exception:
            pass

    return False


def click_step2_download_button(sb, worker_id, log):
    """Robust multi-strategy clicker for Step 2 Download / Create Download Link button."""
    try:
        result = sb.execute_script(r"""
        (() => {
            const bodyText = document.body ? document.body.innerText : '';
            const waitMatch = bodyText.match(/wait\s+(\d+)\s+sec/i) || bodyText.match(/starting in\s+(\d+)/i) || bodyText.match(/(\d+)\s+seconds/i);
            if (waitMatch && parseInt(waitMatch[1]) > 0) {
                return { status: "countdown", seconds: parseInt(waitMatch[1]) };
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

                    // If form exists and has turnstile response, also submit
                    if (el.form) {
                        try { el.form.requestSubmit ? el.form.requestSubmit(el) : el.form.submit(); } catch(e) {}
                    }
                    return { status: "clicked", text: text };
                }
            }
            return { status: "not_found" };
        })();
        """)
        if result and result.get("status") == "clicked":
            return True
    except Exception:
        pass

    # SeleniumBase selector fallback
    step2_selectors = [
        '#btn_dl',
        'button:contains("Create Download Link")',
        'input[value*="Create Download Link"]',
        'button:contains("Direct Download")',
        'button:contains("Download Now")',
        'a:contains("Create Download Link")',
        'a:contains("Direct Download")',
        'input[name*="down"]',
        'button[name*="down"]'
    ]
    for sel in step2_selectors:
        try:
            if sb.is_element_visible(sel):
                sb.uc_click(sel)
                return True
        except Exception:
            pass

    return False


def close_ad_popups_and_tabs(sb, main_window_handle=None):
    """Closes any rogue popup or popunder tabs/windows and returns focus to the main window."""
    try:
        handles = sb.driver.window_handles
        if len(handles) > 1:
            target_main = main_window_handle if (main_window_handle and main_window_handle in handles) else handles[0]
            for handle in handles:
                if handle != target_main:
                    try:
                        sb.driver.switch_to.window(handle)
                        sb.driver.close()
                    except Exception:
                        pass
            sb.driver.switch_to.window(target_main)
    except Exception:
        pass


#--------------[Scraping Logic]--------------
def process_single_link(sb, link, worker_id, out_q, is_retry=False):
    filename = os.path.basename(link) if "/" in link else link
    max_retries = 3
    retry_count = 0

    def log(msg, style="white"):
        out_q.put(("LOG", msg, style))

    # Block native Chrome file downloads so workers do not stream 500MB files into the browser
    try:
        sb.driver.execute_cdp_cmd('Page.setDownloadBehavior', {'behavior': 'deny'})
    except Exception:
        pass
    try:
        sb.driver.execute_cdp_cmd('Browser.setDownloadBehavior', {'behavior': 'deny'})
    except Exception:
        pass

    main_handle = None
    try:
        main_handle = sb.driver.current_window_handle
    except Exception:
        pass

    while retry_count < max_retries:
        try:
            if retry_count == 0:
                log(f"[Worker {worker_id}] PROCESSING: {filename}", "cyan")

            # Clear any stale URL from previous link
            try:
                sb.execute_script(CLEAR_URL_JS)
            except Exception:
                pass

            # Install interceptor via CDP so it runs BEFORE page JS
            try:
                sb.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': INTERCEPTOR_SCRIPT
                })
            except Exception:
                pass

            # Navigate
            sb.open(link)
            try:
                main_handle = sb.driver.current_window_handle
            except Exception:
                pass
            close_ad_popups_and_tabs(sb, main_handle)

            try:
                sb.execute_script(CLEAR_URL_JS)
            except Exception:
                pass

            # Belt-and-suspenders: also inject directly into current page context
            try:
                sb.execute_script(INTERCEPTOR_SCRIPT)
            except Exception:
                pass

            # Cloudflare / server errors
            if sb.is_text_visible("Bad Gateway") or sb.is_text_visible("Error 502"):
                time.sleep(2)
                retry_count += 1
                continue

            # Auto-handle Turnstile if present on Step 1
            solve_turnstile_if_present(sb, worker_id, log)
            close_ad_popups_and_tabs(sb, main_handle)

            # File not found
            if sb.is_text_visible("File not found") or sb.is_text_visible("File Not Found") or sb.is_text_visible("File was deleted"):
                raise Exception("File not found on server")

            # Click "Free Download" button (Step 1)
            button_clicked = False
            for _ in range(30):
                if sb.is_text_visible("File not found") or sb.is_text_visible("File Not Found"):
                    raise Exception("File not found on server")

                # Try solving Turnstile if it appeared on Step 1
                solve_turnstile_if_present(sb, worker_id, log)
                close_ad_popups_and_tabs(sb, main_handle)

                if click_free_download_button(sb, worker_id, log):
                    button_clicked = True
                    close_ad_popups_and_tabs(sb, main_handle)
                    break

                time.sleep(1)

            if not button_clicked:
                already_on_step2 = False
                try:
                    already_on_step2 = sb.execute_script("""
                    (() => {
                        const t = document.body ? document.body.innerText : '';
                        return t.includes('Starting in') || t.includes('Starts automatically') || t.includes('Download') || location.href.includes('/download');
                    })();
                    """)
                except Exception:
                    pass
                if not already_on_step2:
                    raise Exception("Timeout waiting for 'Free Download' button")

            log(f"[Worker {worker_id}]   -> Free download clicked. Waiting for countdown / verification...", "dim")

            # Poll for the captured URL and handle Step 2
            download_url = None
            for tick in range(60):  # 60 seconds max
                close_ad_popups_and_tabs(sb, main_handle)
                try:
                    sb.execute_script(INTERCEPTOR_SCRIPT)
                except Exception:
                    pass

                # 1. Read from all persistence locations
                try:
                    captured = sb.execute_script(READ_URL_JS)
                    if captured and is_valid_download_url(captured, link):
                        download_url = unquote(captured)
                        break
                except Exception:
                    pass

                # 2. Check if browser navigated to a CDN URL
                try:
                    curr_url = sb.get_current_url()
                    if is_valid_download_url(curr_url, link):
                        download_url = unquote(curr_url)
                        break
                except Exception:
                    pass

                # 3. Auto-solve Turnstile captcha on Step 2
                solve_turnstile_if_present(sb, worker_id, log)
                close_ad_popups_and_tabs(sb, main_handle)

                # 4. Check and click Step 2 "Download" / "Create Download Link" button if enabled
                if click_step2_download_button(sb, worker_id, log):
                    log(f"[Worker {worker_id}]   Clicked final Download button...", "dim")
                    close_ad_popups_and_tabs(sb, main_handle)

                # 5. Fallback: scan for direct download <a> tags
                try:
                    direct = sb.execute_script("""
                    (() => {
                        const aa = Array.from(document.querySelectorAll('a[href]'));
                        for (const a of aa) {
                            const h = a.href || '';
                            if (h.includes('dlproxy') || h.includes('?sig=') || h.includes('&sig=')) return h;
                        }
                        return null;
                    })();
                    """)
                    if direct and is_valid_download_url(direct, link):
                        download_url = unquote(direct)
                        break
                except Exception:
                    pass

                # File-not-found mid-wait
                if sb.is_text_visible("File not found") or sb.is_text_visible("File Not Found"):
                    raise Exception("File not found on server")

                time.sleep(1)

            if download_url and is_valid_download_url(download_url, link):
                try:
                    sb.execute_script("window.stop();")
                except Exception:
                    pass
                cancel_active_downloads(sb)
                return True, download_url, ""

            retry_count += 1
            if retry_count < max_retries:
                log(f"[Worker {worker_id}] RETRYING: {filename} (Attempt {retry_count}/{max_retries - 1}) - URL not captured", "yellow")
                time.sleep(2)

        except Exception as e:
            error_msg = str(e)
            retry_count += 1
            if retry_count < max_retries:
                log(f"[Worker {worker_id}] RETRYING: {filename} (Attempt {retry_count}/{max_retries - 1}) - {error_msg[:50]}", "yellow")
                time.sleep(2)
            else:
                return False, f"# Failed to extract from {link}: {error_msg}", error_msg

    return False, f"# Failed to extract from {link}: Max retries reached", "Max retries reached"


#--------------[Worker Process Main]--------------
def worker_process_main(worker_id, in_q, out_q):
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # Each worker gets an isolated unique profile folder
    temp_dir = tempfile.mkdtemp(prefix=f"sb_dn_worker_{worker_id}_")
    # Flags to disable download bubbles, block popups, notifications and deny automatic downloads
    chrome_deny_flags = [
        "--download_restrictions=3",  # 3 completely blocks all downloads
        "--disable-features=DownloadBubble,DownloadBubbleV2",
        "--profile.default_content_setting_values.automatic_downloads=2",
        "--disable-notifications",
        "--deny-permission-prompts",
        "--disable-popup-blocking=false",
        "--mute-audio",
        "--disable-background-networking"
    ]

    sb_kwargs = {
        "uc": True,
        "test": False,
        "ad_block": True,
        "headless": False,
        "user_data_dir": temp_dir,
        "chromium_arg": chrome_deny_flags
    }
    if BROWSER_PATH:
        sb_kwargs["binary_location"] = BROWSER_PATH

    try:
        with SB(**sb_kwargs) as sb:
            try:
                null_path = "NUL" if sys.platform == "win32" else "/dev/null"
                sb.driver.execute_cdp_cmd("Network.enable", {})
                sb.driver.execute_cdp_cmd("Network.setBlockedURLs", {
                    "urls": BLOCKED_AD_URLS
                })
                sb.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                    "behavior": "deny",
                    "downloadPath": null_path
                })
                sb.driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
                    "behavior": "deny",
                    "downloadPath": null_path
                })
                sb.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": INTERCEPTOR_SCRIPT
                })
            except Exception:
                pass

            out_q.put(("WORKER_READY", worker_id))
            while True:
                item = in_q.get()
                if item is None:
                    break

                idx, link, is_retry = item
                try:
                    success, download_url, error_msg = process_single_link(sb, link, worker_id, out_q, is_retry=is_retry)
                    out_q.put(("COMPLETE", idx, link, success, download_url, error_msg, is_retry))
                except Exception as e:
                    out_q.put(("COMPLETE", idx, link, False, f"# Error: {e}", str(e), is_retry))
    except Exception as e:
        out_q.put(("LOG", f"Worker {worker_id} crashed: {e}", "bold red"))
        out_q.put(("WORKER_FAILED", worker_id))
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


#--------------[UI & State Manager]--------------
class ScraperUI:
    def __init__(self, total_links):
        self.console = Console()
        self.total = total_links
        self.successful = 0
        self.failed = 0
        self.start_time = time.time()

        self.progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("• [green]{task.completed}/{task.total} completed"),
            TimeElapsedColumn(),
            console=self.console
        )
        self.task_id = self.progress.add_task("Extracting", total=self.total)

    def log(self, message: str, style: str = "white"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.progress.console.print(f"[{timestamp}] {message}", style=style)

    def complete_link(self, link, success=True, error_msg="", is_retry=False):
        filename = os.path.basename(link) if "/" in link else link
        if success:
            self.successful += 1
            if is_retry:
                self.failed = max(0, self.failed - 1)
            ts = datetime.now().strftime("%H:%M:%S")
            self.progress.console.print(f"[{ts}] SUCCESS: {filename}", style="bold green")
        else:
            if not is_retry:
                self.failed += 1
            reason = f" - {error_msg}" if error_msg else ""
            ts = datetime.now().strftime("%H:%M:%S")
            self.progress.console.print(f"[{ts}] FAILED: {filename}{reason}", style="bold red")

        self.progress.update(self.task_id, completed=self.successful + self.failed)


#--------------[Main Function]--------------
def main():
    mp.freeze_support()
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] Input file '{INPUT_FILE}' not found.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        links = [line.strip() for line in f if line.strip()]

    if not links:
        print("[ERROR] No links found in input file.")
        return

    ui = ScraperUI(len(links))
    extracted = [None] * len(links)
    num_workers = max(1, min(NUM_WORKERS, len(links)))

    ui.progress.console.print("=" * 60, style="bold cyan")
    ui.progress.console.print("               DATANODES EXTRACTOR START", style="bold cyan")
    ui.progress.console.print("=" * 60, style="bold cyan")
    ui.log(f"Found {len(links)} links. Launching {num_workers} worker(s)...")

    in_q = mp.Queue()
    out_q = mp.Queue()

    procs = []
    for i in range(num_workers):
        p = mp.Process(
            target=worker_process_main,
            args=(i + 1, in_q, out_q)
        )
        p.start()
        procs.append(p)
        time.sleep(1.5)  # Stagger startup to prevent chromedriver patch lock collision

    with ui.progress:
        # Wait for workers to initialize
        active_workers = 0
        while active_workers < num_workers:
            msg = out_q.get()
            if msg[0] == "WORKER_READY":
                active_workers += 1
            elif msg[0] == "WORKER_FAILED":
                num_workers -= 1
            elif msg[0] == "LOG":
                ui.log(msg[1], msg[2])

        if active_workers == 0:
            ui.log("No workers could be started.", "bold red")
            return

        def save_current_output():
            try:
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(filter(None, extracted)))
            except Exception:
                pass

        # --- PASS 1 ---
        for idx, link in enumerate(links):
            in_q.put((idx, link, False))

        pending_items = len(links)
        while pending_items > 0:
            msg = out_q.get()
            if msg[0] == "LOG":
                ui.log(msg[1], msg[2])
            elif msg[0] == "COMPLETE":
                idx, link, success, download_url, error_msg, is_retry = msg[1:]
                extracted[idx] = download_url
                save_current_output()
                ui.complete_link(link, success=success, error_msg=error_msg, is_retry=is_retry)
                pending_items -= 1

        # --- PASS 2: Auto-Retry Failures ---
        failed_indices = [i for i, r in enumerate(extracted) if r and r.startswith("#")]
        if failed_indices:
            ui.log(f"Main pass done with {len(failed_indices)} errors. Retrying...", "bold yellow")
            for idx in failed_indices:
                in_q.put((idx, links[idx], True))

            pending_retries = len(failed_indices)
            while pending_retries > 0:
                msg = out_q.get()
                if msg[0] == "LOG":
                    ui.log(msg[1], msg[2])
                elif msg[0] == "COMPLETE":
                    idx, link, success, download_url, error_msg, is_retry = msg[1:]
                    if success:
                        extracted[idx] = download_url
                        save_current_output()
                    ui.complete_link(link, success=success, error_msg=error_msg, is_retry=is_retry)
                    pending_retries -= 1

        # Stop workers cleanly
        for _ in range(num_workers):
            in_q.put(None)

        for p in procs:
            p.join(timeout=10)

    # Final write output
    save_current_output()

    elapsed = time.time() - ui.start_time
    ui.console.print("\n" + "=" * 60, style="bold blue")
    ui.console.print("                  EXTRACTION SUMMARY", style="bold green")
    ui.console.print("=" * 60, style="bold blue")
    ui.console.print(f"Total Processed  : {len(links)}", style="white")
    ui.console.print(f"Successfully Done: {ui.successful}", style="bold green")
    ui.console.print(f"Failed Count     : {ui.failed}", style="bold red")
    success_pct = (ui.successful / len(links)) * 100 if len(links) > 0 else 0
    ui.console.print(f"Success Rate     : {success_pct:.1f}%", style="yellow")
    ui.console.print(f"Time Taken       : {elapsed:.1f} seconds", style="cyan")
    ui.console.print("=" * 60 + "\n", style="bold blue")


if __name__ == "__main__":
    main()