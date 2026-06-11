"""GS Studio — backend FastAPI."""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from . import deps as deps_mod
from . import pipeline as pl
from . import projects as proj
from . import blender_integration as bi


APP_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = APP_ROOT.parent
TEMPLATES = Jinja2Templates(directory=str(APP_ROOT / "templates"))
UPLOADS = APP_ROOT / "data" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
BLENDER_EXPORT_SCRIPT = REPO_ROOT / "blender" / "export_template.py"
ADDON_DOWNLOADS = Path.home() / "Downloads" / "blender-gs-addons"

app = FastAPI(title="GS Studio")
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "static")), name="static")

# Estado em memória — uma única run de cada vez
_run_task: asyncio.Task | None = None
_run_events: list[dict] = []
_run_clients: set[WebSocket] = set()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return TEMPLATES.TemplateResponse(request, "index.html")


# ───────────────────────────────────────────────────── Dependências


@app.get("/api/deps")
async def get_deps():
    return {"deps": deps_mod.check_all()}


@app.websocket("/ws/install/{dep_name}")
async def ws_install(ws: WebSocket, dep_name: str):
    await ws.accept()
    try:
        proc = await deps_mod.install_one(dep_name)
    except ValueError as e:
        await ws.send_json({"type": "error", "message": str(e)})
        await ws.close()
        return
    assert proc.stdout
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        await ws.send_json({"type": "log", "line": line.decode(errors="replace").rstrip()})
    rc = await proc.wait()
    await ws.send_json({"type": "end", "rc": rc})
    await ws.close()


# ───────────────────────────────────────────────────── Upload


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "Sem ficheiro")
    safe = "".join(c if c.isalnum() or c in ".-_ " else "_" for c in file.filename)
    dst = UPLOADS / safe
    with dst.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    return {"path": str(dst), "size": dst.stat().st_size, "name": safe}


@app.post("/api/upload-path")
async def use_local_path(path: str = Form(...)):
    """Aceita um caminho já no disco — evita copiar vídeos enormes."""
    p = Path(path).expanduser()
    if not p.exists() or not p.is_file():
        raise HTTPException(400, f"Ficheiro não encontrado: {p}")
    return {"path": str(p), "size": p.stat().st_size, "name": p.name}


# ───────────────────────────────────────────────────── Pipeline


def _build_config(payload: dict) -> pl.RunConfig:
    return pl.RunConfig(
        project_name=payload["project_name"],
        video_path=payload["video_path"],
        output_root=payload["output_root"],
        frames=pl.FramesCfg(**payload.get("frames", {})),
        colmap=pl.ColmapCfg(**payload.get("colmap", {})),
        brush=pl.BrushCfg(**payload.get("brush", {})),
        output=pl.OutputCfg(**payload.get("output", {})),
    )


async def _broadcast(ev: dict):
    _run_events.append(ev)
    dead = []
    for ws in _run_clients:
        try:
            await ws.send_json(ev)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _run_clients.discard(ws)


async def _run_and_broadcast(cfg: pl.RunConfig):
    pscript = pl.perspective_script_path(APP_ROOT)
    async for ev in pl.run_pipeline(cfg, pscript):
        await _broadcast(ev)
        if ev.get("type") == "end":
            # actualizar histórico
            summary = proj.project_summary(cfg.scenedir)
            summary.update({
                "video_path": cfg.video_path,
                "config": cfg.to_dict(),
                "result": ev,
            })
            proj.upsert_project(APP_ROOT, summary)
            if cfg.output.auto_open_supersplat and ev.get("status") == "done" and ev.get("final_ply"):
                proj.open_in_supersplat(ev["final_ply"])


@app.post("/api/run")
async def start_run(payload: dict):
    global _run_task, _run_events
    if _run_task and not _run_task.done():
        raise HTTPException(409, "Já está uma run a decorrer")
    cfg = _build_config(payload)
    _run_events = []
    _run_task = asyncio.create_task(_run_and_broadcast(cfg))
    return {"status": "started", "scenedir": str(cfg.scenedir)}


@app.post("/api/cancel")
async def cancel_run():
    global _run_task
    if _run_task and not _run_task.done():
        _run_task.cancel()
        return {"status": "cancelling"}
    return {"status": "idle"}


