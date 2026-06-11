# Workflow: Character animado dentro de Gaussian Splat no Blender

Guia específico para Blender **5.1.1** com o projecto **IMG_1139_v01** (cenário) + character animado.

## Caso de uso

- **Cenário** = Gaussian Splat (do vídeo gravado, `~/Desktop/IMG_1139_v01/exports/export_50000.ply`)
- **Câmara** = fixa (escolhe um dos pontos de vista do COLMAP, ou cria nova)
- **Character** = animado dentro do cenário

---

## 1. Instalar add-ons (uma vez só)

### 1.a · **Splats** (extensão oficial Blender — instalação mais fácil)

1. Blender → `Edit → Preferences → Get Extensions`
2. Pesquisa **"Splats"**
3. Carrega em **Install**
4. Activa o toggle

Esta serve para abertura rápida de `.ply` GS no viewport.

### 1.b · **3DGS Render by KIRI Engine v5.0** (o principal — render e animação)

Ficheiro: `~/Downloads/blender-gs-addons/3dgs_render_kiri_5.0.0.zip` *(738 MB)*

1. Blender → `Edit → Preferences → Add-ons`
2. Top-right ▾ → **Install from Disk…**
3. Aponta para o zip acima → **Install**
4. Activa o toggle "3DGS Render by KIRI Engine"
5. Reinicia o Blender (carrega modelos ML internos)

Este é o que vai permitir **render em EEVEE/Cycles** e **animar deformações** do splat (não vais precisar disso aqui, mas é bom ter).

### 1.c · **Blender Photogrammetry Importer** (importa câmaras COLMAP)

Ficheiro: `~/Downloads/blender-gs-addons/photogrammetry_importer.zip` *(116 KB)*

1. `Edit → Preferences → Add-ons → Install from Disk…`
2. Selecciona o zip → **Install**
3. Activa o toggle

---

## 2. Montar a cena

### 2.a · Importar o cenário (Gaussian Splat)

`File → Import → 3DGS Render` *(ou via painel lateral do add-on KIRI)*
→ aponta para:
```
~/Desktop/IMG_1139_v01/exports/export_50000.ply
```

O splat aparece na viewport. Roda/escala se necessário (eixos do COLMAP nem sempre coincidem com os do Blender).

### 2.b · Importar as câmaras do COLMAP

`File → Import → Colmap (.txt/.bin)` *(via Photogrammetry Importer)*
→ aponta para:
```
~/Desktop/IMG_1139_v01/sparse/0/
```
*(a pasta com `cameras.bin`, `images.bin`, `points3D.bin`)*

Opções recomendadas:
- ✅ **Import Cameras**
- ✅ **Import Points** *(útil como referência visual da estrutura)*
- ❌ Image Plane (opcional — coloca preview de cada frame; pesado se tens muitas frames)

Vais ter agora **N câmaras** no Outliner (uma por frame registado). Escolhe a que melhor enquadra a cena para o teu shot.

### 2.c · Alinhar o splat com as câmaras

Se o splat não aparece exactamente onde os pontos COLMAP esperam:

1. Selecciona o splat no Outliner
2. `Object → Set Origin → Origin to 3D Cursor` (com o cursor em 0,0,0)
3. Se a orientação parece "deitada", roda 90° em X: `R, X, 90, Enter`

> **Dica**: as câmaras COLMAP e o splat partilham o mesmo espaço métrico. Se importares ambos com defaults, devem coincidir. Se não coincidirem, é quase sempre rotação de eixos (Blender Z-up, COLMAP Y-down).

---

## 3. Trazer o character

1. `File → Append…` (ou Link, se quiseres referência viva)
2. Aponta para o `.blend` do teu character
3. Append: **Collection** ou **Armature + Mesh**

Posicionamento:
- O **splat tem escala real** (metros do mundo) — se o teu character tem escala diferente, ajusta com `S` até parecer credível
- Coloca o character no chão do cenário (vê os pontos COLMAP como guia)

---

## 4. Definir câmara fixa

Como decidiste **câmara fixa, character a mover-se**:

1. Selecciona uma câmara COLMAP que mostra um bom enquadramento do cenário (ex: `Camera_frame_00010`)
2. `View → Cameras → Set Active Object as Camera` (ou `Ctrl+Numpad 0`)
3. **Bloqueia transformação**: `Object → Constraints → Limit Location/Rotation` com todos os eixos travados — ou simplesmente não animes a câmara

Alternativa: cria uma câmara nova num ponto de vista escolhido por ti e usa essa.

---

## 5. Iluminação (o ponto crítico)

O splat tem **luz baked-in** do dia em que filmaste. Para o character não parecer colado:

### Estratégia A — HDRI gerado do próprio splat ⭐ (recomendado)

