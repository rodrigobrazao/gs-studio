# Blender integration

Esta pasta contém o que GS Studio precisa para integrar com o Blender.

## Conteúdo

| Ficheiro | O que faz |
|---|---|
| `install_addons.sh` | Instala os add-ons necessários no Blender, sem precisar de abrir o Blender |
| `export_template.py` | Corre dentro do Blender (modo headless) para gerar um `.blend` com splat + câmaras COLMAP alinhadas |

## Add-ons usados

1. **[3DGS Render by KIRI Engine v5.0](https://github.com/Kiri-Innovation/3dgs-render-blender-addon)** — render real-time + offline de Gaussian Splats em Blender 5.1+
2. **[Blender Photogrammetry Importer](https://github.com/SBCV/Blender-Addon-Photogrammetry-Importer)** — importa câmaras + pontos esparsos de COLMAP
3. **[Splats](https://extensions.blender.org/add-ons/splats/)** *(opcional, instalado via Blender Extensions UI)* — extensão oficial para abertura rápida de PLY GS

## Instalação manual

Se o botão "Instalar add-ons Blender" da Web UI não funcionar:

1. Descarrega os zips para `~/Downloads/blender-gs-addons/`:
   - `3dgs_render_kiri_5.0.0.zip` (~704 MB) de [Kiri-Innovation releases](https://github.com/Kiri-Innovation/3dgs-render-blender-addon/releases/latest)
   - `photogrammetry_importer.zip` (~120 KB) de [SBCV releases](https://github.com/SBCV/Blender-Addon-Photogrammetry-Importer/releases/latest)
2. Corre:
   ```sh
   cd blender
   ./install_addons.sh
   ```
3. Abre o Blender → `Edit → Preferences → Add-ons` e confirma que estão activos.

## Export template

O `export_template.py` é chamado pela app através de:

```sh
blender --background \
  --python blender/export_template.py \
  -- --ply <path/to/.ply> \
     --colmap <path/to/sparse/0/> \
     --out <path/to/output.blend>
```

Quando aberto, o `.blend` contém:
- O splat importado e visível na viewport
- Todas as câmaras COLMAP do projecto (uma por frame registado)
- Pontos esparsos como referência espacial
- Um cubo cor-de-laranja `CHARACTER_PLACEHOLDER` na origem — substitui-o pelo teu character

Vê [`docs/BLENDER_WORKFLOW.md`](../docs/BLENDER_WORKFLOW.md) para o workflow completo.
