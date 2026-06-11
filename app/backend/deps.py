"""Verificação e instalação de dependências do pipeline Gaussian Splatting."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

from .pyresolve import user_python


@dataclass
class Dep:
    name: str
    label: str
    kind: str            # "binary" | "python" | "file"
    check: str           # comando / módulo / path
    install_hint: str    # instrução shell para instalar
    required: bool = True
    version: str | None = None
    found: bool = False


HOME = Path.home()

DEPS: list[Dep] = [
    Dep("xcode_clt", "Xcode Command Line Tools", "binary", "xcode-select",
        "xcode-select --install"),
    Dep("homebrew", "Homebrew", "binary", "brew",
        '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'),
    Dep("ffmpeg", "FFmpeg", "binary", "ffmpeg", "brew install ffmpeg"),
    Dep("xz", "xz", "binary", "xz", "brew install xz"),
    Dep("pyenv", "pyenv", "binary", "pyenv", "brew install pyenv"),
    Dep("python", "Python 3.12+", "binary", "python3",
        "pyenv install 3.12.9 && pyenv global 3.12.9"),
    Dep("brush", "Brush (Gaussian Splatting engine)", "binary", "brush",
        "mkdir -p ~/.local/bin && "
        "curl -L https://github.com/ArthurBrussee/brush/releases/download/v0.3.0/brush-app-aarch64-apple-darwin.tar.xz "
        "| tar xJf - && "
        "mv brush-app-aarch64-apple-darwin/brush_app ~/.local/bin/brush && "
        "rm -rf brush-app-aarch64-apple-darwin"),
    Dep("clis_repo", "Repo rodrigopolo/clis", "file", str(HOME / "clis" / "GaussianSplatting"),
        f"cd && git clone https://github.com/rodrigopolo/clis.git"),
    Dep("pycolmap", "pycolmap", "python", "pycolmap",
        "$USER_PY -m pip install pycolmap"),
    Dep("sharp_frames", "sharp-frames", "python", "sharp_frames",
        "$USER_PY -m pip install sharp-frames"),
    Dep("opencv", "OpenCV (headless)", "python", "cv2",
        "$USER_PY -m pip install opencv-python-headless"),
    Dep("pillow", "Pillow", "python", "PIL",
        "$USER_PY -m pip install Pillow"),
    Dep("scipy", "SciPy", "python", "scipy",
        "$USER_PY -m pip install scipy"),
]


def _check_binary(name: str) -> tuple[bool, str | None]:
    path = shutil.which(name)
    if not path:
        return False, None
    try:
        out = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=5)
        version = (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else "ok"
    except Exception:
        version = "ok"
    return True, version


def _check_python(module: str) -> tuple[bool, str | None]:
    try:
        out = subprocess.run(
            [user_python(), "-c", f"import {module}; print(getattr({module}, '__version__', 'ok'))"],
            capture_output=True, text=True, timeout=8,
        )
    except Exception:
        return False, None
    if out.returncode != 0:
        return False, None
    return True, out.stdout.strip() or "ok"


def _check_file(path: str) -> tuple[bool, str | None]:
    p = Path(path).expanduser()
    return p.exists(), str(p) if p.exists() else None


def check_all() -> list[dict]:
    results: list[dict] = []
    for dep in DEPS:
        if dep.kind == "binary":
            found, version = _check_binary(dep.check)
        elif dep.kind == "python":
            found, version = _check_python(dep.check)
        else:
            found, version = _check_file(dep.check)
        dep.found = found
        dep.version = version
        results.append(asdict(dep))
    return results


async def install_one(dep_name: str) -> asyncio.subprocess.Process:
    """Devolve o processo a correr; o caller faz stream do output."""
    dep = next((d for d in DEPS if d.name == dep_name), None)
    if dep is None:
        raise ValueError(f"Dep desconhecida: {dep_name}")
    cmd = dep.install_hint.replace("$USER_PY", user_python())
    return await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
