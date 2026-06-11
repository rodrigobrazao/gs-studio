"""Integração com Blender: instalação de add-ons e exportação de cenas."""
from __future__ import annotations

import asyncio
import shutil
import zipfile
from pathlib import Path


HOME = Path.home()
BLENDER_APP = Path("/Applications/Blender.app/Contents/MacOS/Blender")
BLENDER_PREFS_ROOTS = sorted(
    [p for p in (HOME / "Library" / "Application Support" / "Blender").glob("*") if p.is_dir()],
    reverse=True,
)


def blender_version_dir() -> Path | None:
    """Devolve a pasta da versão mais recente do Blender no perfil do utilizador."""
    return BLENDER_PREFS_ROOTS[0] if BLENDER_PREFS_ROOTS else None


def addons_dir() -> Path | None:
    v = blender_version_dir()
    if not v:
        return None
    p = v / "scripts" / "addons"
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_blender_installed() -> bool:
    return BLENDER_APP.exists()


# ───────────────────────────────────────────── Install add-ons


def install_addon_from_zip(zip_path: Path) -> dict:
    """Descomprime um zip de add-on para a pasta de add-ons do utilizador."""
    target = addons_dir()
    if not target:
        return {"ok": False, "error": "Pasta de add-ons do Blender não encontrada"}
    if not zip_path.exists():
        return {"ok": False, "error": f"Zip não encontrado: {zip_path}"}

    extracted_names: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        # detecta o nome do diretório de top-level
        top_levels = {n.split("/")[0] for n in zf.namelist() if "/" in n}
        if len(top_levels) != 1:
            return {"ok": False, "error": f"Zip com múltiplos toplevels: {top_levels}"}
        top = top_levels.pop()
        dest = target / top
        if dest.exists():
            shutil.rmtree(dest)
        zf.extractall(target)
        extracted_names.append(top)

    return {"ok": True, "installed": extracted_names, "target": str(target)}


async def enable_addons_headless(modules: list[str]) -> dict:
    """Activa add-ons via Blender headless e guarda userpref.blend."""
    if not is_blender_installed():
        return {"ok": False, "error": "Blender não encontrado em /Applications/Blender.app"}

    py = (
        "import bpy\n"
        f"modules = {modules!r}\n"
        "ok, fail = [], []\n"
        "for m in modules:\n"
        "    try:\n"
        "        bpy.ops.preferences.addon_enable(module=m)\n"
        "        ok.append(m)\n"
        "    except Exception as e:\n"
        "        fail.append((m, str(e)))\n"
        "bpy.ops.wm.save_userpref()\n"
        "print('ENABLED', ok)\n"
        "print('FAILED', fail)\n"
    )
    proc = await asyncio.create_subprocess_exec(
        str(BLENDER_APP), "--background", "--python-expr", py,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    out = stdout.decode(errors="replace")
    enabled = "ENABLED [" in out
    return {"ok": proc.returncode == 0 and enabled, "log": out[-4000:]}


# ───────────────────────────────────────────── Export to .blend


async def export_scene(
    ply_path: Path,
    colmap_dir: Path,
    out_blend: Path,
    blender_export_script: Path,
) -> dict:
    """Corre o Blender em headless para gerar um .blend com splat + câmaras."""
    if not is_blender_installed():
        return {"ok": False, "error": "Blender não encontrado em /Applications/Blender.app"}
    if not ply_path.exists():
        return {"ok": False, "error": f"PLY não encontrado: {ply_path}"}
    if not colmap_dir.exists():
        return {"ok": False, "error": f"Pasta COLMAP não encontrada: {colmap_dir}"}
    if not blender_export_script.exists():
        return {"ok": False, "error": f"Script export não encontrado: {blender_export_script}"}

    out_blend.parent.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        str(BLENDER_APP), "--background",
        "--python", str(blender_export_script),
        "--",
        "--ply", str(ply_path),
        "--colmap", str(colmap_dir),
        "--out", str(out_blend),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    out = stdout.decode(errors="replace")
    return {
        "ok": proc.returncode == 0 and out_blend.exists(),
        "log": out[-6000:],
        "blend": str(out_blend) if out_blend.exists() else None,
    }
