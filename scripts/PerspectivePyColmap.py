#!/usr/bin/env python3
"""
Pipeline COLMAP perspectiva (PyCOLMAP) para vídeo 16:9 normal.

Adaptado de A1PyColmap.py (rodrigopolo/clis), que era específico para input
equirectangular (360°). Esta versão assume frames perspectiva standard.

Estrutura esperada:
  <scenedir>/frames/   <- frames nítidos extraídos pelo Exctract.sh

Estrutura produzida:
  <scenedir>/images/   <- mesmos frames, renomeados para a convenção do Brush
  <scenedir>/sparse/<N>/{cameras.bin, images.bin, points3D.bin}

Uso:
  ./PerspectivePyColmap.py --scenedir ~/Desktop/Projecto
"""

import argparse
import shutil
from pathlib import Path

import pycolmap


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenedir", required=True, type=Path, help="Diretório do projecto")
    ap.add_argument(
        "--camera-model",
        default="SIMPLE_RADIAL",
        choices=["SIMPLE_PINHOLE", "PINHOLE", "SIMPLE_RADIAL", "RADIAL", "OPENCV"],
        help="Modelo de câmara COLMAP (default: SIMPLE_RADIAL)",
    )
    ap.add_argument(
        "--matcher",
        default="sequential",
        choices=["sequential", "exhaustive"],
        help="Estratégia de matching (sequential para vídeo, exhaustive para fotos soltas)",
    )
    args = ap.parse_args()

    scenedir: Path = args.scenedir.expanduser().resolve()
    frames_dir = scenedir / "frames"
    images_dir = scenedir / "images"
    sparse_dir = scenedir / "sparse"
    database_path = scenedir / "database.db"

    if not frames_dir.is_dir():
        raise SystemExit(f"Erro: não existe {frames_dir}. Corre primeiro o Exctract.sh.")

    # Garante a convenção do Brush: pasta chama-se "images/"
    if not images_dir.exists():
        print(f"[1/4] A criar symlink {images_dir} -> {frames_dir.name}")
        images_dir.symlink_to(frames_dir.name)
    else:
        print(f"[1/4] {images_dir} já existe — reutilizado")

    sparse_dir.mkdir(parents=True, exist_ok=True)

    # Reset da database (corridas anteriores podem deixar lixo)
    if database_path.exists():
        print(f"     A apagar database antiga: {database_path}")
        database_path.unlink()

    print(f"[2/4] Extracção de features ({args.camera_model})…")
    reader_opts = pycolmap.ImageReaderOptions()
    reader_opts.camera_model = args.camera_model
    pycolmap.extract_features(
        database_path=database_path,
        image_path=images_dir,
        camera_mode=pycolmap.CameraMode.SINGLE,  # mesma câmara em todos os frames (vídeo)
        reader_options=reader_opts,
    )

    print(f"[3/4] Matching ({args.matcher})…")
    if args.matcher == "sequential":
        pycolmap.match_sequential(database_path=database_path)
    else:
        pycolmap.match_exhaustive(database_path=database_path)

    print("[4/4] Mapping incremental (Structure-from-Motion)…")
    maps = pycolmap.incremental_mapping(
        database_path=database_path,
        image_path=images_dir,
        output_path=sparse_dir,
    )

    if not maps:
        raise SystemExit(
            "Erro: COLMAP não conseguiu reconstruir nenhum modelo. "
            "Verifica se os frames têm sobreposição suficiente e textura."
        )

    print("\n=== Reconstrução concluída ===")
    for idx, rec in maps.items():
        print(f"  Modelo {idx}: {rec.num_reg_images()} imagens registadas, "
              f"{rec.num_points3D()} pontos 3D")
    print(f"\nPróximo passo:")
    print(f"  ~/clis/GaussianSplatting/Brush.sh --scenedir {scenedir}")


if __name__ == "__main__":
    main()
