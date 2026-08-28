import os
import sys
import time
import json
import uuid
import shutil
import tempfile
import asyncio
import subprocess
import threading
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import unquote

try:
    from seleniumbase import sb_cdp
except ImportError:
    sb_cdp = None


class WorkerSlot:
    def __init__(self, worker_id: int, port: int, headless: bool = False):
        self.worker_id = worker_id
        self.port = port
        self.headless = headless
        self.sb_instance = None
        self.proc: Optional[subprocess.Popen] = None
        self.endpoint_url: Optional[str] = None
        self.temp_dir: Optional[str] = None
        self.is_busy = False
        self.is_ready = False
        self.current_link: Optional[str] = None
        self.current_stage = "idle"
        self.current_step = "Initialized"
        self.reader_thread: Optional[threading.Thread] = None

    def start(self, on_event_cb: Callable[[Dict[str, Any]], None]):
        """Starts the SeleniumBase CDP browser and connects the Node Puppeteer worker process."""
        self.temp_dir = tempfile.mkdtemp(prefix=f"sb_cdp_worker_{self.worker_id}_")
        is_linux = sys.platform != "win32"

        chrome_flags = [
            "--download_restrictions=3",
            "--disable-features=DownloadBubble,DownloadBubbleV2",
            "--profile.default_content_setting_values.automatic_downloads=2",
            "--disable-notifications",
            "--deny-permission-prompts",
            "--mute-audio",
            "--disable-background-networking",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1366,768",
            "--enable-webgl"
        ]

        sb_kwargs = {
            "headless": self.headless,
            "user_data_dir": self.temp_dir,
            "sandbox": False,
            "browser_args": chrome_flags
        }

        on_event_cb({
            "type": "log",
            "worker": self.worker_id,
            "text": f"Worker {self.worker_id} launching stealth Chrome (Headless={self.headless})...",
            "level": "info"
        })

        self.sb_instance = sb_cdp.Chrome(**sb_kwargs)
        self.endpoint_url = self.sb_instance.get_endpoint_url()
        try:
            self.port = self.sb_instance.get_port()
        except Exception:
            pass

        on_event_cb({
            "type": "log",
            "worker": self.worker_id,
            "text": f"Worker {self.worker_id} browser ready at {self.endpoint_url} (Port {self.port}). Starting Puppeteer worker...",
            "level": "info"
        })

        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "puppeteer_worker.js")
        node_cmd = [
            "node",
            script_path,
            "--cdp", self.endpoint_url,
            "--worker", str(self.worker_id),
            "--ipc"
        ]

        self.proc = subprocess.Popen(
            node_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1
        )

        def stream_reader():
            while self.proc and self.proc.poll() is None:
                line = self.proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "ready":
                        self.is_ready = True
                    elif data.get("type") == "status":
                        self.current_stage = data.get("stage", "idle")
                        self.current_step = data.get("step", "")
                    on_event_cb(data)
                except Exception:
                    # Non-JSON fallback output
                    on_event_cb({
                        "type": "log",
                        "worker": self.worker_id,
                        "text": line,
                        "level": "info"
                    })

        self.reader_thread = threading.Thread(target=stream_reader, daemon=True)
        self.reader_thread.start()

    def send_task(self, link: str, task_id: int):
        if not self.proc or self.proc.poll() is not None:
            return False
        self.is_busy = True
        self.current_link = link
        payload = json.dumps({"cmd": "scrape", "link": link, "taskId": task_id}) + "\n"
        self.proc.stdin.write(payload)
        self.proc.stdin.flush()
        return True

    def stop(self):
        """Cleanly stops Node process, terminates sb_cdp browser, and deletes temp folder."""
        self.is_busy = False
        self.is_ready = False
        if self.proc:
            try:
                if self.proc.stdin:
                    self.proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                    self.proc.stdin.flush()
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None

        if self.sb_instance:
            try:
                self.sb_instance.quit()
            except Exception:
                pass
            self.sb_instance = None

        if self.temp_dir:
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception:
                pass
            self.temp_dir = None


