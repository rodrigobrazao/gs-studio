#!/usr/bin/env bash
# Instala os add-ons Blender necessários para o workflow GS Studio.
# Independente da Web UI — corre standalone.
#
# Uso:
#   ./install_addons.sh                # usa ~/Downloads/blender-gs-addons
#   ./install_addons.sh /caminho/zips  # usa pasta custom

set -euo pipefail

ZIPS_DIR="${1:-$HOME/Downloads/blender-gs-addons}"
BLENDER_APP="/Applications/Blender.app/Contents/MacOS/Blender"

if [[ ! -x "$BLENDER_APP" ]]; then
  echo "✗ Blender não encontrado em /Applications/Blender.app" >&2
  exit 1
fi

# Detecta versão mais recente em ~/Library/Application Support/Blender/
BLENDER_PREFS_ROOT="$HOME/Library/Application Support/Blender"
VERSION_DIR=$(ls -1d "$BLENDER_PREFS_ROOT"/[0-9]* 2>/dev/null | sort -V | tail -1)
if [[ -z "$VERSION_DIR" ]]; then
  echo "✗ Pasta de preferências do Blender não encontrada" >&2
  exit 1
fi
ADDONS_DIR="$VERSION_DIR/scripts/addons"
mkdir -p "$ADDONS_DIR"
echo "→ Add-ons em: $ADDONS_DIR"
echo ""

ENABLE_MODULES=()

install_zip() {
  local zip="$1"
  local module_hint="$2"
  if [[ ! -f "$zip" ]]; then
    echo "⚠️  $zip não existe — pula"
    return
  fi
  echo "→ A descomprimir $(basename "$zip")…"
  # Detecta o nome do diretório de top-level
  local top
  top=$(unzip -Z -1 "$zip" | head -1 | sed 's|/.*||')
  rm -rf "$ADDONS_DIR/$top"
  unzip -q -o "$zip" -d "$ADDONS_DIR"
  echo "  ✓ instalado: $top"
  ENABLE_MODULES+=("$module_hint")
}

install_zip "$ZIPS_DIR/3dgs_render_kiri_5.0.0.zip" "3dgs_render_by_kiri_engine_5.0.0"
install_zip "$ZIPS_DIR/photogrammetry_importer.zip" "photogrammetry_importer"

if [[ ${#ENABLE_MODULES[@]} -gt 0 ]]; then
  echo ""
  echo "→ A activar add-ons em Blender headless (pode demorar)…"
  PYTHON_EXPR=$(cat <<EOF
import bpy
modules = ${ENABLE_MODULES[@]@Q}
ok, fail = [], []
for m in modules.split():
    try:
        bpy.ops.preferences.addon_enable(module=m)
        ok.append(m)
    except Exception as e:
        fail.append((m, str(e)))
bpy.ops.wm.save_userpref()
print("ENABLED", ok)
print("FAILED", fail)
EOF
)
  "$BLENDER_APP" --background --python-expr "$PYTHON_EXPR" 2>&1 | tail -20
fi

echo ""
echo "✓ Concluído. Abre o Blender e confirma em Edit → Preferences → Add-ons."