@app.websocket("/ws/run")
async def ws_run(ws: WebSocket):
    await ws.accept()
    _run_clients.add(ws)
    # entrega backlog
    for ev in _run_events:
        await ws.send_json(ev)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _run_clients.discard(ws)


# ───────────────────────────────────────────────────── Projectos


@app.get("/api/projects")
async def list_projects():
    return {"projects": proj.load_projects(APP_ROOT)}


@app.post("/api/projects/discover")
async def discover_projects():
    items = proj.discover_projects(APP_ROOT)
    return {"projects": items, "count": len(items)}


@app.delete("/api/projects")
async def delete_project(scenedir: str):
    p = Path(scenedir).expanduser()
    if not p.exists():
        raise HTTPException(404, "Não existe")
    shutil.rmtree(p)
    items = [x for x in proj.load_projects(APP_ROOT) if x.get("scenedir") != scenedir]
    proj.save_projects(APP_ROOT, items)
    return {"status": "deleted"}


@app.post("/api/reveal")
async def reveal(path: str = Form(...)):
    proj.reveal_in_finder(path)
    return {"status": "ok"}


@app.post("/api/open-supersplat")
async def open_ss(path: str = Form(...)):
    proj.open_in_supersplat(path)
    return {"status": "ok"}


# ───────────────────────────────────────────────────── Estimativa rápida


# ───────────────────────────────────────────────────── Blender


@app.get("/api/blender/status")
async def blender_status():
    return {
        "installed": bi.is_blender_installed(),
        "addons_dir": str(bi.addons_dir()) if bi.addons_dir() else None,
        "version_dir": str(bi.blender_version_dir()) if bi.blender_version_dir() else None,
        "export_script": str(BLENDER_EXPORT_SCRIPT),
        "addon_downloads": str(ADDON_DOWNLOADS),
    }


@app.post("/api/blender/install-addons")
async def blender_install_addons():
    """Instala 3DGS Render (KIRI) + Photogrammetry Importer descomprimindo os zips de ~/Downloads/blender-gs-addons/."""
    results = []
    candidates = [
        (ADDON_DOWNLOADS / "3dgs_render_kiri_5.0.0.zip", "3dgs_render_by_kiri_engine_5.0.0"),
        (ADDON_DOWNLOADS / "photogrammetry_importer.zip", "photogrammetry_importer"),
    ]
    enable_list: list[str] = []
    for zp, module in candidates:
        if not zp.exists():
            results.append({"zip": str(zp), "ok": False, "error": "Zip não existe — descarrega primeiro"})
            continue
        r = bi.install_addon_from_zip(zp)
        results.append({"zip": str(zp), **r})
        if r.get("ok"):
            enable_list.append(module)

    enable_r = await bi.enable_addons_headless(enable_list) if enable_list else {"ok": False, "log": "nada para activar"}
    return {"install_results": results, "enable_result": enable_r}


@app.post("/api/blender/export")
async def blender_export(payload: dict):
    """Cria um .blend com splat + câmaras COLMAP a partir de um scenedir."""
    scenedir = Path(payload["scenedir"]).expanduser()
    if not scenedir.exists():
        raise HTTPException(404, f"scenedir não existe: {scenedir}")
    # encontra o .ply final
    exports = scenedir / "exports"
    plys = sorted(exports.glob("export_*.ply")) if exports.exists() else []
    if not plys:
        raise HTTPException(404, "Nenhum .ply em exports/")
    ply = plys[-1]
    colmap_dir = scenedir / "sparse" / "0"
    out_blend = scenedir / f"{scenedir.name}.blend"
    r = await bi.export_scene(ply, colmap_dir, out_blend, BLENDER_EXPORT_SCRIPT)
    return r


@app.post("/api/estimate-frames")
async def estimate_frames(payload: dict):
    """Quantos frames vamos extrair? Lê duration via ffprobe."""
    video = Path(payload["video_path"]).expanduser()
    if not video.exists():
        raise HTTPException(404, "Vídeo não encontrado")
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
            capture_output=True, text=True, timeout=10,
        )
        duration = float(out.stdout.strip())
    except Exception as e:
        raise HTTPException(500, f"ffprobe falhou: {e}")
    fps = payload.get("fps", 3)
    max_frames = payload.get("max_frames", 300)
    raw = int(duration * fps)
    return {
        "duration_s": round(duration, 2),
        "extracted_raw": raw,
        "selected_estimate": min(raw, max_frames),
    }
