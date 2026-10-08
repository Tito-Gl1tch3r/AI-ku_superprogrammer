# CHANGELOG

## [0.4.1] — Reordenación curricular (solo documentación, cero cambios de datos)

- **README reestructurado como plan de estudios numerado** en el orden en que AI-ku aprende: **00 · Code Comprehension** (1º entender el código) → **01 · Code Writing** (2º escribir código) → **02 · Opus 5.5 Generative Video** + **03 · Opus 5.5 Game Mixes & Modding** (3º, el tocho: crear vídeos y mezclas de juegos como Opus 5.5). Las secciones de referencia conceptual (pdoom-video / Opus-mind, Universal Modder / crossovers) quedan anidadas bajo sus módulos 02 y 03.
- **Nuevo `docs/CURRICULUM.md`**: etapas con justificación pedagógica del orden, contenido por módulo, mezclas de entrenamiento con replay anti-olvido, criterios de avance vía `hard_holdout`, y snippet funcional para construir los lotes de cada etapa filtrando shards por `dataset` + `provenance.generator` (nombres de generator auditados contra los shards reales).
- **Corregido**: la tabla de datasets del README arrastraba los counts de v0.3.0 (media 949 / game 1.968); ahora muestra los reales de v0.4.0 (media 1.310 / game 2.229), cuadrados con `reports/stats.json` y la DATASET_CARD. Referencias internas "Dataset 2/3/4" sustituidas por la numeración de módulos.
- Sin cambios en shards, hashes ni stats: los nombres y paths físicos de los datasets se mantienen estables por reproducibilidad; la numeración 00–03 es el orden pedagógico de presentación y entrenamiento.

## [0.4.0] — Extensión Opus-mind / crossover (ingeniería inversa de la autoría de Opus 5.5)

- **Nueva referencia**: se documenta en `docs/OPUS_STYLE.md` la ingeniería inversa de cómo trabaja Opus 5.5 al construir vídeos generativos y mods crossover: el propio `mexicat/pdoom-video` (MIT) es de autoría Opus (su `docs/ENGINE.md` es la guía operativa de agentes de escena: determinismo como contrato, paleta centralizada C_*/LIN.*/rgba(), LineBatch, cadena de post, píxeles lógicos vs físicos en 4K, etiqueta multi-agente), junto con la guía de animación de `JohnHeibel/ClaudeAnimationBase` (MIT: modelo de "reads", storyboard primero, principios de animación anti-código-mecánico) y la ola 2026 de crossovers (decompilar 2 juegos + puente en tiempo real).
- **5 familias write nuevas** (todas python, verificación real, bugs que fallan determinista):
  - `media_mv_post_chain` (`generators/media/opus_families.py`): cadena HDR exposure → bright-pass con knee suave → box blur separable → halation con tinte turquesa → viñeta → grano LCG → sRGB; bugs: blur antes del bright-pass (halo sobre todo), hard-clip del knee, grano tras cuantizar (no-op).
  - `media_mv_line_batch`: batching 2D determinista con orden total (z, seq, seg), manifest sha256 del lote ordenado y suelo de hairline en píxeles FÍSICOS (`HAIRLINE_PX / SCALE`); bugs: clave sin seq (interleave entre líneas con mismo z), suelo lógico constante (líneas 4K gordas).
  - `media_mv_shot_reads`: timing de planos desde "reads" del espectador (find → understand → hold, estrictamente secuenciales, hold final obligatorio, anticipación opcional); bugs: soltar el hold final, anticipación que solapa.
  - `game_crossover_bridge` (`generators/game/crossover_families.py`): puente determinista de eventos entre dos juegos-juguete — entrega idempotente por (chan, seq), FIFO por canal, rate limit que DIFIERE el overflow (nunca lo pierde); bugs: sin idempotencia (doble entrega), cola diferida nunca drenada, drenado global por seq (reordena canales).
  - `game_state_scan`: recon de memoria — scan little-endian de 4 bytes, intersección de dos snapshots para resolver la dirección viva (los decoys estáticos caen por el cambio), freeze con hash del imagen parcheada; bugs: unión en vez de intersección, write big-endian.
