#!/usr/bin/env bash
# GS Studio — launcher
#
# Cria venv, instala dependências e arranca o servidor.
# Uso:
#   ./launch.sh            # arranca em http://localhost:8765
#   ./launch.sh --port 9000

set -euo pipefail

PORT=8765
HOST=127.0.0.1
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opção desconhecida: $1"; exit 1 ;;
  esac
done

# venv (usa python3 do sistema/pyenv — não precisa de pyenv install adicional)
if [[ ! -d ".venv" ]]; then
  echo "→ A criar venv…"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ A instalar/atualizar dependências…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

URL="http://${HOST}:${PORT}"
echo ""
echo "════════════════════════════════════════"
echo "  GS Studio a correr em:"
echo "  ${URL}"
echo "════════════════════════════════════════"
echo ""

# Abre o browser passados 1s
( sleep 1 && open "${URL}" ) &

# Arranca o servidor
exec uvicorn backend.main:app --host "${HOST}" --port "${PORT}" --log-level info