class ExtractionManager:
    """Manages the full lifecycle of a batch extraction job with FileKeeper fast-resolver and up to 5 concurrent browser workers for DataNodes."""

    def __init__(self):
        self.workers: List[WorkerSlot] = []
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        self.current_job_id: Optional[str] = None
        self.total_links = 0
        self.completed_links = 0
        self.successful_links = 0
        self.failed_links = 0
        self.start_time: float = 0.0
        self.items: List[Dict[str, Any]] = []
        self.event_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.Lock()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def register_callback(self, cb: Callable[[Dict[str, Any]], None]):
        self.event_callbacks.append(cb)

    def unregister_callback(self, cb: Callable[[Dict[str, Any]], None]):
        if cb in self.event_callbacks:
            self.event_callbacks.remove(cb)

    def _broadcast(self, event: Dict[str, Any]):
        for cb in list(self.event_callbacks):
            try:
                cb(event)
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            elapsed = time.time() - self.start_time if self.is_running and self.start_time > 0 else 0
            speed = (self.completed_links / (elapsed / 60)) if elapsed > 5 else 0
            worker_states = []
            for w in self.workers:
                worker_states.append({
                    "id": w.worker_id,
                    "port": w.port,
                    "isBusy": w.is_busy,
                    "isReady": w.is_ready,
                    "currentLink": w.current_link,
                    "stage": w.current_stage,
                    "step": w.current_step
                })

            return {
                "jobId": self.current_job_id,
                "isRunning": self.is_running,
                "total": self.total_links,
                "completed": self.completed_links,
                "successful": self.successful_links,
                "failed": self.failed_links,
                "successRate": round((self.successful_links / self.completed_links * 100), 1) if self.completed_links > 0 else 0,
                "elapsed": round(elapsed, 1),
                "speed": round(speed, 1),
                "workers": worker_states,
                "items": list(self.items)
            }

    def start_job(self, links: List[str], num_workers: int = 3, headless: bool = False) -> str:
        with self._lock:
            if self.is_running:
                raise RuntimeError("An extraction job is already in progress.")

            # Clamp workers strictly between 1 and 5 (max 5)
            num_workers = max(1, min(int(num_workers), 5, len(links) if links else 1))
            self.is_running = True
            self.should_stop = False
            self.current_job_id = str(uuid.uuid4())[:8]
            self.completed_links = 0
            self.successful_links = 0
            self.failed_links = 0
            self.start_time = time.time()
            self.items = [
                {
                    "id": idx,
                    "originalUrl": link.strip(),
                    "service": "filekeeper" if filekeeper.is_filekeeper_url(link.strip()) else "datanodes",
                    "filename": link.strip().split("/")[-1] if "/" in link.strip() else link.strip(),
                    "status": "pending",
                    "extractedUrl": None,
                    "error": None,
                    "worker": None,
                    "timeTaken": None
                }
                for idx, link in enumerate(links)
                if link.strip()
            ]
            self.total_links = len(self.items)

        # Start execution in background thread
        threading.Thread(target=self._run_job, args=(num_workers, headless), daemon=True).start()
        return self.current_job_id

    def _run_job(self, num_workers: int, headless: bool):
        self._broadcast({"type": "job_started", "data": self.get_status()})
        
        fk_count = sum(1 for itm in self.items if itm["service"] == "filekeeper")
        dn_count = self.total_links - fk_count

        self._broadcast({
            "type": "log",
            "worker": 0,
            "text": f"Starting extraction job ({self.total_links} total links: {dn_count} DataNodes, {fk_count} FileKeeper)...",
            "level": "info"
        })

        # Phase 1: Rapid HTTP Resolution for FileKeeper Links (zero browser overhead)
        fk_indices = [i for i, itm in enumerate(self.items) if itm["service"] == "filekeeper"]
        if fk_indices:
            self._broadcast({
                "type": "log",
                "worker": 0,
                "text": f"Resolving {len(fk_indices)} FileKeeper direct links via high-speed HTTP engine...",
                "level": "info"
            })
            for f_idx in fk_indices:
                if self.should_stop:
                    break
                item = self.items[f_idx]
                item["status"] = "processing"
                item["startTime"] = time.time()
                self._broadcast({"type": "item_updated", "item": item})

                res = filekeeper.resolve_filekeeper_url(item["originalUrl"])
                success = res.get("success", False)
                item["status"] = "success" if success else "failed"
                item["extractedUrl"] = res.get("resolved") if success else None
                item["error"] = res.get("error") if not success else None
                if res.get("filename"):
                    item["filename"] = res["filename"]
                item["timeTaken"] = round(time.time() - item["startTime"], 2)

                with self._lock:
                    self.completed_links += 1
                    if success:
                        self.successful_links += 1
                        try:
                            with open("extracted_links.txt", "a", encoding="utf-8") as f_out:
                                f_out.write(f"{item['extractedUrl']}\n")
                        except Exception:
                            pass
                    else:
                        self.failed_links += 1

                self._broadcast({"type": "item_updated", "item": item})
                self._broadcast({"type": "status_update", "data": self.get_status()})
                self._broadcast({
                    "type": "log",
                    "worker": 0,
                    "text": f"[FileKeeper] {'Resolved: ' + item['extractedUrl'] if success else 'Failed: ' + str(item['error'])}",
                    "level": "success" if success else "error"
                })

        # Phase 2: Browser workers for DataNodes links
        dn_indices = [i for i, itm in enumerate(self.items) if itm["service"] == "datanodes" and itm["status"] == "pending"]
        
        if dn_indices and not self.should_stop:
            actual_workers = min(num_workers, len(dn_indices))
            self._broadcast({
                "type": "log",
                "worker": 0,
                "text": f"Launching {actual_workers} stealth browser worker(s) for DataNodes links...",
                "level": "info"
            })

            base_port = 9221
            self.workers = []
            for i in range(actual_workers):
                if self.should_stop:
                    break
                slot = WorkerSlot(worker_id=i + 1, port=base_port + i, headless=headless)
                self.workers.append(slot)
                try:
                    slot.start(on_event_cb=self._handle_worker_event)
                    time.sleep(1.0)  # Stagger startup to prevent port collisions
                except Exception as e:
                    self._broadcast({
                        "type": "log",
                        "worker": i + 1,
                        "text": f"Failed to initialize Worker {i + 1}: {e}",
                        "level": "error"
                    })

            # Wait for workers to become ready (up to 30s)
            ready_timeout = 30
            start_wait = time.time()
            while time.time() - start_wait < ready_timeout and not self.should_stop:
                if all(w.is_ready for w in self.workers if w.proc is not None):
                    break
                time.sleep(0.5)

            self._broadcast({"type": "status_update", "data": self.get_status()})

            queue = list(dn_indices)

            while (queue or any(w.is_busy for w in self.workers)) and not self.should_stop:
                # Assign idle workers to queued items
                for worker in self.workers:
                    if not worker.is_busy and worker.is_ready and queue:
                        item_idx = queue.pop(0)
                        item = self.items[item_idx]
                        item["status"] = "processing"
                        item["worker"] = worker.worker_id
                        item["startTime"] = time.time()

                        self._broadcast({
                            "type": "item_updated",
                            "item": item
                        })
                        worker.send_task(item["originalUrl"], item_idx)

                time.sleep(0.2)

            # Auto-retry pass for failed DataNodes items
            failed_dn = [i for i, itm in enumerate(self.items) if itm["service"] == "datanodes" and itm["status"] == "failed" and itm.get("retried") is not True]
            if failed_dn and not self.should_stop:
                self._broadcast({
                    "type": "log",
                    "worker": 0,
                    "text": f"DataNodes extraction completed with {len(failed_dn)} failed link(s). Auto-retrying...",
                    "level": "warn"
                })
                for f_idx in failed_dn:
                    self.items[f_idx]["retried"] = True
                    self.items[f_idx]["status"] = "retrying"
                    queue.append(f_idx)

                while (queue or any(w.is_busy for w in self.workers)) and not self.should_stop:
                    for worker in self.workers:
                        if not worker.is_busy and worker.is_ready and queue:
                            item_idx = queue.pop(0)
                            item = self.items[item_idx]
                            item["status"] = "processing"
                            item["worker"] = worker.worker_id
                            item["startTime"] = time.time()
                            self._broadcast({"type": "item_updated", "item": item})
                            worker.send_task(item["originalUrl"], item_idx)
                    time.sleep(0.2)

        # Cleanup workers
        self._shutdown_workers()

        with self._lock:
            self.is_running = False

        self._broadcast({"type": "job_completed", "data": self.get_status()})
        self._broadcast({
            "type": "log",
            "worker": 0,
            "text": f"Extraction job finished! Total Success: {self.successful_links}/{self.total_links}",
            "level": "success"
        })

    def _handle_worker_event(self, event: Dict[str, Any]):
        evt_type = event.get("type")
        worker_id = event.get("worker", 0)

        if evt_type == "result":
            task_id = event.get("taskId")
            success = event.get("success", False)
            url = event.get("url")
            err = event.get("error")

            # Match item by taskId or link
            item = None
            if task_id is not None and 0 <= task_id < len(self.items):
                item = self.items[task_id]
            else:
                for itm in self.items:
                    if itm["originalUrl"] == event.get("link") and itm["status"] in ("processing", "retrying"):
                        item = itm
                        break

            if item:
                item["status"] = "success" if success else "failed"
                item["extractedUrl"] = url if success else None
                item["error"] = err if not success else None
                if item.get("startTime"):
                    item["timeTaken"] = round(time.time() - item["startTime"], 1)

                with self._lock:
                    self.completed_links += 1
                    if success:
                        self.successful_links += 1
                        try:
                            with open("extracted_links.txt", "a", encoding="utf-8") as f_out:
                                f_out.write(f"{item['extractedUrl']}\n")
                        except Exception:
                            pass
                    else:
                        self.failed_links += 1

                self._broadcast({"type": "item_updated", "item": item})
                self._broadcast({"type": "status_update", "data": self.get_status()})

            # Free worker
            for w in self.workers:
                if w.worker_id == worker_id:
                    w.is_busy = False
                    w.current_link = None
                    w.current_stage = "idle"
                    w.current_step = "Ready"
                    break

        elif evt_type == "status":
            for w in self.workers:
                if w.worker_id == worker_id:
                    w.current_stage = event.get("stage", "idle")
                    w.current_step = event.get("step", "")
                    break
            self._broadcast({"type": "status_update", "data": self.get_status()})

        # Forward all events (logs, statuses, etc.)
        self._broadcast(event)

    def _shutdown_workers(self):
        for w in self.workers:
            try:
                w.stop()
            except Exception:
                pass
        self.workers = []

    def stop_job(self):
        with self._lock:
            if not self.is_running:
                return
            self.should_stop = True

        self._broadcast({
            "type": "log",
            "worker": 0,
            "text": "Stopping extraction job and shutting down browser sessions...",
            "level": "warn"
        })
        self._shutdown_workers()
        with self._lock:
            self.is_running = False
        self._broadcast({"type": "job_stopped", "data": self.get_status()})


# Singleton manager instance
manager = ExtractionManager()
