"""Gestão do histórico de projectos."""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def projects_index_path(app_root: Path) -> Path:
    p = app_root / "data" / "projects.json"
    if not p.exists():
        p.write_text("[]")
    return p


def load_projects(app_root: Path) -> list[dict]:
    return json.loads(projects_index_path(app_root).read_text())


def save_projects(app_root: Path, items: list[dict]) -> None:
    projects_index_path(app_root).write_text(json.dumps(items, indent=2, ensure_ascii=False))


def upsert_project(app_root: Path, entry: dict) -> None:
    items = load_projects(app_root)
    items = [x for x in items if x.get("scenedir") != entry.get("scenedir")]
    items.insert(0, entry)
    save_projects(app_root, items[:200])


def project_summary(scenedir: Path) -> dict:
    exports = scenedir / "exports"
    plys = sorted(exports.glob("export_*.ply")) if exports.exists() else []
    final = plys[-1] if plys else None
    frames = scenedir / "frames"
    n_frames = len([f for f in frames.glob("*.jpg")]) if frames.exists() else 0
    return {
        "scenedir": str(scenedir),
        "name": scenedir.name,
        "modified": datetime.fromtimestamp(scenedir.stat().st_mtime).isoformat() if scenedir.exists() else None,
        "n_frames": n_frames,
        "final_ply": str(final) if final else None,
        "final_ply_size_mb": round(final.stat().st_size / 1024 / 1024, 1) if final else None,
        "n_intermediate_plys": len(plys),
    }


def reveal_in_finder(path: str) -> None:
    p = Path(path).expanduser()
    if p.exists():
        subprocess.Popen(["open", "-R", str(p)])


def open_in_supersplat(path: str) -> None:
    """superspl.at é browser-only — abre o site e o ficheiro no Finder para drag-and-drop."""
    subprocess.Popen(["open", "https://superspl.at/editor"])
    reveal_in_finder(path)


def discover_projects(app_root: Path, roots: list[Path] | None = None) -> list[dict]:
    """Procura scenedirs (qualquer pasta com sparse/0/ e/ou exports/*.ply) e adiciona ao histórico."""
    if roots is None:
        home = Path.home()
        roots = [home / "Desktop", home / "Documents", home / "Movies"]
    found: list[dict] = []
    seen_paths: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        # procura até 3 níveis dentro de cada root
        for path in root.glob("*"):
            if not path.is_dir():
                continue
            looks_like_scenedir = (
                (path / "sparse" / "0").exists()
                or (path / "exports").exists()
                or (path / "frames").exists()
            )
            if not looks_like_scenedir:
                continue
            if str(path) in seen_paths:
                continue
            seen_paths.add(str(path))
            summary = project_summary(path)
            found.append(summary)
    # merge com o histórico existente
    existing = load_projects(app_root)
    existing_paths = {x.get("scenedir") for x in existing}
    new_entries = [f for f in found if f["scenedir"] not in existing_paths]
    if new_entries:
        merged = new_entries + existing
        # ordena por modified desc
        merged.sort(key=lambda x: x.get("modified") or "", reverse=True)
        save_projects(app_root, merged[:200])
        return merged
    return existing
