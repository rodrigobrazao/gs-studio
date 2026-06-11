# GS Studio

App local em macOS para gerar **Gaussian Splatting** a partir de vídeo, com pipeline completo (extracção de frames → COLMAP → Brush).

Wrapper visual sobre os scripts de [rodrigopolo/clis](https://github.com/rodrigopolo/clis) + um pipeline COLMAP perspectiva próprio (`PerspectivePyColmap.py`) para vídeo 16:9 normal.

## Arranque

```sh
cd gs-studio
./launch.sh
```

Cria um virtualenv, instala dependências (FastAPI + uvicorn + python-multipart) e abre `http://localhost:8765` no browser.

## O que faz

- **Sistema** — verifica e instala Brew, ffmpeg, pyenv, Python, Brush, pycolmap, sharp-frames, OpenCV, Pillow, scipy
- **Projecto** — upload de vídeo, escolha da pasta de destino, tipo de input (perspectiva vs 360°)
- **Frames** — controla FPS, máximo de frames e algoritmo de selecção do `sharp-frames`
- **COLMAP** — modelo de câmara (SIMPLE_RADIAL ⭐), single-camera, matcher sequencial/exhaustivo
- **Brush** — presets (rápido/equilibrado/alta qualidade) + sliders avançados para todos os hiperparâmetros
- **Output** — abertura automática no [superspl.at/editor](https://superspl.at/editor), limpeza de intermédios
- **Execução** — progresso por fase, logs em directo via WebSocket, cancelamento
- **Histórico** — projectos anteriores com botões "Abrir no Finder" e "Abrir no superspl.at"

## Estrutura

```
gs-studio/
├── backend/
│   ├── main.py                # FastAPI + WebSocket
│   ├── deps.py                # check + install de dependências
│   ├── pipeline.py            # 3 fases com stream de eventos
│   ├── projects.py            # histórico
│   └── PerspectivePyColmap.py # COLMAP para vídeo 16:9 (copiado em runtime)
├── static/
│   ├── css/app.css            # design system (dark mode editorial)
│   └── js/app.js              # vanilla JS, sem framework
├── templates/index.html
├── data/
│   ├── projects.json          # histórico persistente
│   └── uploads/               # vídeos via drag-and-drop
├── requirements.txt
└── launch.sh
```

## Notas

- A app não substitui as dependências de sistema (Homebrew, Brush, etc.) — apenas as gere. Os instaladores correm `brew install …`, `pip install …` ou `curl … | tar …` consoante a dependência.
- O vídeo pode ser **carregado** (copiado para `data/uploads/`) ou **referenciado por caminho** (mais rápido para vídeos grandes).
- O resultado final fica em `<pasta-destino>/<projecto>/exports/export_<N>.ply`.

## Requisitos mínimos

- macOS 12+ (Apple Silicon recomendado)
- Python 3.10+ (a app prefere o `python3` do PATH; ideal: pyenv 3.12.9)
- Espaço em disco: ~500 MB por projecto pequeno (vídeo + frames + sparse + splat final)
