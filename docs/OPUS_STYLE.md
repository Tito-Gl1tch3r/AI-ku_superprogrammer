# La mente de Opus 5.5 — ingeniería inversa del estilo (v0.4.0)

Este documento resume **cómo trabaja Claude Opus 5.5 cuando construye vídeos
generativos por código y mods crossover**, tal como se extrae de artefactos
reales publicados, y cómo cada principio destilado quedó convertido en tareas
verificadas de este dataset. La lógica es la misma que siguió el proyecto con
la metodología universal-modder (v0.3.0): se aprende el método general, nunca
se copia código ni assets.

## 1. Fuentes analizadas

| Fuente | Qué es | Qué se extrajo |
|---|---|---|
| [mexicat/pdoom-video](https://github.com/mexicat/pdoom-video) (MIT, © Giacomo Magnanini) | Vídeo musical generativo "I'm Upping My P(doom)" — **construido por Opus 5.5 en Claude Code**; TypeScript + three.js, render determinista 1920×1080/4K | Su `docs/ENGINE.md` es literalmente la guía operativa que Opus escribió para agentes Opus: contrato de determinismo, paleta centralizada, toolbox de render, muestreo adaptativo, etiqueta multi-agente |
| [JohnHeibel/ClaudeAnimationBase](https://github.com/JohnHeibel/ClaudeAnimationBase) (MIT, © 2026 John Heibel) | Kit forkable del mismo estilo (p5.brush, mascota con 31 emociones) cuyo `ANIMATION_GUIDE.md` "Claude lo lee primero" | Modelo de timing por *reads* del espectador, storyboard-first, principios de animación aplicados a código, reglas anti-fallos típicos de generación |
| [pdoomvideo.com](https://pdoomvideo.com) | Guía fan de 10 pasos para hacer tu propio vídeo Opus 5.5 | Flujo completo: kit → canción (Suno, pista de letras del .m4a → SRT) → BPM/offset → config → stills/contact sheets → ffmpeg |
| Forks del repo (p. ej. `OnePoMan/Teeth-music-video`) | Mods reales producidos con Opus | Evidencia del flujo de producción por placas con *handoffs* ("CHANGE? approved", conceptos, aprobaciones) |
| Ola 2026 de crossovers (Minecraft-in-Elden-Ring de TobynJacobs; `GBurgardt/pokemon-emerald-arena` sobre el decomp de pret; tendencia documentada por VGC/GamerBraves) | Dos juegos ejecutándose a la vez, puenteados en tiempo real | Patrón bridge: recon/decomp → proceso adaptador → traducción de eventos con orden, idempotencia y rate limit → oracle en el juego real |

## 2. Los principios destilados y su trazabilidad

### P1 — El determinismo es un contrato, no una propiedad
"La salida debe ser función pura de `f.t` (y de aleatoriedad sembrada:
`mulberry32(seed)`, `hash(...)`). Nunca `Math.random()`, `Date.now()` ni
`performance.now()` para visuals." Además, nada puede contar cuántas veces se
llama a `render()`: el export renderiza sub-frames fuera de orden y en
cualquier cantidad.

**En el dataset**: toda familia MV exige byte-stability (`a == b` en dos
renders), `media_mv_scene_engine` y `media_mv_project` fallan si el código no
es puro; `media_mv_determinism_debug` entrena el diagnóstico.

### P2 — `floor(t * 60)` es una trampa: `frameIdx(t)`
El export promedia muchos sub-frames repartidos por el shutter del frame. Si
el parpadeo se siembra con `floor(t*60)`, el shutter cae exactamente sobre el
borde de la región y **cada frame exportado es un fantasma 50/50 de dos
estados**. `frameIdx(t)` es constante sobre el shutter: ese es su único
trabajo. Reglas hermanas: el ruido continuo se siembra con `frameIdx(t)`, y
la tasa de un emisor se pasa como función del tiempo de nacimiento.

**En el dataset**: `mv_frameidx_pitfall` hace calcular el número de estados
distintos promediados y su reparto, con la aritmética real de muestreo
recomputada en el builder.

### P3 — Paleta centralizada con tres caras
Un hex decide la marca: `C_*` en GLSL, `LIN.*` en TS para GL, `rgba('nombre')`
en Canvas2D. Cambiar 3 constantes propaga a ~95% de las escenas; lo que no
pasa por la paleta es un bug vestido de parche (el "hardcodeado que funciona"
tras un recoloreado).

**En el dataset**: `media_mv_post_chain` añade el tinte turquesa de halation
por constante; `mv_palette_propagation` entrena el radio de blast de un cambio
en palette.ts, incluyendo el fichero que cambia por la razón equivocada.

### P4 — El ORDEN de la cadena de post ES el look
exposure → bright-pass con knee suave → blur → halation → viñeta → grano →
cuantizar sRGB. Difuminar antes del bright-pass pone halo sobre TODO; cortar
el knee a lo duro hace que el bloom "salte" en los golpes de baile; el grano
tras cuantizar se redondea a nada (cero dither).

**En el dataset**: `media_mv_post_chain` con los tres bugs canónicos
(`blur_before_bright`, `hard_clip_knee`, `grain_after_quantize`), cada uno
matado por asserts exactos sobre bytes concretos.

### P5 — El batching de líneas es un contrato de orden
`LineBatch` aplana polilíneas en segmentos GPU; el orden debe ser total y
estable: `(z, seq, seg)` — empates por orden de autoría, nunca por suerte del
contenedor. El manifest hash cubre la lista ORDENADA.

**En el dataset**: `media_mv_line_batch` (con el matiz de que el `sort` de
Python ya es estable: el bug real es usar una clave que no refleja el
contrato, p. ej. `(z, seg, seq)`).

### P6 — Píxeles lógicos vs físicos (la lección 4K)
En `?scale=2` el layout sigue en 1920×1080 lógicos; el AA y el suelo de
hairline trabajan en píxeles físicos: `max(width, HAIRLINE_PX / SCALE)`. Un
suelo lógico constante produce líneas 4K gordas; un suelo físico produce
hairlines nítidas a cualquier escala.

**En el dataset**: `media_mv_line_batch` variante `hairline_scale` con
SCALE=2 forzado.

### P7 — El timing se modela desde el espectador: los "reads"
"Para cada momento, pregunta qué necesita entender el espectador y cuánto
tardará en entenderlo." Cada *read* cuesta encontrarlo + entenderlo + un
hold; un read nuevo no empieza mientras el anterior aterriza; el shot acaba
en hold; la anticipación va ANTES de la acción y no solapa. El fallo típico
de la animación generada: todo a una velocidad brusca y eventos apilados.

**En el dataset**: `media_mv_shot_reads` (`read_schedule` y `anticipation`,
con los bugs `final_hold_dropped` y `anticipation_overlaps`).

### P8 — Producción por placas, storyboard primero, MIRA los renders
Se escribe `STORYBOARD.md` antes del código de escenas; cada placa es un
fichero de escena; el workflow verifica con stills y contact sheets ("después
MIRA los PNGs con la herramienta Read"); los cambios de diseño se aprueban en
handoffs (los commits de los forks reales lo muestran: "handoff: CHANGE?
approved; chorus 1 notes").

**En el dataset**: `media_mv_project` (proyecto multi-file con manifest y
tests de determinismo) + `media_mv_shot_reads` (el storyboard cuantificado).

### P9 — Etiqueta multi-agente del engine
Cada agente de escena toca SOLO sus ficheros `scenes/<name>*.ts`;
`timeline.ts` intocable; los motivos compartidos (`_motifs.ts`) son
read-only; los cambios de engine se piden al lead. Así escalan N agentes
Opus sin pisarse.

**En el dataset**: la estructura de familias replica esa modularidad (cada
familia es su propio módulo con contrato propio; `registry.py` hace de lead).

### P10 — El puente crossover: idempotencia, orden por canal, difierir
El patrón de la ola 2026: decompilar ambos juegos, correr los dos, y un
proceso puente traduce eventos A→B en tiempo real. Los invariantes que
separan un mod jugable de un vídeo de mentira: entrega **at-most-once**
clave `(canal, seq)`, **FIFO por canal** (un sort global por seq es OTRO
contrato), y rate limit que **difiere** el overflow a una cola por canal que
se drena — nunca lo suelta.

**En el dataset**: `game_crossover_bridge` (los tres invariantes con sus tres
bugs canónicos) y `crossover_event_debug` (localizar la primera divergencia
de logs y su delta de inventario en B).

### P11 — El recon de memoria antes de puentear
Antes de puentear la vida de un juego hay que encontrarla: scan little-endian
de dwords sobre snapshots, **intersección** de candidatos entre dos estados
(los decoys estáticos caen por el cambio, no por suerte), y solo entonces el
freeze/patch.

**En el dataset**: `game_state_scan` (`union_not_intersect` y
`big_endian_write` como bugs canónicos).

## 3. Cómo se verifica que el dataset "aprendió" el estilo

- Cada familia ejecuta su código de referencia en el sandbox y compara contra
  valores dorados exactos (bytes, hashes, horarios de fases).
- Los bugs incorporados reproducen los fallos REALES del estilo (halo
  universal, fantasma 50/50, línea 4K gorda, doble entrega, decoy congelado)
  y fallan deterministamente.
- El color de señal por defecto de todo el bloque MV es el turquesa Miku
  `#39C5BB` — identidad de AI-ku, nunca el naranja original.
- Trazabilidad: 5 familias write + 3 builders understand, 622 records
  publicados en v0.4.0 (ver `CHANGELOG.md`).

## 4. Nota legal y de alcance

Ambas referencias de vídeo son MIT; se estudian como arquitectura conceptual
y se reimplementa desde cero con objetivos sintéticos. La guía fan
(pdoomvideo.com) es material descriptivo. La canción original NO está
liberada: aquí no hay audio, letras ni assets de terceros — solo patrones de
ingeniería convertidos en código original verificable.
