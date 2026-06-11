"""Pipeline Gaussian Splatting: extract → COLMAP → Brush, com stream de logs."""
from __future__ import annotations

import asyncio
import json
import shutil
import textwrap
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Literal

from .pyresolve import user_python


HOME = Path.home()
CLIS = HOME / "clis" / "GaussianSplatting"


@dataclass
class FramesCfg:
    fps: float = 3
    max_frames: int = 300
    selection: Literal["best-n", "outlier-removal", "batched"] = "best-n"


@dataclass
class ColmapCfg:
    camera_model: Literal[
        "SIMPLE_PINHOLE", "PINHOLE", "SIMPLE_RADIAL", "RADIAL", "OPENCV"
    ] = "SIMPLE_RADIAL"
    single_camera: bool = True
    matcher: Literal["sequential", "exhaustive"] = "sequential"
    input_kind: Literal["perspective", "equirectangular"] = "perspective"


@dataclass
class BrushCfg:
    total_steps: int = 30000
    max_splats: int = 4_000_000
    growth_stop_iter: int = 15000
    sh_degree: int = 3
    max_resolution: int | None = None      # None = sem downsample
    export_every: int = 5000


@dataclass
class OutputCfg:
    auto_open_supersplat: bool = True
    keep_intermediate_plys: bool = False
    keep_database: bool = False
    backup_sparse: bool = True


@dataclass
class RunConfig:
    project_name: str
    video_path: str
    output_root: str
    frames: FramesCfg = field(default_factory=FramesCfg)
    colmap: ColmapCfg = field(default_factory=ColmapCfg)
    brush: BrushCfg = field(default_factory=BrushCfg)
    output: OutputCfg = field(default_factory=OutputCfg)

    @property
    def scenedir(self) -> Path:
        return Path(self.output_root).expanduser() / self.project_name

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "video_path": self.video_path,
            "output_root": self.output_root,
            "frames": asdict(self.frames),
            "colmap": asdict(self.colmap),
            "brush": asdict(self.brush),
            "output": asdict(self.output),
        }


# ───────────────────────────────────────────────────── Stream helpers


async def _stream_process(proc: asyncio.subprocess.Process) -> AsyncIterator[str]:
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        yield line.decode(errors="replace").rstrip()
    await proc.wait()


# ───────────────────────────────────────────────────── Phases


async def phase_extract(cfg: RunConfig) -> AsyncIterator[dict]:
    """Extracção de frames nítidos via Exctract.sh do Polo."""
    yield {"type": "phase", "phase": "extract", "status": "start"}

    scenedir = cfg.scenedir
    scenedir.mkdir(parents=True, exist_ok=True)
    script = CLIS / "Exctract.sh"
    if not script.exists():
        yield {"type": "error", "message": f"Não encontro {script}"}
        return

    cmd = (
        f'{script} '
        f'--scenedir "{scenedir}" '
        f'--fps {cfg.frames.fps} '
        f'--frames {cfg.frames.max_frames} '
        f'"{cfg.video_path}"'
    )
    yield {"type": "cmd", "cmd": cmd}
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    async for line in _stream_process(proc):
        yield {"type": "log", "phase": "extract", "line": line}
    yield {
        "type": "phase",
        "phase": "extract",
        "status": "done" if proc.returncode == 0 else "error",
        "rc": proc.returncode,
    }


async def phase_colmap(cfg: RunConfig, perspective_script: Path) -> AsyncIterator[dict]:
    """COLMAP: PerspectivePyColmap.py (perspectiva) ou A1PyColmap.py (360°)."""
    yield {"type": "phase", "phase": "colmap", "status": "start"}

    scenedir = cfg.scenedir
    if cfg.colmap.input_kind == "equirectangular":
        script = CLIS / "A1PyColmap.py"
    else:
        script = perspective_script
    if not script.exists():
        yield {"type": "error", "message": f"Não encontro {script}"}
        return

    args = [user_python(), str(script), "--scenedir", str(scenedir)]
    if cfg.colmap.input_kind == "perspective":
        args += ["--camera-model", cfg.colmap.camera_model, "--matcher", cfg.colmap.matcher]
    cmd = " ".join(f'"{a}"' if " " in a else a for a in args)
    yield {"type": "cmd", "cmd": cmd}
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    async for line in _stream_process(proc):
        yield {"type": "log", "phase": "colmap", "line": line}
    yield {
        "type": "phase",
        "phase": "colmap",
        "status": "done" if proc.returncode == 0 else "error",
        "rc": proc.returncode,
    }


