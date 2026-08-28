import re
import http.client
import urllib.parse
from typing import List, Dict, Any, Optional
import concurrent.futures


def is_filekeeper_url(url: str) -> bool:
    """Checks if a URL is a FileKeeper domain link."""
    if not url:
        return False
    return "filekeeper.net" in url.lower()


def extract_filekeeper_id(url: str) -> Optional[str]:
    """Extracts the alphanumeric FileKeeper file ID from URL."""
    if not url:
        return None
    match = re.search(r"filekeeper\.net/([a-zA-Z0-9]+)", url, re.IGNORECASE)
    return match.group(1) if match else None


def resolve_filekeeper_url(url: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Directly resolves a FileKeeper landing URL to its direct CDN streaming URL
    by simulating the free-tier form POST handshake and intercepting HTTP 302 Location.
    """
    url = url.strip()
    if not url:
        return {"original": url, "resolved": url, "success": False, "error": "Empty URL"}

    # If already a direct resolved CDN/dlproxy endpoint
    if "filekeeper.net" in url and ("dlproxy.uk" in url or ":8443" in url):
        filename = url.split("/")[-1].split("?")[0] or "filekeeper_file"
        return {"original": url, "resolved": url, "success": True, "filename": filename}

    file_id = extract_filekeeper_id(url)
    if not file_id:
        return {"original": url, "resolved": url, "success": False, "error": "Invalid FileKeeper URL format"}

    # Form payload for XFileSharing free-tier handshake
    post_body = urllib.parse.urlencode({
        "op": "download2",
        "id": file_id,
        "rand": "",
        "referer": "",
        "method_free": "Free download",
        "down_direct": "1"
    })

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://filekeeper.net/download",
        "Cookie": f"lang=english; file_code={file_id}",
        "Connection": "close"
    }

    try:
        conn = http.client.HTTPSConnection("filekeeper.net", timeout=timeout)
        conn.request("POST", "/download", body=post_body, headers=headers)
        res = conn.getresponse()
        location = res.getheader("Location")
        conn.close()

        if location and (location.startswith("http://") or location.startswith("https://")):
            # Extract filename from resolved CDN path
            filename = location.split("/")[-1].split("?")[0]
            if not filename or len(filename) > 120:
                filename = f"filekeeper_{file_id}"
            return {
                "original": url,
                "resolved": location,
                "success": True,
                "filename": filename
            }
        else:
            return {
                "original": url,
                "resolved": url,
                "success": False,
                "error": f"HTTP {res.status}: No direct 302 location header returned by FileKeeper."
            }
    except Exception as e:
        return {
            "original": url,
            "resolved": url,
            "success": False,
            "error": f"Resolution error: {str(e)}"
        }


def resolve_filekeeper_urls_bulk(urls: List[str], max_workers: int = 10, timeout: int = 15) -> List[Dict[str, Any]]:
    """Resolves multiple FileKeeper URLs concurrently using a thread pool."""
    clean_urls = [u.strip() for u in urls if u.strip()]
    if not clean_urls:
        return []

    results = [None] * len(clean_urls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(clean_urls))) as executor:
        future_to_idx = {executor.submit(resolve_filekeeper_url, url, timeout): idx for idx, url in enumerate(clean_urls)}
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = {
                    "original": clean_urls[idx],
                    "resolved": clean_urls[idx],
                    "success": False,
                    "error": str(e)
                }

    return results