- **3 builders understand nuevos** (`generators/understand/opus.py`, evidencia real recalculada): `mv_frameidx_pitfall` (por qué `floor(t*60)` doble-expone dos estados dentro del shutter de un frame y `frameIdx(t)` no), `mv_palette_propagation` (radio de blast de un cambio en palette.ts: qué ficheros cambian de verdad, cuáles no y cuál cambia por un hex hardcodeado), `crossover_event_debug` (primera divergencia entre el log de entrega correcto y el desplegado + delta de inventario en B).
- Registro: `registry.py` (+2 módulos, +5 familias), `dispatch.py` (+3 task types), `schemas/understand.schema.json` (+3 enums).
- `scripts/build_opus_delta.py`: batch media 005 (write) + game 004 (write) + media 005 / game 003 (understand) con cuotas explícitas; SEED_BASE 20260301.
- 39.336 staged → **20.610 publicados** (write 13.697 · understand 3.374 · media 1.310 · game 2.229). Extensión publicada: 622 records (media write 230 · game write 178 · media understand 131 · game understand 83). 557 records llevan el literal `#39C5BB`. Tests 13/13; smoke FAIL=0 en las 61 familias; make_buggy de las 5 familias nuevas falla determinista (21-24/24 seeds).

## [0.3.0] — Extensión Universal Modder (metodología de modding verificable)