async def phase_brush(cfg: RunConfig) -> AsyncIterator[dict]:
    """Treino do Gaussian Splat com Brush. Substitui o Brush.sh para passar args custom."""
    yield {"type": "phase", "phase": "brush", "status": "start"}

    scenedir = cfg.scenedir
    # 1) seleccionar melhor modelo sparse (lógica do Brush.sh)
    sparse_root = scenedir / "sparse"
    if not sparse_root.exists():
        yield {"type": "error", "message": "Falta pasta sparse/. Corre o COLMAP primeiro."}
        return

    # Se já existe sparse/0/ com images.bin, está pronto; senão escolhe o melhor.
    if not (sparse_root / "0" / "images.bin").exists():
        best, best_count = None, 0
        for model_dir in sparse_root.glob("*/"):
            images_bin = model_dir / "images.bin"
            if not images_bin.exists():
                continue
            try:
                proc = await asyncio.create_subprocess_exec(
                    user_python(), "-c",
                    f"import pycolmap; m=pycolmap.Reconstruction(r'{model_dir}'); print(len(m.images))",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                )
                out, _ = await proc.communicate()
                count = int(out.decode().strip() or 0)
            except Exception:
                count = 0
            yield {"type": "log", "phase": "brush", "line": f"sparse {model_dir.name}: {count} imagens"}
            if count > best_count:
                best, best_count = model_dir, count
        if best is None:
            yield {"type": "error", "message": "Nenhum modelo sparse válido."}
            return
        if cfg.output.backup_sparse:
            backup = scenedir / "sparse_backup.zip"
            yield {"type": "log", "phase": "brush", "line": f"Backup → {backup.name}"}
            shutil.make_archive(str(backup.with_suffix("")), "zip", root_dir=scenedir, base_dir="sparse")
        if best.name != "0":
            yield {"type": "log", "phase": "brush", "line": f"A mover {best.name} → 0"}
            (sparse_root / "0").mkdir(exist_ok=True)
            for f in best.iterdir():
                shutil.move(str(f), sparse_root / "0" / f.name)
            shutil.rmtree(best)

    # 2) correr brush
    exports = scenedir / "exports"
    exports.mkdir(exist_ok=True)
    args = [
        "brush", str(scenedir),
        "--total-steps", str(cfg.brush.total_steps),
        "--max-splats", str(cfg.brush.max_splats),
        "--growth-stop-iter", str(cfg.brush.growth_stop_iter),
        "--sh-degree", str(cfg.brush.sh_degree),
        "--export-every", str(cfg.brush.export_every),
        "--export-path", str(exports),
    ]
    if cfg.brush.max_resolution:
        args += ["--max-resolution", str(cfg.brush.max_resolution)]
    cmd = " ".join(f'"{a}"' if " " in a else a for a in args)
    yield {"type": "cmd", "cmd": cmd}
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    async for line in _stream_process(proc):
        yield {"type": "log", "phase": "brush", "line": line}
    yield {
        "type": "phase",
        "phase": "brush",
        "status": "done" if proc.returncode == 0 else "error",
        "rc": proc.returncode,
    }


# ───────────────────────────────────────────────────── Orchestration


async def run_pipeline(cfg: RunConfig, perspective_script: Path) -> AsyncIterator[dict]:
    """Corre as 3 fases sequencialmente, fazendo yield de eventos para WebSocket."""
    start = datetime.now()
    yield {"type": "start", "ts": start.isoformat(), "config": cfg.to_dict()}

    try:
        async for ev in phase_extract(cfg):
            yield ev
            if ev.get("type") == "phase" and ev.get("status") == "error":
                yield {"type": "end", "status": "error", "phase": "extract"}
                return

        async for ev in phase_colmap(cfg, perspective_script):
            yield ev
            if ev.get("type") == "phase" and ev.get("status") == "error":
                yield {"type": "end", "status": "error", "phase": "colmap"}
                return

        async for ev in phase_brush(cfg):
            yield ev
            if ev.get("type") == "phase" and ev.get("status") == "error":
                yield {"type": "end", "status": "error", "phase": "brush"}
                return

        # Cleanup opcional
        if not cfg.output.keep_intermediate_plys:
            exports = cfg.scenedir / "exports"
            keep = f"export_{cfg.brush.total_steps:05d}.ply"
            for p in exports.glob("export_*.ply"):
                if p.name != keep:
                    p.unlink(missing_ok=True)
                    yield {"type": "log", "phase": "cleanup", "line": f"apaguei {p.name}"}
        if not cfg.output.keep_database:
            db = cfg.scenedir / "database.db"
            if db.exists():
                db.unlink()
                yield {"type": "log", "phase": "cleanup", "line": "apaguei database.db"}

        final_ply = cfg.scenedir / "exports" / f"export_{cfg.brush.total_steps:05d}.ply"
        yield {
            "type": "end",
            "status": "done",
            "elapsed_s": (datetime.now() - start).total_seconds(),
            "final_ply": str(final_ply) if final_ply.exists() else None,
        }
    except asyncio.CancelledError:
        yield {"type": "end", "status": "cancelled"}
        raise


def perspective_script_path(app_root: Path) -> Path:
    """Caminho do PerspectivePyColmap.py — vive em <repo>/scripts/."""
    return app_root.parent / "scripts" / "PerspectivePyColmap.py"
