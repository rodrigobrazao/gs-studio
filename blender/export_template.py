"""
GS Studio · gerador de .blend
Corre em modo headless dentro do Blender 5.x para construir uma cena com:
  - Splat (Gaussian Splatting .ply) importado via 3DGS Render (KIRI) ou Splats
  - Câmaras COLMAP importadas via Photogrammetry Importer
  - World e render setup razoáveis para começar a animar

Uso (chamado pela app GS Studio):
  blender --background --python export_template.py -- \
      --ply <path/to/export_30000.ply> \
      --colmap <path/to/sparse/0/> \
      --out <path/to/output.blend>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    # tudo depois de '--' é nosso; argparse precisa de ignorar args do Blender
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    ap = argparse.ArgumentParser()
    ap.add_argument("--ply", required=True, type=Path)
    ap.add_argument("--colmap", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    return ap.parse_args(argv)


def log(msg: str) -> None:
    print(f"[gs-studio export] {msg}", flush=True)


def reset_scene(bpy) -> None:
    bpy.ops.wm.read_homefile(use_empty=True)


def setup_world(bpy) -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)
        bg.inputs[1].default_value = 1.0


def setup_render(bpy) -> None:
    scene = bpy.context.scene
    # EEVEE (Blender 5.1) por defeito; algumas versões expõem _NEXT como alias
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except Exception:
            continue
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    # Viewport em RENDERED para ver o splat colorido logo ao abrir o .blend
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            try:
                area.spaces.active.shading.type = 'RENDERED'
            except Exception:
                pass


def activate_splat_modifiers(bpy) -> None:
    """KIRI deixa os modifiers de render com show_viewport=False por defeito.
    Ligamo-los para o splat aparecer colorido logo ao abrir o .blend."""
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        has_kiri = any("KIRI_3DGS" in m.name for m in obj.modifiers)
        if not has_kiri:
            continue
        for m in obj.modifiers:
            m.show_viewport = True
            m.show_render = True
        log(f"modifiers KIRI activados em '{obj.name}'")


def import_splat(bpy, ply_path: Path) -> bool:
    """Tenta importar o splat com os add-ons disponíveis. Devolve True se conseguir."""
    # 1) 3DGS Render by KIRI Engine (caminho preferencial)
    for module in ("3dgs_render_by_kiri_engine_5.0.0", "3dgs_render_by_kiri_engine"):
        try:
            bpy.ops.preferences.addon_enable(module=module)
            log(f"add-on KIRI activado: {module}")
            break
        except Exception:
            continue

    # 2) Splats (Blender extension oficial)
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.splats")
        log("Splats extension activada")
    except Exception:
        pass

    # 3) Tentar importar pelo operador real do KIRI v5.0
    #    (descoberto via inspecção do __init__.py do add-on)
    handlers = [
        ("sna.dgs_render_import_ply_e0a3a", {}),  # KIRI v5.0
        ("wm.ply_import", {}),                    # built-in Blender 4.0+ (sem material GS, mas funciona)
        ("import_mesh.ply", {}),                  # legado
    ]
    for op_name, params in handlers:
        try:
            op_path = op_name.split(".")
            op_module = bpy.ops
            for part in op_path:
                op_module = getattr(op_module, part)
            op_module(filepath=str(ply_path), **params)
            log(f"Splat importado via bpy.ops.{op_name}")
            return True
        except Exception as e:
            log(f"  bpy.ops.{op_name} falhou: {e}")
            continue
    log("⚠️ Nenhum importador disponível — o .ply terá de ser importado manualmente")
    return False


def import_colmap(bpy, sparse_dir: Path) -> int:
    """Importa câmaras + pontos esparsos via Photogrammetry Importer. Devolve nº câmaras."""
    import os
    try:
        bpy.ops.preferences.addon_enable(module="photogrammetry_importer")
    except Exception as e:
        log(f"Aviso: Photogrammetry Importer não disponível ({e})")
        return 0
    # 1) trailing slash em directory (add-on faz os.path.dirname)
    # 2) image_dp explícito porque a nossa estrutura tem images/ 2 níveis acima
    # 3) o operador pode lançar SystemError na fase de drawing dos pontos
    #    em modo --background; nesse caso, as câmaras já foram criadas e
    #    contamos-las à mesma.
    directory_with_slash = str(sparse_dir).rstrip(os.sep) + os.sep
    images_dir = sparse_dir.parent.parent / "images"
    if not images_dir.exists():
        images_dir = sparse_dir.parent.parent / "frames"
    log(f"image_dp → {images_dir}")
    try:
        bpy.ops.import_scene.colmap_model(
            directory=directory_with_slash,
            image_dp=str(images_dir),
        )
    except Exception as e:
        # Tolerar — pode falhar nos pontos (GPU drawing em background)
        log(f"Aviso durante import COLMAP (ignorado): {e}")
    n_cams = sum(1 for o in bpy.data.objects if o.type == "CAMERA")
    log(f"COLMAP · {n_cams} câmaras na cena")
    return n_cams


def add_character_placeholder(bpy) -> None:
    """Adiciona um cubo simples como placeholder para o character animado."""
    bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0, 0, 0.25))
    obj = bpy.context.active_object
    obj.name = "CHARACTER_PLACEHOLDER"
    # destaca a cor
    mat = bpy.data.materials.new(name="character_placeholder_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (1.0, 0.35, 0.24, 1.0)
    obj.data.materials.append(mat)


def main() -> None:
    args = parse_args()
    log(f"PLY:    {args.ply}")
    log(f"COLMAP: {args.colmap}")
    log(f"OUT:    {args.out}")

    import bpy  # disponível apenas dentro do Blender

    reset_scene(bpy)
    setup_world(bpy)
    setup_render(bpy)

    splat_ok = import_splat(bpy, args.ply)
    activate_splat_modifiers(bpy)
    n_cams = import_colmap(bpy, args.colmap)
    add_character_placeholder(bpy)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out))
    log(f"Guardado: {args.out}")
    log(f"Sumário: splat={'ok' if splat_ok else 'fallback/manual'} · câmaras={n_cams} · placeholder=CHARACTER_PLACEHOLDER")


if __name__ == "__main__":
    main()
