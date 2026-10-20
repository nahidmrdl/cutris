"""A loopback-only, persistent, sequential image processing queue."""
from __future__ import annotations

import io
import json
import os
import re
import secrets
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from engine import ROOT, MODELS, Remover, apply_strokes, load_image, save_png
from app_paths import APP_ID, APP_NAME, VERSION, DATA_DIR, public_error
from model_manager import model_status

DATA = DATA_DIR / "jobs"
DATA.mkdir(parents=True, exist_ok=True)
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cutout")
REMOVER = Remover()
JOBS: dict[str, dict] = {}
DESKTOP_MODE = False
app = FastAPI(docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


def persist(job):
    path = DATA / job["id"] / "manifest.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


for path in DATA.glob("*/manifest.json"):
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
        if not re.fullmatch(r"[a-f0-9]{32}", job["id"]):
            continue
        if job["status"] in {"running", "queued", "pausing"}:
            job["status"] = "paused"
            job["stage"] = "Interrupted by a restart. Resume to continue."
            for item in job["items"]:
                if item["status"] == "running":
                    item["status"] = "waiting"
            persist(job)
        JOBS[job["id"]] = job
    except (ValueError, KeyError, OSError):
        pass


@app.middleware("http")
async def local_safety(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("X-Cutout-Token") != TOKEN:
            return JSONResponse({"detail": "Session expired. Refresh this page and try again."}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Only this local app may make changes."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    # pywebview constructs its local native API with Function(). Browser mode
    # keeps eval disabled; the desktop renderer only loads bundled local code.
    script_policy = "'self' 'unsafe-eval'" if DESKTOP_MODE else "'self'"
    response.headers["Content-Security-Policy"] = f"default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src {script_policy}; connect-src 'self'; frame-ancestors 'none'"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
        if request.method == "GET" and "/items/" in request.url.path and request.query_params.get("download") != "true":
            response.headers["Cache-Control"] = "private, max-age=3600"
    return response


def get_job(job_id):
    if job_id not in JOBS:
        raise HTTPException(404, "Batch not found.")
    return JOBS[job_id]


def get_item(job_id, item_id):
    job = get_job(job_id)
    item = next((i for i in job["items"] if i["id"] == item_id), None)
    if not item:
        raise HTTPException(404, "Image not found.")
    return job, item, DATA / job_id / item_id


def thumbnail(image, path):
    preview = image.copy()
    preview.thumbnail((128, 128), Image.Resampling.LANCZOS)
    save_png(preview, path)


def run_job(job_id):
    with LOCK:
        job = JOBS[job_id]
        if job["status"] != "queued":
            return
        job["status"] = "running"
        persist(job)
    for item in job["items"]:
        with LOCK:
            if job["status"] == "pausing":
                job["status"] = "paused"
                job["stage"] = "Paused. Your completed images are saved."
                persist(job)
                return
            if item["status"] != "waiting":
                continue
            item["status"] = "running"
            job["current"] = item["id"]
            persist(job)
        directory = DATA / job_id / item["id"]
        try:
            def progress(stage):
                with LOCK:
                    job["stage"] = stage
            with Image.open(directory / "original.png") as image:
                result, notes = REMOVER.process(image.convert("RGBA"), job["quality"], job["mode"], progress)
            save_png(result, directory / "automatic.png")
            save_png(result, directory / "result.png")
            thumbnail(result, directory / "thumbnail.png")
            with LOCK:
                item.update(status="done", notes=notes, error=None)
        except Exception as exc:
            with LOCK:
                item.update(status="error", error=public_error(exc, "The image could not be processed. Check the model installation, available memory, and source image, then retry."))
        with LOCK:
            persist(job)
    with LOCK:
        job["status"] = "complete"
        job["current"] = None
        job["stage"] = "Batch finished. Review the edges before exporting."
        persist(job)


@app.get("/api/config")
def config():
    return {"appId": APP_ID, "name": APP_NAME, "version": VERSION, "token": TOKEN, "models": model_status(), "maxFiles": 50}


@app.get("/api/about")
def about():
    notices = ROOT / "THIRD_PARTY_NOTICES.md"
    return {"name": APP_NAME, "version": VERSION,
            "notices": notices.read_text(encoding="utf-8") if notices.is_file() else "See the licenses folder included with this application."}


@app.get("/api/jobs")
def list_jobs():
    with LOCK:
        return [{"id": j["id"], "created": j["created"], "count": len(j["items"]), "status": j["status"]} for j in sorted(JOBS.values(), key=lambda j: j["created"], reverse=True)]


@app.post("/api/jobs")
def create_job(files: list[UploadFile] = File(...), quality: str = Form("detail"), mode: str = Form("ai")):
    if not 1 <= len(files) <= 50:
        raise HTTPException(400, "Choose between 1 and 50 images per batch.")
    if quality not in MODELS or mode not in {"white", "ai"}:
        raise HTTPException(400, "Unknown processing setting.")
    # One active batch avoids surprising concurrent memory and disk consumption.
    with LOCK:
        if any(j["status"] in {"running", "queued", "pausing"} for j in JOBS.values()):
            raise HTTPException(409, "A batch is already processing. Pause it or wait until it finishes.")
        job_id = uuid.uuid4().hex
        directory = DATA / job_id
        directory.mkdir()
        job = {"id": job_id, "created": time.time(), "quality": quality, "mode": mode, "status": "queued", "stage": "Waiting for the AI", "current": None, "items": []}
        for index, file in enumerate(files):
            item_id = uuid.uuid4().hex
            name = (file.filename or "image").replace("\\", "/").split("/")[-1][:180]
            stem = re.sub(r"[^\w .-]", "_", Path(name).stem).strip(" .")[:100] or "image"
            item = {"id": item_id, "name": name, "output": f"{index + 1:03d}_{stem}.png", "status": "waiting", "notes": [], "revision": 0, "strokes": []}
            target = directory / item_id
            target.mkdir()
            try:
                content = file.file.read(30 * 1024 * 1024 + 1)
                if len(content) > 30 * 1024 * 1024:
                    raise ValueError("Image exceeds 30 MB. Export a smaller source file.")
                image = load_image(content)
                item["width"], item["height"] = image.size
                save_png(image, target / "original.png")
            except Exception as exc:
                item.update(status="error", error=public_error(exc, "This file could not be opened. Choose a supported, undamaged image."))
            finally:
                file.file.close()
            job["items"].append(item)
        JOBS[job_id] = job
        persist(job)
        POOL.submit(run_job, job_id)
    return job


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with LOCK:
        # Snapshot before the worker changes nested data during serialization.
        return json.loads(json.dumps(get_job(job_id)))


@app.post("/api/jobs/{job_id}/{action}")
def control(job_id: str, action: str):
    with LOCK:
        job = get_job(job_id)
        if action == "pause" and job["status"] in {"queued", "running"}:
            job["status"] = "paused" if job["status"] == "queued" else "pausing"
        elif action in {"resume", "retry"} and job["status"] in {"paused", "complete"}:
            if any(j["status"] in {"queued", "running", "pausing"} for j in JOBS.values()):
                raise HTTPException(409, "Another batch is processing.")
            if action == "retry":
                for item in job["items"]:
                    if item["status"] == "error" and (DATA / job_id / item["id"] / "original.png").is_file():
                        item["status"] = "waiting"
            job["status"] = "queued"
            POOL.submit(run_job, job_id)
        else:
            raise HTTPException(409, "This action is not available for the current batch state.")
        persist(job)
    return {"ok": True}


class Stroke(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    mode: str = Field(pattern="^(erase|restore|wand)$")
    size: float = Field(default=1, ge=1, le=500)
    points: list[tuple[float, float]] = Field(default_factory=list, max_length=20000)
    spans: list[tuple[int, int, int]] = Field(default_factory=list, max_length=100000)


class Edits(BaseModel):
    revision: int = Field(ge=0)
    strokes: list[Stroke] = Field(max_length=500)


@app.put("/api/jobs/{job_id}/items/{item_id}/edits")
def edit(job_id: str, item_id: str, edits: Edits):
    if sum(len(s.points) for s in edits.strokes) > 100000:
        raise HTTPException(400, "Too many brush points in this edit.")
    if sum(len(s.spans) for s in edits.strokes) > 200000:
        raise HTTPException(400, "Too many selection segments. Simplify this touch-up before saving.")
    with LOCK:
        job, item, directory = get_item(job_id, item_id)
        if item["status"] != "done":
            raise HTTPException(409, "Wait for this image to finish.")
        if edits.revision != item["revision"]:
            raise HTTPException(409, "This image changed in another tab. Reload it before editing.")
        for stroke in edits.strokes:
            if stroke.mode == "wand":
                if not stroke.spans or stroke.points:
                    raise HTTPException(400, "A magic-wand edit needs selected pixel spans, not brush points.")
                for y, x0, x1 in stroke.spans:
                    if not (0 <= y < item["height"] and 0 <= x0 < x1 <= item["width"]):
                        raise HTTPException(400, "Selection must stay inside the image.")
            elif not stroke.points or stroke.spans:
                raise HTTPException(400, "A brush edit needs at least one point and no selection spans.")
            if any(not (-500 <= x <= item["width"] + 500 and -500 <= y <= item["height"] + 500) for x, y in stroke.points):
                raise HTTPException(400, "Brush coordinates must be on the image.")
        with Image.open(directory / "original.png") as original, Image.open(directory / "automatic.png") as automatic:
            strokes = [s.model_dump() for s in edits.strokes]
            result = apply_strokes(original.convert("RGBA"), automatic.convert("RGBA"), strokes)
        save_png(result, directory / "result.png")
        thumbnail(result, directory / "thumbnail.png")
        item["strokes"] = strokes
        item["revision"] += 1
        persist(job)
        return {"revision": item["revision"]}


@app.get("/api/jobs/{job_id}/items/{item_id}/{kind}")
def image_file(job_id: str, item_id: str, kind: str, download: bool = False):
    with LOCK:
        _, item, directory = get_item(job_id, item_id)
        if kind not in {"original", "automatic", "result", "thumbnail", "original-thumbnail"}:
            raise HTTPException(404, "Unknown image type.")
        path = directory / f"{kind}.png"
        if kind in {"thumbnail", "original-thumbnail"} and not path.is_file():
            source = directory / ("result.png" if kind == "thumbnail" else "original.png")
            if source.is_file():
                with Image.open(source) as original:
                    thumbnail(original.convert("RGBA"), path)
        if not path.is_file():
            raise HTTPException(404, "Image is not ready.")
        return FileResponse(path, media_type="image/png", filename=item["output"] if download else None)


@app.get("/api/jobs/{job_id}/download.zip")
def download_zip(job_id: str):
    with LOCK:
        job = get_job(job_id)
        ready = [i for i in job["items"] if i["status"] == "done"]
        if not ready:
            raise HTTPException(409, "No completed images yet.")
        # A spool avoids keeping a 50-image archive in RAM.
        import tempfile
        archive = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
            for item in ready:
                bundle.write(DATA / job_id / item["id"] / "result.png", item["output"])
            bundle.writestr("batch-manifest.json", json.dumps(job, ensure_ascii=False, indent=2))
        archive.seek(0)
    def stream():
        try:
            while chunk := archive.read(1024 * 1024):
                yield chunk
        finally:
            archive.close()
    return StreamingResponse(stream(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="cutouts-' + job_id[:8] + '.zip"'})


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
