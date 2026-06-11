# GS Studio

> Web UI local em macOS para gerar **Gaussian Splatting** a partir de vídeo, com integração directa para Blender.

GS Studio orquestra um pipeline completo de fotogrametria + Gaussian Splatting:

```
Vídeo → frames nítidos → COLMAP (SfM) → Brush (treino GS) → .ply → Blender / superspl.at
```

Não substitui as ferramentas open-source — orquestra-as numa interface coerente, com presets, monitorização em directo e exportação directa para Blender.

## Por que existe

A maioria das implementações de Gaussian Splatting precisa de CUDA. Em macOS isso obriga a soluções alternativas. Este projecto encapsula a melhor stack actual para Mac Apple Silicon:

- **[sharp-frames](https://github.com/davidg191/sharp_frames)** para extracção de frames nítidos
- **[PyCOLMAP](https://github.com/colmap/colmap)** para Structure-from-Motion
- **[Brush](https://github.com/ArthurBrussee/brush)** (Rust + Metal via `wgpu`) como engine de treino
- **[3DGS Render](https://github.com/Kiri-Innovation/3dgs-render-blender-addon)** + **[Photogrammetry Importer](https://github.com/SBCV/Blender-Addon-Photogrammetry-Importer)** para integração com Blender

Inspirado e construído sobre os scripts de **[rodrigopolo/clis](https://github.com/rodrigopolo/clis)**.

## Quick start

```bash
git clone git@github.com:rodrigobrazao/gs-studio.git
cd gs-studio/app
./launch.sh
```

Abre `http://127.0.0.1:8765` no browser. A app verifica dependências automaticamente e oferece-se para instalar o que falta.

## Funcionalidades

- ✅ Verificação e instalação automática de dependências (Homebrew, ffmpeg, pyenv, Python, Brush, pycolmap, …)
- ✅ Upload de vídeo ou referência por caminho local
- ✅ Suporte para vídeo perspectiva 16:9 e equirectangular 360°
- ✅ Pipeline completo com 3 fases monitorizadas (Extract → COLMAP → Brush)
- ✅ Presets de qualidade (rápido / equilibrado / alta qualidade) + sliders avançados
- ✅ Streaming de logs em tempo real via WebSocket
- ✅ Histórico de projectos
- ✅ Exportação directa para Blender com câmaras COLMAP alinhadas
- ✅ Instalação automática de add-ons Blender

## Documentação

- [`docs/INSTALL.md`](docs/INSTALL.md) — dependências de sistema e setup inicial
- [`docs/PIPELINE.md`](docs/PIPELINE.md) — como o pipeline funciona internamente
- [`docs/BLENDER_WORKFLOW.md`](docs/BLENDER_WORKFLOW.md) — integrar character animado no splat dentro do Blender

## Estrutura

```
gs-studio/
├── app/              # Web UI (FastAPI + JS vanilla)
├── scripts/          # PyCOLMAP perspectiva para vídeo 16:9
├── blender/          # Integração Blender (export template, instalador add-ons)
└── docs/             # Documentação
```

## Requisitos

- macOS 12+ (Apple Silicon recomendado — M1/M2/M3/M4)
- Python 3.10+ (idealmente via pyenv)
- Blender 5.0+ (para a parte de Blender; opcional para usar só a Web UI)
- ~5 GB livres por projecto pequeno

## Contexto académico

Construído no âmbito do curso de **Licenciatura em Design Visual** do IADE, disciplina de **Modelação 3D**, com aplicação directa em **Projecto de Produção Multimédia**.

## Licença

MIT — ver [`LICENSE`](LICENSE).
