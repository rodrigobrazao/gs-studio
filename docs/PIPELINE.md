# Pipeline interno

Este documento descreve como GS Studio orquestra as três fases do pipeline de Gaussian Splatting.

```
┌──────────────┐      ┌────────────────┐      ┌────────────────┐      ┌──────────┐
│   Vídeo      │ ──▶  │  Extracção de  │ ──▶  │  COLMAP (SfM)  │ ──▶  │  Brush   │ ──▶ .ply
│  (.mov/.mp4) │      │  frames        │      │                │      │  (Metal) │
└──────────────┘      └────────────────┘      └────────────────┘      └──────────┘
                       sharp-frames           pycolmap                Rust + wgpu
```

## Fase 1 — Extracção de frames

Implementação: `app/backend/pipeline.py::phase_extract` invoca `~/clis/GaussianSplatting/Exctract.sh`.

### O que faz
1. Extrai N frames por segundo do vídeo via `ffmpeg`
2. Calcula sharpness score de cada frame
3. Selecciona os mais nítidos (`best-n`, `outlier-removal` ou `batched`)
4. Escreve em `<scenedir>/frames/`

### Parâmetros expostos
- `fps`: 1–10 frames/s (default 3)
- `max_frames`: 50–500 (default 300)
- `selection`: estratégia de selecção

### Notas
- Em vídeos curtos com muito movimento de câmara, o `sharp-frames` tende a descartar muitos frames. Solução: aumentar fps.
- O algoritmo `best-n` privilegia nitidez; `batched` privilegia distribuição uniforme no tempo (melhor para sequências curtas).

## Fase 2 — COLMAP (Structure-from-Motion)

Implementação: `app/backend/pipeline.py::phase_colmap` invoca:
- Vídeo perspectiva → `scripts/PerspectivePyColmap.py` (próprio do GS Studio)
- Vídeo equirectangular → `~/clis/GaussianSplatting/A1PyColmap.py`

### O que faz
1. Cria symlink `<scenedir>/images → frames` (Brush espera pasta `images`)
2. Extracção de features SIFT (`pycolmap.extract_features`)
3. Matching entre frames (sequential para vídeo, exhaustive para fotos)
4. Mapping incremental — estima poses 3D das câmaras e triangula pontos
5. Output em `<scenedir>/sparse/<N>/{cameras.bin, images.bin, points3D.bin}`

### Parâmetros expostos
- `camera_model`: SIMPLE_PINHOLE (1) → OPENCV (8 params)
- `single_camera`: usar mesma câmara para todos os frames
- `matcher`: `sequential` (vídeo) ou `exhaustive` (fotos)

### Notas
- 100% das frames registadas = ideal. Abaixo de 80% indica problemas (texturas pobres, sobreposição insuficiente).
- O número de pontos esparsos típico para uma cena pequena é 3–10 mil.

## Fase 3 — Brush (treino Gaussian Splatting)

Implementação: `app/backend/pipeline.py::phase_brush`.

### O que faz
1. Selecciona o melhor modelo sparse (mais imagens registadas)
2. (Opcional) Faz backup `sparse_backup.zip`
3. Move o melhor modelo para `<scenedir>/sparse/0/`
4. Invoca o binário `brush`:
   ```sh
   brush <scenedir> \
     --total-steps 30000 \
     --max-splats 4000000 \
     --growth-stop-iter 15000 \
     --sh-degree 3 \
     --export-every 5000 \
     --export-path <scenedir>/exports/
   ```

### O algoritmo (resumo)
- Inicializa gaussianas 3D nos pontos esparsos do COLMAP
- Itera: renderiza visão sintética → compara com frame real → ajusta posição/cor/opacidade/escala via Adam
- **Densificação**: gaussianas com alto erro são clonadas/divididas (cresce nº de splats)
- **Pruning**: gaussianas com opacidade baixa são removidas
- A partir de `growth_stop_iter`, só refina; não cresce mais

### Hardware
- Brush usa **Metal** via `wgpu` (Rust) — corre na GPU integrada do Apple Silicon
- M1 base: ~20–40 passos/s
- M3 Max: ~80–100 passos/s
- M4 Pro/Max: 100+ passos/s

### Output
- `<scenedir>/exports/export_<step>.ply` a cada `export_every` passos
- Final: `export_<total_steps>.ply` (50–250 MB típico)

## Integração com Blender

Implementação: `app/backend/blender_integration.py` + `blender/export_template.py`.

### O que faz
1. Verifica se o Blender está instalado em `/Applications/Blender.app`
2. Invoca o Blender em modo headless: `blender --background --python blender/export_template.py -- --ply ... --colmap ... --out ...`
3. O script Python dentro do Blender:
   - Activa add-ons (3DGS Render, Photogrammetry Importer)
   - Importa o `.ply` como Gaussian Splat
   - Importa câmaras COLMAP do `sparse/0/`
   - Adiciona um placeholder para o character
   - Configura World, render (EEVEE Next, 1920×1080, 30 fps)
   - Guarda como `.blend`

Resultado: ficheiro `<scenedir>/<projecto>.blend` pronto a abrir.

Ver [`docs/BLENDER_WORKFLOW.md`](BLENDER_WORKFLOW.md) para o que fazer depois.

## Estado partilhado

A app mantém **uma run de cada vez** em memória:
- `_run_task: asyncio.Task` — a task em execução
- `_run_events: list[dict]` — backlog para clientes que liguem a meio
- `_run_clients: set[WebSocket]` — conexões activas

Comunicação backend → frontend via WebSocket `/ws/run`. Cada evento é `{"type": "phase"|"log"|"cmd"|"end", ...}` em JSON.

## Persistência

| Onde | O quê |
|---|---|
| `<scenedir>/` | Resultados de cada projecto (definido pelo utilizador) |
| `app/data/uploads/` | Vídeos arrastados para a app |
| `app/data/projects.json` | Histórico de projectos (gerido pelo `projects.py`) |