O GS Studio inclui um gerador de HDRI panorâmico no painel **Output → Gerar HDRI**:

1. Escolhe o projecto, define resolução (4096×2048 cobre 99% dos casos)
2. Engine: **Cycles** para qualidade final, **EEVEE** para preview rápido
3. Posição: `auto` usa o centroide dos pontos COLMAP (boa para começar)
4. Carrega **Renderizar HDRI** — sai um `hdri.exr` na pasta do projecto

Aplicar no Blender:
1. `World → Surface → Background → Color → Environment Texture`
2. Aponta para `<scenedir>/hdri.exr`
3. Strength: começa em 1.0, ajusta visualmente até o character "encaixar"
4. Opcional: roda o HDRI com Mapping node se a orientação não coincidir

O character recebe iluminação **direccional e cromaticamente coerente** com o cenário — sombras, reflexos especulares (em pele, metal, plástico) e tons gerais vão encaixar no splat.

#### Como funciona internamente

- Backend invoca Blender headless com `blender/render_hdri.py`
- O script importa o splat, calcula o centroide dos pontos esparsos do COLMAP
- Cria câmara panorâmica equirectangular nessa posição (ou na que definiste)
- Renderiza em **.EXR 32-bit float** (preserva luz brilhante sem clamping)

#### Limitações conhecidas

- O HDRI só tem boa informação onde o teu vídeo tinha cobertura. Filmaste a meia altura? Zénite e nadir do panorama vão estar pretos/desfocados. Para character em pé numa cena de altura humana, isto não afecta o resultado visível.
- A escala de luz é **arbitrária** (não é HDRI calibrado fisicamente). Vais provavelmente ajustar `Strength` no World para casar com a exposição da câmara.

### Estratégia B — Luz neutra no character
- World → cor neutra (cinza médio ou HDRI difuso genérico)
- Sem luzes direccionais fortes — o character só apanha luz ambiente
- Funciona se o cenário tinha luz muito suave (nublado, interior difuso)

### Estratégia C — Match-light manual
- Identifica direcção da luz principal no vídeo
- Cria um Sun light na mesma direcção
- Ajusta intensidade até as sombras coincidirem com as do splat

---

## 6. Oclusão (se o character precisa de passar atrás de algo do cenário)

O splat é **renderizado como pixels**, não tem geometria 3D para fazer occlusion proper. Soluções:

### Opção rápida — mesh proxy invisível
1. Importa os pontos COLMAP (`points3D.bin`) como point cloud
2. Converte em mesh com Geometry Nodes (`Mesh from Points → Convex Hull` ou Poisson)
3. Aplica material **Holdout** → fica invisível mas oclui o character

### Opção avançada — depth-aware composite
- Renderiza o splat com depth pass
- Renderiza o character separado
- Compõe em Compositor com Z-combine

---

## 7. Render

### Preview rápido (EEVEE Next)
- Render Engine: **EEVEE Next**
- Splat aparece em real-time
- Bom para iterar

### Final (Cycles)
- Render Engine: **Cycles**
- Splat renderizado correctamente com luz/sombras integradas
- Lento mas fica fotorrealista

### Resolução e formato
- Mesma resolução do vídeo original (1920×1080 do teu IMG_1139)
- Output: PNG sequence para preservar canal alpha se vais compor depois

---

## 8. Animation timeline

Para o character animado em câmara fixa:

```
Frame 1   → character pose inicial
Frame N   → character pose final
Câmara    → estática, sem keyframes
Splat     → estático, sem keyframes
World     → estático
```

Length total: ajusta ao tempo da tua animação (typical 24–60 fps × 5–10 s).

---

## Troubleshooting

| Problema | Causa provável | Solução |
|---|---|---|
| Splat aparece deitado | Eixos Blender vs COLMAP | Roda 90° em X |
| Splat muito pequeno | COLMAP usa unidade arbitrária | Escala uniforme até parecer real |
| Character "flutua" | Plano de chão não coincide | Importa pontos COLMAP como referência, alinha visual |
| Sombras do character não combinam | Luz não matched | Estratégia C de iluminação (Sun light direcional) |
| Render Cycles lento | Splat muito denso | Decimar splat em superspl.at antes de importar |
| Add-on KIRI não carrega | Faltam modelos ML | Reiniciar Blender após primeira instalação |

---

## Referências

- [3DGS Render KIRI v5.0 GitHub](https://github.com/Kiri-Innovation/3dgs-render-blender-addon)
- [Splats — Blender Extensions](https://extensions.blender.org/add-ons/splats/)
- [Blender Photogrammetry Importer GitHub](https://github.com/SBCV/Blender-Addon-Photogrammetry-Importer)
- [Splatware — Blender 5 GS workflow](https://splatware.com/learn/gaussian-splatting-blender)
