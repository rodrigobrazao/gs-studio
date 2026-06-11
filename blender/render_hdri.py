"""
GS Studio · render HDRI equirectangular a partir de um Gaussian Splat.

Corre dentro do Blender em modo headless. Importa o splat, posiciona uma
câmara panorâmica no centroide dos pontos COLMAP (ou numa posição custom),
renderiza em .EXR 32-bit e guarda.

Uso (chamado pela app):
  blender --background --python render_hdri.py -- \
      --ply <path>/export_50000.ply \
      --colmap <path>/sparse/0/ \
      --out <path>/hdri.exr \
      --resolution 4096x2048 \
      --engine cycles \
      --samples 128 \
      --position auto
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    ap = argparse.ArgumentParser()
    ap.add_argument("--ply", required=True, type=Path, help="Splat .ply")
    ap.add_argument("--colmap", required=True, type=Path, help="Pasta sparse/0/")
    ap.add_argument("--out", required=True, type=Path, help="Output .exr")
    ap.add_argument("--resolution", default="4096x2048", help="WxH (default 4096x2048, ratio 2:1)")
    ap.add_argument("--engine", default="cycles", choices=["cycles", "eevee"])
    ap.add_argument("--samples", type=int, default=128, help="Render samples (Cycles)")
    ap.add_argument(
        "--position", default="auto",
        help='"auto" (centroide dos pontos COLMAP) ou "x,y,z"',
    )
    return ap.parse_args(argv)


def log(msg: str) -> None:
    print(f"[gs-studio hdri] {msg}", flush=True)


def reset_scene(bpy) -> None:
    bpy.ops.wm.read_homefile(use_empty=True)


def enable_addons(bpy) -> None:
    for module in (
        "3dgs_render_by_kiri_engine_5.0.0",
        "3dgs_render_by_kiri_engine",
        "bl_ext.blender_org.splats",
        "photogrammetry_importer",
    ):
        try:
            bpy.ops.preferences.addon_enable(module=module)
            log(f"add-on activado: {module}")
        except Exception:
            pass


def import_splat(bpy, ply: Path) -> bool:
    handlers = [
        "sna.dgs_render_import_ply_e0a3a",  # KIRI v5.0
        "wm.ply_import",                    # built-in 4.0+
        "import_mesh.ply",                  # legado
    ]
    for op_name in handlers:
        try:
            op = bpy.ops
            for part in op_name.split("."):
                op = getattr(op, part)
            op(filepath=str(ply))
            log(f"splat importado via bpy.ops.{op_name}")
            return True
        except Exception as e:
            log(f"  bpy.ops.{op_name} falhou: {e}")
            continue
    log("⚠️ Nenhum importador GS disponível — sem splat na cena, o HDRI ficará preto")
    return False


def import_colmap_points(bpy, sparse_dir: Path) -> bool:
    """Importa câmaras + pontos para podermos calcular o centroide.
    Tolera SystemError nas drawings dos pontos em modo background."""
    import os
    directory_with_slash = str(sparse_dir).rstrip(os.sep) + os.sep
    images_dir = sparse_dir.parent.parent / "images"
    if not images_dir.exists():
        images_dir = sparse_dir.parent.parent / "frames"
    try:
        bpy.ops.import_scene.colmap_model(
            directory=directory_with_slash,
            image_dp=str(images_dir),
        )
    except Exception as e:
        log(f"Aviso COLMAP (ignorado, possivelmente GPU em background): {e}")
    # Contar o que ficou na cena
    n_cams = sum(1 for o in bpy.data.objects if o.type == "CAMERA")
    log(f"COLMAP · {n_cams} câmaras")
    return n_cams > 0


def compute_centroid(bpy) -> tuple[float, float, float]:
    """Centroide preferencialmente dos pontos COLMAP. Em modo background os
    pontos podem não ter sido criados (limitação GPU drawing); usamos então
    o centroide das posições das câmaras como aproximação razoável."""
    xs, ys, zs = [], [], []
    # 1) tentar pontos
    for obj in bpy.data.objects:
        nm = obj.name.lower()
        if "point" in nm or "colmap" in nm or obj.type == "POINTCLOUD":
            if obj.type == "MESH" and obj.data and obj.data.vertices:
                for v in obj.data.vertices:
                    w = obj.matrix_world @ v.co
                    xs.append(w.x); ys.append(w.y); zs.append(w.z)
    if xs:
        cx, cy, cz = (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs))
        log(f"centroide de {len(xs)} pontos: ({cx:.3f}, {cy:.3f}, {cz:.3f})")
        return (cx, cy, cz)

    # 2) fallback: centroide das câmaras COLMAP
    cam_xs, cam_ys, cam_zs = [], [], []
    for obj in bpy.data.objects:
        if obj.type == "CAMERA" and obj.name != "HDRI_Camera":
            cam_xs.append(obj.location.x)
            cam_ys.append(obj.location.y)
            cam_zs.append(obj.location.z)
    if cam_xs:
        cx, cy, cz = (sum(cam_xs) / len(cam_xs), sum(cam_ys) / len(cam_ys), sum(cam_zs) / len(cam_zs))
        log(f"centroide (fallback) de {len(cam_xs)} câmaras: ({cx:.3f}, {cy:.3f}, {cz:.3f})")
        return (cx, cy, cz)

    log("centroide: sem pontos nem câmaras, uso (0,0,0)")
    return (0.0, 0.0, 0.0)


def parse_position(s: str, bpy) -> tuple[float, float, float]:
    if s.strip().lower() == "auto":
        return compute_centroid(bpy)
    try:
        parts = [float(p) for p in s.split(",")]
        if len(parts) != 3:
            raise ValueError("precisa de 3 valores x,y,z")
        return tuple(parts)
    except Exception as e:
        log(f"posição inválida ({e}) — uso (0,0,0)")
        return (0.0, 0.0, 0.0)


def setup_camera(bpy, position: tuple[float, float, float]):
    cam_data = bpy.data.cameras.new("HDRI_Camera")
    cam_data.type = "PANO"
    # Em Cycles, o tipo de panorâmica:
    try:
        cam_data.panorama_type = "EQUIRECTANGULAR"
    except Exception:
        # Blender 4.5+/5.x usa propriedade no cycles
        try:
            cam_data.cycles.panorama_type = "EQUIRECTANGULAR"
        except Exception:
            log("⚠️ Sem campo panorama_type — vais ter de definir manualmente")
    cam_obj = bpy.data.objects.new("HDRI_Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = position
    # Olha para cima (+Z) — equirectangular orienta-se sozinho à volta
    cam_obj.rotation_euler = (1.5707963, 0, 0)  # 90° em X (panorama horizontal)
    bpy.context.scene.camera = cam_obj
    log(f"câmara panorâmica em ({position[0]:.3f}, {position[1]:.3f}, {position[2]:.3f})")
    return cam_obj


def setup_render(bpy, resolution: str, engine: str, samples: int, out_path: Path) -> None:
    scene = bpy.context.scene
    try:
        w, h = (int(x) for x in resolution.lower().split("x"))
    except Exception:
        w, h = 4096, 2048
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    if engine == "cycles":
        scene.render.engine = "CYCLES"
        try:
            scene.cycles.samples = samples
            scene.cycles.use_denoising = True
            # GPU/Metal se disponível
            prefs = bpy.context.preferences.addons["cycles"].preferences
            try:
                prefs.compute_device_type = "METAL"
                for d in prefs.devices:
                    d.use = True
                scene.cycles.device = "GPU"
                log("Cycles a usar Metal GPU")
            except Exception:
                log("Cycles a usar CPU")
        except Exception:
            pass
    else:
        try:
            scene.render.engine = "BLENDER_EEVEE_NEXT"
        except Exception:
            scene.render.engine = "BLENDER_EEVEE"

    # Output .EXR 32-bit
    scene.render.image_settings.file_format = "OPEN_EXR"
    try:
        scene.render.image_settings.color_depth = "32"
        scene.render.image_settings.exr_codec = "PIZ"
    except Exception:
        pass
    out_path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_path)
    log(f"output: {out_path} · {w}×{h} · engine={engine}")


def main() -> None:
    args = parse_args()
    log(f"PLY:    {args.ply}")
    log(f"COLMAP: {args.colmap}")
    log(f"OUT:    {args.out}")

    import bpy

    reset_scene(bpy)
    enable_addons(bpy)

    import_splat(bpy, args.ply)
    import_colmap_points(bpy, args.colmap)
    position = parse_position(args.position, bpy)
    setup_camera(bpy, position)
    setup_render(bpy, args.resolution, args.engine, args.samples, args.out)

    log("a renderizar…")
    bpy.ops.render.render(write_still=True)
    if args.out.exists():
        log(f"✓ HDRI guardado: {args.out} ({args.out.stat().st_size // 1024} KB)")
    else:
        log(f"✗ ficheiro não foi criado em {args.out}")


if __name__ == "__main__":
    main()
