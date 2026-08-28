import os
import sys
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from manager import manager
import filekeeper

app = FastAPI(title="DataNodes & FileKeeper Link Extractor Pro", version="2.5.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
connected_websockets: List[WebSocket] = []
main_event_loop: Optional[asyncio.AbstractEventLoop] = None


class ExtractRequest(BaseModel):
    links: List[str] = Field(..., description="List of DataNodes or FileKeeper URLs to extract")
    workers: int = Field(default=3, ge=1, le=5, description="Number of parallel browser workers (1 to 5)")
    headless: bool = Field(default=False, description="Run browsers in headless mode")


class ResolveLinksRequest(BaseModel):
    urls: List[str] = Field(..., description="List of FileKeeper URLs to resolve directly")


def websocket_event_forwarder(event: dict):
    """Callback registered with manager to forward events to all connected WebSockets."""
    if not connected_websockets or not main_event_loop:
        return

    message_str = json.dumps(event)

    async def broadcast():
        disconnected = []
        for ws in connected_websockets:
            try:
                await ws.send_text(message_str)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if ws in connected_websockets:
                connected_websockets.remove(ws)

    asyncio.run_coroutine_threadsafe(broadcast(), main_event_loop)


# Register event callback with manager
manager.register_callback(websocket_event_forwarder)


@app.on_event("startup")
async def startup_event():
    global main_event_loop
    main_event_loop = asyncio.get_running_loop()


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "DataNodes Link Extractor",
        "version": "2.0.0",
        "headlessDefault": False,
        "maxWorkers": 5
    }


@app.get("/api/status")
async def get_status():
    return manager.get_status()


@app.post("/api/extract")
async def start_extraction(req: ExtractRequest):
    # Filter empty links
    clean_links = [link.strip() for link in req.links if link.strip()]
    if not clean_links:
        raise HTTPException(status_code=400, detail="No valid URLs provided.")

    # Enforce max 5 workers
    num_workers = max(1, min(req.workers, 5))

    try:
        job_id = manager.start_job(links=clean_links, num_workers=num_workers, headless=req.headless)
        return {
            "success": True,
            "jobId": job_id,
            "totalLinks": len(clean_links),
            "workers": num_workers,
            "headless": req.headless
        }
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resolve-links")
async def resolve_filekeeper_links(req: ResolveLinksRequest):
    """
    Bulk FileKeeper link resolution endpoint matching technical documentation specification.
    Resolves FileKeeper landing URLs in parallel using the direct HTTP handshake.
    """
    if not req.urls or not isinstance(req.urls, list):
        raise HTTPException(status_code=400, detail="urls array is required")

    clean_urls = [u.strip() for u in req.urls if u and u.strip()]
    if not clean_urls:
        return {"results": []}

    results = await asyncio.to_thread(filekeeper.resolve_filekeeper_urls_bulk, clean_urls)
    return {"results": results}


@app.post("/api/stop")
async def stop_extraction():
    manager.stop_job()
    return {"success": True, "message": "Extraction stopped."}


@app.get("/api/export/{fmt}")
async def export_results(fmt: str):
    status = manager.get_status()
    items = status.get("items", [])

    if fmt == "txt":
        lines = []
        for item in items:
            if item.get("status") == "success" and item.get("extractedUrl"):
                lines.append(item["extractedUrl"])
            elif item.get("status") == "failed":
                lines.append(f"# Failed: {item['originalUrl']} ({item.get('error')})")
        content = "\n".join(lines)
        return PlainTextResponse(content, headers={"Content-Disposition": 'attachment; filename="extracted_links.txt"'})

    elif fmt == "idm":
        # IDM export format: URL<CRLF>
        lines = [item["extractedUrl"] for item in items if item.get("status") == "success" and item.get("extractedUrl")]
        content = "\r\n".join(lines)
        return PlainTextResponse(content, headers={"Content-Disposition": 'attachment; filename="idm_links.txt"'})

    elif fmt == "json":
        return JSONResponse(
            content=items,
            headers={"Content-Disposition": 'attachment; filename="extracted_data.json"'}
        )

    raise HTTPException(status_code=400, detail="Unsupported export format. Use 'txt', 'idm', or 'json'.")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)

    # Immediately push current status
    await websocket.send_text(json.dumps({
        "type": "init",
        "data": manager.get_status()
    }))

    try:
        while True:
            # Keep-alive ping/pong or client commands
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "get_status":
                    await websocket.send_text(json.dumps({
                        "type": "status_update",
                        "data": manager.get_status()
                    }))
                elif msg.get("action") == "stop":
                    manager.stop_job()
            except Exception:
                pass
    except WebSocketDisconnect:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)
    except Exception:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)


# Mount static directory for frontend Web UI
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
os.makedirs(static_dir, exist_ok=True)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"DataNodes Web Server starting on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