### Añadido
- **Extensión Universal Modder** en Dataset 4, inspirada en la metodología pública de [universal-modder](https://github.com/rehan-remade/universal-modder) (rehan_shei, sep 2026: recon → lab seguro → leer el código real → slice vertical → oracle → publicar → field note). Código 100% original, objetivos 100% sintéticos. 4 familias write nuevas (`generators/game/modding_families.py`):
  - `game_engine_recon` (115 records): fingerprinting de installs sintéticos por magias/markers (GDPC, UnityFS, pak 0x5A6F12E1, XNB+FNA, FORM, jars, par IL2CPP) + loaders (bepinex/ue4ss/tmodloader/fabric/smapi) + anti-cheat + strings online → escalera de rutas `refuse-online > loader-api > data > managed-patch > native-hook`.
  - `game_save_backup` (83): snapshot/diff/restore de saves con claims sha256 por operación y restauración que rechaza diffs stale (modelo `um backup`).
  - `game_publish_lint` (77): lint pre-release de paquetes de mods — FAIL por game file byte-idéntico (hash), `.env` y claves filtradas (sk-/ghp_/AKIA); WARN por artefactos de decompilador (FUN_/DAT_/sub_), rutas absolutas y README ausente (modelo `um publish check`).
  - `game_oracle_replay` (83): oracle trace-replay con semántica f32 cuantizada (`q32`), input polled después de física (acción en t surte efecto en t+1) y buff oculto plantado; el comparador fija `first_divergence` en orden fijo de variables.
- 3 builders understand nuevos (`generators/understand/modding.py`): `mod_route_selection` (decisión de ruta con reglas duras: la respuesta correcta ante anti-cheat+online es NEGARSE y ofrecer offline/official tools), `mod_oracle_gotcha` (síntoma→causa→fix de oracles rotos: capture congelado con SHA idénticos y CPU quemando, oracle de frame t/t+1, fake-host sobreestimado, sweep dorado que no puede fallar, screenshots no leídos) y `mod_evidence_levels` (etiquetado creator_report < design < source_inspection < derived_comparison < synthetic_test < real_run + trampas que parecen prueba sin serlo).
- `scripts/build_modding_delta.py` (batch 005/002 con cuotas explícitas) + registro de las familias en `registry.py`/`dispatch.py` y de los 3 nuevos `task_type` en `schemas/understand.schema.json`.
- Reglas de seguridad entrenadas DENTRO del ground truth: `refuse-online` es la respuesta correcta del dataset, redistribuir game files/decompilados es FAIL del lint, y "funciona" sin run real se penaliza en los niveles de evidencia.

### Decisiones de calidad
- 38.712 staged → **19.988 publicados** (write 13.697 · understand 3.374 · media 949 · game 1.968). La extensión aportó 644 staged → 489 publicados (358 write + 131 understand); el dedup normalizado eliminó los duplicados semánticos de los builders de baja entropía de escenario (retención 44-75% según familia).
- Corregidos durante el desarrollo: primer frame de divergencia del replay (el buff activo DURANTE el update hace diverger x y vx en el mismo frame → el orden fijo de variables decide el pin), escenario de backup donde remove se tragaba el change op, y reintentos en make_buggy para escenarios donde el bug no dispara (paquetes limpios en lint, muestras sin ruta data en recon).

## [0.2.0] — Extensión MV + corrección de dedup

### Añadido
- **Extensión MV (motor de vídeo musical generativo)** en Dataset 3, inspirada en la arquitectura conceptual de pdoom-video (código 100% original): 3 familias nuevas — `media_mv_scene_engine` (ventanas de escena end-exclusive, beat grid BPM→frames con desempate determinista, rampa de calor de la señal), `media_mv_karaoke` (estado de palabra activa con gaps explícitos, tipografía karaoke renderizada con Pillow) y `media_mv_project` (proyecto multi-file: paleta + timeline + karaoke + renderer puro + `render_all()` offline con manifest sha256 y tests de determinismo).
- **El color de señal por defecto de todas las familias MV es el turquesa Miku `#39C5BB`** (identidad visual de AI-ku; nunca naranja). 148 records publicados llevan el literal de color en su código; todos los proyectos MV lo usan.
- Builders understand MV con evidencia ejecutada: variante de depuración de determinismo en el render path (RNG global sin semilla → dos renders difieren → corrección verificada) y etapas de razonamiento `mv_timeline`/`mv_karaoke` con salidas observadas en sandbox.
- `scripts/build_mv_delta.py`: build delta con cuotas explícitas por familia reutilizando los workers del pipeline (verify + quality gates + formato de record).

### Corregido
- **`validators/dedup.py`**: `normalize()` colapsaba whitespace ANTES de strippear comentarios; al quedar todo el texto en una línea, `#[^\n]*` devoraba desde el primer `#` (incluidos literales hex como `'#39C5BB'` dentro de strings) hasta el final del blob completo, over-colapsando records distintos. Ahora los comentarios se strippean sobre el texto multi-línea original. Impacto medido: +3.739 records legítimamente distintos recuperados en el pilot (write 10.704→13.697, game 1.441→1.479, understand 3.043→3.374).
- **`scripts/finalize.py`**: los shards de `hard_holdout` compartían prefijo entre write y understand del mismo dataset (media/game), por lo que el segundo grupo BORRABA los shards del primero (7 records game-understand perdidos). Ahora el prefijo se califica por kind.
- **`scripts/make_stats.py`**: los records de hard_holdout se atribuían por prefijo de nombre de fichero (compartido entre kinds) → doble conteo (game_understand inflado 618→806). Ahora se atribuyen por los campos `(dataset, kind)` del propio record.

### Decisiones de calidad
- 38.068 staged → **19.499 publicados** (write 13.697 · understand 3.374 · media 949 · game 1.479): el dedup normalizado elimina duplicados semánticos; la retención MV tras parametrizar las familias (mid de rampa, tonos ember, letras/timings karaoke, jitter, dimensiones) fue del 59–77%.

## [0.1.0] — Piloto verificado

### Añadido
- Pipeline reproducible GENERAR → EJECUTAR → COMPROBAR → FILTRAR → CONSERVAR con reanudación por lotes (`scripts/build_dataset.py`).
- 49 familias generadoras en 14 lenguajes + banco multilingüe de 13 problemas (py/cpp/c/js/ts/bash) con CLI shims para equivalencia cruzada.
- Ejecutores con sandbox (rlimits): python, c (gcc), cpp (g++), js (node), ts (type-stripping), sql (sqlite), bash, validación estructural (html/css/powershell/glsl/genérico para lenguajes sin toolchain).
- Dataset 1 `write` (10.704 verificados) y Dataset 2 `understand` (3.043) con 14 tipos de tarea: debugging con prueba real de fallo/corrección, trazas verificadas por ejecución, traducción con equivalencia entre lenguajes, optimización con evidencia de tiempo, testing con puntuación de mutación, seguridad con demostración controlada, predicción de fallos con comportamiento observado, revisión, complejidad, refactor, comparación, arquitectura y selección de lenguaje.
- Dataset 3 `media` (545): timeline/easing, render determinista con Pillow (frames comparados byte a byte), análisis audio→datos→visual (envolventes, onsets, BPM→frames), lógica TS, shaders GLSL (estático), proyecto multi-file.
- Dataset 4 `game_engineering` (1.441): formatos binarios sintéticos con round-trip, saves TLV+crc32, atlas de sprites, conversión de coordenadas/cuaterniones, VM de scripting (assembler+intérprete), buses de eventos para modding con gates semver, proyecto de interoperabilidad entre motores; tareas de análisis con protocolo hipótesis→test→evidencia→conclusión.
- Deduplicación exacta + normalizada (identificadores posicionales), splits agrupados por (familia, variante), hard holdout experto, quarantine.
- Esquemas JSON, suite pytest (13 tests), Makefile, CI (GitHub Actions), estadísticas y quality report automáticos.

### Decisiones de calidad
- 37.482 generados → 15.733 publicados: los duplicados semánticos (familias con espacios de parámetros pequeños) se eliminaron en lugar de inflar el volumen.
- Lenguajes sin toolchain en el sandbox quedan en `static_check` y no cuentan como verificados por ejecución.
