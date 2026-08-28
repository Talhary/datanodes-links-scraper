import os
import sys
import subprocess
from seleniumbase import sb_cdp

def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 60)
    print("      SELENIUMBASE + PUPPETEER CDP RUNNER")
    print("=" * 60)
    
    print("[1/3] Launching stealth Chrome browser with SeleniumBase...")
    sb = sb_cdp.Chrome()
    try:
        endpoint_url = sb.get_endpoint_url()
        ws_url = sb.get_websocket_url()
        print(f"[2/3] Retrieved CDP Endpoint URL: {endpoint_url}")
        print(f"      WebSocket URL: {ws_url}")
        
        print("[3/3] Handing over control to Puppeteer scraper...\n")
        node_cmd = [
            "node",
            "puppeteer_scraper.js",
            "--cdp", endpoint_url,
            "--input", "links.txt",
            "--output", "output.txt"
        ]
        
        # Stream Node.js output in real-time
        proc = subprocess.Popen(
            node_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8"
        )
        
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(line, end="", flush=True)
                
        proc.wait()
        
    finally:
        print("\nClosing SeleniumBase browser session...")
        try:
            sb.quit()
        except Exception:
            pass

if __name__ == "__main__":
    main()
