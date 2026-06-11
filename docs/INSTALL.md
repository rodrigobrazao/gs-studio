# Instalação

GS Studio depende de várias ferramentas open-source. A maioria pode ser instalada pela própria app (painel **Sistema**), mas este documento descreve o que está por baixo.

## Pré-requisitos

- macOS 12+ (idealmente Apple Silicon — M1/M2/M3/M4)
- Conexão à internet (para descarregar ferramentas)

## Stack completa

### Camada de sistema

| Ferramenta | Para que serve | Instalação |
|---|---|---|
| **Xcode Command Line Tools** | Compilador, git, headers | `xcode-select --install` |
| **Homebrew** | Gestor de pacotes | Ver [brew.sh](https://brew.sh) |
| **FFmpeg** | Decodificação de vídeo | `brew install ffmpeg` |
| **xz** | Descompressão `.tar.xz` (Brush) | `brew install xz` |
| **pyenv** | Gestão de versões Python | `brew install pyenv` |

### Python

Recomenda-se `pyenv` + Python **3.12.9**:

```sh
pyenv install 3.12.9
pyenv global 3.12.9
```

### Pacotes Python (no Python do pyenv)

```sh
python3 -m pip install --upgrade pip
python3 -m pip install pycolmap sharp-frames opencv-python-headless Pillow scipy
```

### Brush (Gaussian Splatting engine)

Binário pré-compilado para Apple Silicon (~80 MB):

```sh
mkdir -p ~/.local/bin
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc

curl -L https://github.com/ArthurBrussee/brush/releases/download/v0.3.0/brush-app-aarch64-apple-darwin.tar.xz \
  | tar xJf -
mv brush-app-aarch64-apple-darwin/brush_app ~/.local/bin/brush
rm -rf brush-app-aarch64-apple-darwin
```

### Scripts do Polo (dependência de runtime)

GS Studio reutiliza o `Exctract.sh` de [rodrigopolo/clis](https://github.com/rodrigopolo/clis):

```sh
cd && git clone https://github.com/rodrigopolo/clis.git
```

### Blender (opcional, só para a integração)

- Descarrega Blender 5.0+ de [blender.org](https://www.blender.org/download/)
- A app instala os add-ons automaticamente pelo botão "Instalar add-ons Blender"

## Instalação automatizada

Tudo o que precede pode ser feito pelo painel **Sistema** da app:

```sh
cd app
./launch.sh
```

→ http://127.0.0.1:8765 → carrega em **Instalar todas em falta**.

## Troubleshooting

| Sintoma | Causa | Solução |
|---|---|---|
| `pycolmap` não importa | Foi instalado no Python errado | Confirmar `pyenv which python3` e instalar nesse |
| `brush: command not found` | `~/.local/bin` não no PATH | Adicionar ao `~/.zshrc` |
| `sharp-frames` falha com PIL/_imaging | Versão incompatível | Reinstalar Pillow: `pip install -U Pillow` |
| Mais que um Python disponível | Confusão venv/pyenv/system | Ver `app/backend/pyresolve.py` para a ordem de preferência |
