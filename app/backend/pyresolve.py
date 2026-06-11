"""Encontra o Python "do utilizador" — o que tem pycolmap/cv2/sharp-frames instalado.

Ordem de preferência:
1. PYTHON_BIN env var
2. ~/.pyenv/shims/python3 (se existir)
3. /opt/homebrew/bin/python3 (Homebrew Apple Silicon)
4. /usr/bin/python3 (sistema)
5. python3 do PATH
"""
from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def user_python() -> str:
    env = os.environ.get("PYTHON_BIN")
    if env and Path(env).exists():
        return env
    candidates = [
        Path.home() / ".pyenv" / "shims" / "python3",
        Path("/opt/homebrew/bin/python3"),
        Path("/usr/bin/python3"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    p = shutil.which("python3")
    return p or "python3"
