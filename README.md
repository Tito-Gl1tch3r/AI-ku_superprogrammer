# AI-ku_superprogrammer

[![ci](https://github.com/Tito-Gl1tch3r/AI-ku_superprogrammer/actions/workflows/ci.yml/badge.svg)](https://github.com/Tito-Gl1tch3r/AI-ku_superprogrammer/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-39C5BB.svg)](LICENSE)

**Dataset de entrenamiento de nivel profesional para AI-ku: PRIMERO entender el código, DESPUÉS escribirlo, AL FINAL crear vídeos y mezclas de juegos como Opus 5.5.**

> TL;DR: 6 datasets organizados como plan de estudios numerado (**00 comprensión de código · 01 escritura de código · 02 vídeo generativo estilo Opus · 03 mezclas de juegos y modding · 04 ingeniería inversa · 05 persistencia de objetivos · +extensión TS de vídeo end-to-end en 02/03**), pipeline **GENERAR → EJECUTAR → COMPROBAR → FILTRAR → CONSERVAR**, verificación real por compilación/ejecución, splits anti-contaminación, quarantine para todo lo no verificado. Licencia MIT. Piloto v0.8.0: **24.136 ejemplos** (22.815 publicados + 1.321 en `hard_holdout`) de ~45.000 generados acumulados (el resto: duplicados semánticos eliminados por las reglas anti-basura — ver `QUALITY_REPORT.md`; el total de intentos ya no se agrega globalmente, hueco D-5 del audit). "Verificado" se declara por método y dataset: `executed`/`compiled_and_executed` (ejecución/compilación real), `static_check` (solo estructural, lenguajes sin toolchain) y `authored_verified` (ground truth autorizado y cotejado); los porcentajes exactos por dataset están en `DATASET_CARD.md`.

---

## 1. Objetivo

AI-ku no debe aprender a "completar snippets". Este repositorio entrena la cadena completa:

```
OBJETIVO → REQUISITOS → RESTRICCIONES → ENTORNO → ELECCIÓN DE LENGUAJE
→ IMPLEMENTACIÓN → TEST → VERIFICACIÓN → CORRECCIÓN/OPTIMIZACIÓN
```

El resultado buscado: dado *"este programa falla en X"*, AI-ku debe comprender el programa, localizar el fallo, explicar la causa, corregirlo, verificar la corrección, detectar efectos secundarios y optimizar — tratando el código como un SISTEMA que se comprende, no como texto que se imita.

## 2. Plan de estudios — el orden en que AI-ku aprende

Cinco etapas, seis módulos numerados: **1º entender el código (00)** → **2º escribir código (01)** → **3º crear como Opus 5.5 (02 + 03, el tocho: vídeos generativos y mezclas de juegos)** → **4º leer lo compilado: ingeniería inversa (04)** → **5º terminar el trabajo: persistencia de objetivos (05)**. La numeración es el orden pedagógico de entrenamiento; los nombres y paths físicos de los datasets se mantienen estables por reproducibilidad. Receta completa por etapa (mezclas, replay anti-olvido, criterios de avance) en `docs/CURRICULUM.md`.

| Módulo | Dataset físico | Qué entrena | Records |
|---|---------|-------------|---------|
| **00 · Code Comprehension** — *1º entender* | `AI-ku_superprogrammer_understand` (`datasets/understand/`) | Explicación, trazas, debugging verificado, testing con mutación real, optimización, traducción, seguridad, complejidad, revisión, predicción de fallos; **bucle agéntico de auto-reparación con logs reales y auto-auditoría de evidencia** | 3.524 |
| **01 · Code Writing** — *2º escribir* | `AI-ku_superprogrammer_write` (`datasets/write/`) | Especificación → código correcto y testeado en 14 lenguajes; **bases numéricas (binario/hex/octal + permisos chmod), refactor de nivel maestro, tolerancia a fallos, property-based testing + shrinking, numéricos robustos, DST/unicode, git bisect real** | 14.097 |
| **02 · Opus 5.5 — Generative Video** — *3º crear: vídeos* | `AI-ku_superprogrammer_media` (`datasets/media/`) | Vídeo programático: timeline, easing, render determinista por frames, análisis audio→datos→visual, shaders, pipelines offline, **motor de vídeo musical generativo** (escenas + beat grid + karaoke word-synced + post-chain + render offline con manifest de hashes) | 1.310 |
| **03 · Opus 5.5 — Game Mixes & Modding** — *3º crear: mezclas de juegos* | `AI-ku_superprogrammer_game_engineering` (`datasets/game_engineering/`) | Formatos binarios sintéticos, serialización de saves, atlases, conversión de sistemas de coordenadas, VM de scripting, interoperabilidad entre motores, análisis con hipótesis→test→evidencia, **metodología universal de modding** (recon, labs seguros, oracles, publish-lint) y **puentes crossover entre dos juegos** | 2.229 |
| **04 · Reverse Engineering** — *4º leer lo compilado* | `AI-ku_superprogrammer_reverse_engineering` (`datasets/reverse_engineering/`) | RE verificable sobre **binarios ELF reales compilados en el sandbox**: parsers de cabeceras/secciones/símbolos contra `readelf`/`nm`, análisis de disassembly real de `objdump`, reimplantación black-box de transforms, diff diferencial entre builds, recuperación de strings ofuscadas; understand con evidencia 100% real (readout de disassembly, conclusiones por evidencia, selección de tool) | 1.153 |
| **05 · Agent Persistence** — *5º terminar el trabajo* | `AI-ku_superprogrammer_agent_ops` (`datasets/agent_ops/`) | Objetivos que no se abandonan: **monitorización de jobs reales** (poll del log, plan, nunca dar por bueno un solo signal), **objetivos compuestos** (sync → verificar → ISO → read-back con ISO9660 real), detección de stalls/timeouts en reloj virtual, **elevación de alcance** (juegos headless con input dual teclado+mando, pausa, rampa, persistencia) y understand: descomposición de objetivos, autopsia de transcripts que abandonan, criterios de finalización | 968 |

Cada dataset tiene splits `train/`, `validation/`, `test/` en shards `.jsonl.gz` de 2.000 records. Los ejemplos `expert` seleccionados por grupo viven aparte en `datasets/hard_holdout/` y **no** se usan en generación ni entrenamiento.

### 02 · Referencia conceptual — pdoom-video y la mente de Opus 5.5

[pdoom-video](https://github.com/mexicat/pdoom-video) se estudia como **arquitectura conceptual** (frames generados por lógica de escena, relación determinista timeline↔salida, render offline): se aprende el principio general, no el proyecto. No se copia código ni assets.

La extensión **MV (v0.2.0)** añade 3 familias que enseñan a CONSTRUIR ese tipo de vídeo desde cero con código original: `media_mv_scene_engine` (ventanas de escena end-exclusive, beat grid BPM→frames, rampa de calor de la señal), `media_mv_karaoke` (estado de palabra activa, tipografía karaoke renderizada con Pillow) y `media_mv_project` (proyecto multi-file: paleta + timeline + karaoke + renderer puro + `render_all()` offline con manifest sha256). **El color de señal por defecto en todas ellas es el turquesa Miku `#39C5BB`** — la identidad visual de AI-ku (nunca naranja).

La extensión **Opus-mind (v0.4.0)** va un paso más allá: ingeniería inversa de cómo trabaja el propio Opus 5.5 al autore vídeos así (el repo pdoom-video es de autoría Opus; ver `docs/OPUS_STYLE.md`) y conversión de esos hábitos en familias verificadas: `media_mv_post_chain` (cadena HDR exposure → bright-pass con knee suave → blur → halation turquesa → viñeta → grano → sRGB; el ORDEN es parte del look), `media_mv_line_batch` (batching 2D determinista con orden (z, seq, seg) y suelo de hairline consciente de la escala 4K) y `media_mv_shot_reads` (timing de planos por "reads" del espectador: find → understand → hold, uno en cadena, con hold final). 557 records publicados llevan ya el `#39C5BB` en su código.

### 03 · Referencia conceptual — metodología Universal Modder y crossovers

[universal-modder](https://github.com/rehan-remade/universal-modder) (rehan_shei, sep 2026) se estudia como **metodología conceptual** (recon → lab seguro → leer el código real → slice vertical → oracle → publicar → field note): se aprende el método general, no el proyecto. La extensión **v0.3.0** añade 4 familias write + 3 builders understand que enseñan la cadena completa con código 100% original sobre objetivos sintéticos:

- `game_engine_recon`: fingerprinting de installs sintéticos (magias GDPC/UnityFS/pak/XNB/FORM, loaders, anti-cheat, flags online) → escalera de rutas `refuse-online > loader-api > data > managed-patch > native-hook`.
- `game_save_backup`: snapshot/diff/restore de saves con claims sha256 y rechazo de diffs stale (el modelo `um backup`).
- `game_publish_lint`: lint pre-release (game files por hash, claves filtradas, artefactos de decompilador, rutas absolutas) con severidad FAIL/WARN.
- `game_oracle_replay`: oracle de trace-replay con semántica f32 y acciones t→t+1; el primer frame de divergencia localiza el bug (incluido el gotcha del buff oculto).
- `mod_route_selection` / `mod_oracle_gotcha` / `mod_evidence_levels`: decisión de ruta con reglas duras, cadenas síntoma→causa→fix de oracles rotos (capture congelado, sweep dorado, fake-host), y niveles de evidencia (creator_report < source_inspection < synthetic_test < real_run).

La extensión **crossover (v0.4.0)** captura el patrón de la ola 2026 de crossovers (dos juegos a la vez puenteados en tiempo real — Minecraft-in-Elden-Ring, Pokémon Emerald arena): `game_crossover_bridge` (puente determinista de eventos entre dos juegos-juguete: entrega idempotente por (chan, seq), FIFO por canal, rate limit que DIFIERE el overflow en vez de perderlo), `game_state_scan` (recon de memoria: intersección de dos snapshots little-endian para resolver la dirección viva y freeze con write verificado) y `crossover_event_debug` (primera divergencia entre logs de entrega correcto/desplegado + delta de inventario en B).

**Las reglas de seguridad del modding quedan entrenadas DENTRO del ground truth**: la ruta `refuse-online` (anti-cheat + online) es la respuesta correcta en el dataset, el lint marca como FAIL redistribuir game files/decompilados, y los niveles de evidencia penalizan declarar "funciona" sin run real. Nunca: anti-cheat, cheats online, DRM, assets propietarios.

### Límites éticos (módulo 03)

Solo objetivos **sintéticos** generados por el propio pipeline, formatos de juguete propios, superficies de modding oficialmente extensibles y patrones defensivos. **Nunca**: DRM, assets propietarios, cheats online, evasión de anti-cheat, acceso no autorizado.

### Extensión Superprogrammer (v0.5.0): el oficio de superprogramadora

Siete familias write nuevas y tres builders understand nuevas que cubren los huecos del roadmap (`docs/ROADMAP.md`), todas verificadas por ejecución real:

- **Bases numéricas** (`py_number_bases`): conversión binario/hex/octal con padding canónico, traducción simbólico↔octal de permisos chmod **incluyendo setuid/setgid/sticky**, aritmética de umask (máscara, nunca resta) y operaciones set/clear/toggle sobre palabras de permisos. El octal de Linux, pedido explícito del currículum.
- **Refactor de nivel maestro** (`py_mastery_refactor`): código pobre-but-funcionante → versión de producción; los tests inspeccionan la solución REAL con `ast` (ni mutable defaults, ni bare except, ni `+=` en bucles, ni funciones-dios). Destilado de los patrones de los mejores autores (incluido el estilo Opus de `docs/OPUS_STYLE.md`).
- **Tolerancia a fallos** (`py_fault_resilience`): backoff exponencial con factor e idempotencia exactly-once y circuit breaker closed/open/half-open, verificados contra inyección de fallos determinista (el doble-cobro y el backoff plano se detectan porque el schedule los dispara).
- **Property-based testing** (`py_property_testing`): propiedades que matan mutantes plantados (las tautologías se rechazan) y shrinking delta-debugging con criterio de minimalidad verificado.
- **Numérica robusta** (`py_numeric_robustness`): sumación de Kahan contra la batería 1e16, reparto de céntimos con pérdida cero, varianza de Welford contra cancelación catastrófica — ground truth por aritmética exacta (Fraction/statistics).
- **Trampas reales** (`py_timezones_unicode`): reuniones semanales cruzando DST con zoneinfo (la hora local se conserva, el offset UTC cambia), igualdad NFC+casefold y ordenación humana.
- **Git forense** (`py_git_forensics`): `git bisect` REAL sobre un repo sintético de 21 commits con presupuesto de 8 ejecuciones del checker (la búsqueda lineal queda fuera por presupuesto) y arqueología de repo que distingue la definición real de los re-exports.

Builders understand: `iterative_repair` (el bucle agéntico como record: borrador que falla con traceback REAL, intento de fix plausible que sigue fallando con salida REAL, y la corrección verificada), `mastery_principles` (defecto→principio→fix con comportamiento verificado) y `evidence_self_audit` (la escalera de evidencia aplicada a los claims propios: creator_report < source_inspection < derived_comparison < synthetic_test < real_run).

### Extensión Reverse Engineering (v0.6.0): el módulo 04, leer lo compilado

Nuevo dataset `AI-ku_superprogrammer_reverse_engineering` (`datasets/reverse_engineering/`), 1.153 records (write 690 al **100% verificado por ejecución** + understand 463). Todo el módulo trabaja sobre **binarios ELF reales** compilados en el propio sandbox con `gcc -nostdlib -static` y ground truth cosechado con binutils de verdad (`readelf`, `nm`, `objdump`, `strings`) — nada de pseudo-hexágonos inventados:

- **Parsers ELF** (`re_elf_parser`): cabeceras, tabla de secciones vía `.shstrtab`, segmentos de programa y tabla de símbolos vía `sh_link` — la solución compite contra una implementación de referencia independiente y ambas se cotejan con la salida real de binutils antes de aceptar el record.
- **Análisis de disassembly** (`re_disasm_analysis`): el bloque `objdump -d` REAL de funciones compiladas; contar calls, extraer immediates, targets de saltos y huella de código — ground truth parseado del dump real, no del fuente.
- **Reimplantación black-box** (`re_blackbox_reimpl`): un binario strip-eado lee stdin, aplica un transform (rolling XOR, offset-add, keystream LCG, rotación de nibbles) y escribe stdout; la suite ejecuta el binario REAL en cada probe y exige salida idéntica byte a byte.
- **Diff diferencial** (`re_version_diff`): dos builds reales que difieren en un parche mínimo (key bump, máscara XOR, drop del término posicional); clasificar qué cambia entre versiones ejecutando ambas.
- **Strings ofuscadas** (`re_strings_decode`): tablas XOR/rolling en `.rodata`; el decoder debe coincidir con lo que el binario REALMENTE imprime (stdout capturado como evidencia).
- Builders understand con evidencia real: `re_disasm_readout` (predecir el comportamiento de un helper desde su disassembly y verificar contra el stdout real capturado), `re_evidence_conclusion` (elegir la conclusión soportada por salidas reales de readelf/nm, con distractores que contradicen campos observables) y `re_tool_selection` (qué comando binutils responde cada pregunta, verificado ejecutándolo de verdad).

**Inspiración**: [morluto/rea](https://github.com/morluto/rea) ("Reverse Engineer Anything", MIT) — la idea de un agente que investiga binarios con evidencia y limitaciones explícitas en cada conclusión. Los datasets son 100% sintéticos y el código del pipeline no copia nada de REA.

### Límites éticos (módulo 04)

Solo binarios **compilados por el propio pipeline** en el sandbox (fuentes sintéticos propios), transforms y formatos de juguete, y patrones defensivos de análisis. **Nunca**: objetivos reales de terceros, DRM, malware, evasión de protecciones ni acceso no autorizado — el módulo enseña a LEER código compilado, no a saltarse barreras ajenas.

### Extensión Agent Persistence (v0.7.0): el módulo 05, objetivos que no se abandonan

Nuevo dataset `AI-ku_superprogrammer_agent_ops` (`datasets/agent_ops/`), 968 records (write 603 al **100% verificado por ejecución** + understand 365). El módulo entrena los tres fallos clásicos de un agente ante un objetivo largo — **abandonar la monitorización**, **perder el objetivo final** y **dar por terminado antes de tiempo** — con ejecución real en sandbox:

- **Monitorización real** (`ops_monitor_watchdog`): el job corre de verdad como subprocess y escribe su log; el monitor debe lanzarlo, hacer polling, parsear el PLAN y reportar `completed` SOLO con exit 0 + marcador DONE + todos los pasos del plan. El impostor de éxito (DONE con log corto), el crash a mitad y la línea FATAL se detectan y se reportan con su causa.
- **Objetivo compuesto de dos fases** (`ops_two_stage_orchestrator`): sincronizar un directorio contra un manifest sha256, VERIFICAR cada byte, y solo entonces construir la **ISO de la unidad actualizada con un escritor ISO9660 real** (Python puro, PVD "CD001", tablas de ruta, read-back con parser independiente). Si el sync falla, la ISO no se construye — la fase 1 es prerrequisito, no la meta.
- **Supervisión de progreso** (`ops_progress_supervisor`): reloj virtual sobre un stream de eventos; checkpoints con `result ok` NO son finalización, un `done` sin su `verify` queda en `unverified`, el silencio es un stall con timestamp exacto y el deadline es absoluto.
- **Elevación de alcance** (`ops_scope_elevation`): ante una spec mínima de juego, se entrega la versión completa: lógica pura separada de la entrada, UN mapa de input para teclado Y mando, pausa que congela la simulación, rampa de dificultad, persistencia de puntuación y las elevaciones de pulido declaradas por instancia (modo profundidad 3D, partículas, screen shake, combo) — todo simulado headless y determinista. Sin benchmarks: arquetipos genéricos (breaker, snake, pong, flyer, memoria, asteroids).
- Builders understand: `ops_goal_decomposition` (extraer el GRAFO completo de un objetivo compuesto y su entregable final), `ops_failure_autopsy` (diagnosticar transcripts que abandonan: clase de fallo, línea decisiva, objetivo pendiente) y `ops_done_criteria` (¿se puede dar por terminado? veredicto contra el checklist con log/exit/artefacto reales).


### Extensión vídeo end-to-end (v0.8.0): el salto TS/Remotion del módulo 02/03

El módulo 02/03 aprende ahora el oficio de vídeo **en TypeScript real** (Node
type-stripping, imports con extensión `.ts`): `media_ts_theme` (theme.ts como
única fuente de color — un hex fuera del tema es defecto, acento único
turquesa #39C5BB), `media_ts_motion_rules` (las reglas de motion como checks
ejecutables: nada de easing lineal en entradas, ninguna entrada de solo
opacidad, todo tween dentro de la composición), `media_ts_deterministic_render`
(mulberry32 con semilla por fotograma — dos renders son byte-idénticos y un
`Math.random()` se detecta), `media_ts_beat_grid` (la rejilla se MIDE del PCM
real con drift de tempo: un corte anclado al BPM nominal se sale de la
tolerancia de 3 frames), `media_render_verify` (QA sobre secuencia renderizada
de verdad con Pillow: frames vacíos, solapes, píxel fuera de paleta, corte
brusco) y `media_ts_mv_project` (proyecto TS multi-fichero experto cuyo
compose(frame) debe reproducir el stream de comandos dorado calculado por el
modelo independiente del generador; cada proyecto completo va al
`hard_holdout`). Builders understand: `video_review_verdict`, 
`video_timeline_readout` y `video_defect_locate`, con evidencia de renders y
mediciones reales. Además: los 90 records bash/sql de módulo 01 llevan ahora
`verification.fixtures` (re-verification de terceros desde el payload — hueco
D-3 del audit) y `re_understand` estrena 103 records expert en holdout (hueco
D-4).

### Corrección de evaluación (v0.7.0): splits y métricas del audit externo

- **`re_understand` ya no es 100% train**: los grupos `(family|variant)` exactos se recuperaron por join con el staging del batch 005 y se reasignaron train/validation/test con garantía de cobertura (145/143/175).
- **`re_write` gana validation** (26 records; el grupo `re_version_diff|xor_mask_tweak` permanece íntegro en holdout).
- **Política de holdout de media**: TODO record `expert` de media va a `datasets/hard_holdout` — los proyectos MV completos son el conjunto de evaluación "proyectos no vistos": media_write 3→45, media_understand 0→3.
- **El holdout preexistente no se toca**: los 695+48+199+7+36 records anteriores están byte-idénticos (verificado contra HEAD).
- **Migración de IDs**: los ids de media/game/re/ops colisionaban entre write y understand desde v0.1.0 (el contador se reiniciaba por kind); ahora hay UN espacio de ids por dataset (`media-0000001..media-001310`, etc.) en orden determinista (kind, language, family, seed).
- **Investigación de vídeo (P3)**: `docs/VIDEO_RESEARCH.md` estudia remotion-dev/skills, video-motion-craft y claude-remotion-skill como referencias de patrones para el salto TS/Remotion de v0.8.0 (paleta de señal por defecto: turquesa `#39C5BB`).

## 3. Lenguajes y cobertura

| Lenguaje | Verificación | | Lenguaje | Verificación |
|---|---|---|---|---|
| Python 3.12 | ejecución real + tests | | Bash | ejecución con fixtures |
| C (gcc 14.2, -Wall -Wextra) | compilación + ejecución | | SQL (SQLite) | filas esperadas calculadas en Python |
| C++17 (g++ 14.2) | compilación + ejecución | | HTML/CSS | validador estructural |
| JavaScript (Node 24) | ejecución + assert | | TypeScript (Node 24, type-stripping) | ejecución (sintaxis erasable) |
| GLSL ES 3.0 | validador estructural | | Java/Rust/Go/PHP/PowerShell | `static_check` (sin toolchain local; ver `configs/full.json` para el run full) |

## 4. Metodología y verificación

1. **GENERAR** — familias parametrizadas (89 familias, 15 lenguajes) con semilla registrada por ejemplo.
2. **EJECUTAR** — cada ejemplo pasa por el executor de su lenguaje en sandbox (subprocess + rlimits: CPU, memoria, tamaño de fichero, timeout).
3. **COMPROBAR** — tests con asserts; el módulo 00 (understand) añade protocolos propios:
   - *debugging*: la versión con bug DEBE fallar (se registra el traceback real) y la corregida DEBE pasar;
   - *traducción*: ambas implementaciones se ejecutan sobre las mismas entradas y se comparan salidas;
   - *optimización/refactor*: equivalencia verificada sobre entradas idénticas;
   - *testing*: puntuación de mutación real (`evaluators/mutation.py`);
   - *seguridad*: impacto demostrado en entorno controlado (sqlite en memoria, resolución de rutas) — nunca contra objetivos reales;
   - *media*: frames renderizados con Pillow y comparados byte a byte (determinismo); los builders MV añaden depuración de determinismo en el render path y razonamiento de timeline/karaoke con evidencia ejecutada;
   - *game*: round-trips pack→parse→compare sobre blobs sintéticos;
   - *agent_ops*: jobs que corren de verdad como subprocesses (poll del log, plan, impostores de éxito), sincronía + ISO9660 real con read-back, reloj virtual de stalls, y simulación headless determinista de juegos con input dual y pausa.
4. **FILTRAR** — gates de calidad (longitud mínima, tokens prohibidos, dominio/dificultad válidos) + deduplicación **exacta y normalizada** (identificadores mapeados a tokens posicionales: la variante "renombrar variables" colapsa).
5. **CONSERVAR** — solo lo verificado entra en train/val/test. Todo lo fallido va a `datasets/_quarantine/` y **nunca** entra en entrenamiento sin validación manual/reproducible.

**Nada está inventado**: cada campo `verification.*` registra lo que el sandbox observó realmente (stage, exit code, traceback, timing, checksum).

## 5. Formato

Esquemas JSON en `schemas/` (validados en el finalize). Campos principales de un record `write`:

```json
{
  "id": "write-0001234",
  "dataset": "AI-ku_superprogrammer_write",
  "kind": "write",
  "language": "python",
  "domain": "algorithms",
  "task": "...",
  "code": "...", "files": null, "tests": "...",
  "expected_behavior": "...",
  "difficulty": "advanced",
  "verification": {"method": "executed", "tests_passed": true, "toolchain": "...", "...": "..."},
  "provenance": {"source": "synthetic", "generator": "py_bank_algorithms", "seed": 123, "...": "..."},
  "license": "MIT",
  "metrics": {"code_chars": 640, "is_project": false}
}
```

Los records `understand` añaden `task_type` (14 tipos), `input.question` + `input.artifacts` (evidencia real observada) y `target.answer/code/tests/key_points/big_o` — razonamiento **resumido y estructurado** (causa → evidencia → corrección → verificación), nunca cadenas de pensamiento privadas.

## 6. Cómo descargar y cargar

```bash
git clone https://github.com/<owner>/AI-ku_superprogrammer.git
```

```python
# HuggingFace-style streaming (cada shard es JSONL.gz)
import gzip, json, glob
def rows(pattern):
    for path in sorted(glob.glob(pattern)):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)

train = rows("datasets/write/train/*.jsonl.gz")
understand = rows("datasets/understand/train/*.jsonl.gz")
media = rows("datasets/media/write/train/*.jsonl.gz")
game = rows("datasets/game_engineering/write/train/*.jsonl.gz")
```

Orden de curriculum para entrenar: **00 → 01 → 02 → 03** (etapas, mezclas con replay anti-olvido y criterios de avance en `docs/CURRICULUM.md`). Mezcla base sugerida dentro de cada etapa: 1×write, 1.5×understand, 0.5×media, 0.5×game; hard_holdout reservado para evaluación.

## 7. Cómo ejecutar validadores / tests

```bash
make smoke    # genera+verifica muestras de las 68 familias
make test     # suite pytest del pipeline (13 tests)
python3 -m generators.smoke --families py_bank_algorithms --samples 5
```

## 8. Cómo reproducir la generación

```bash
make write      BUDGET=480 BATCH=1        # stage write (usa configs/pilot.json)
make understand BUDGET=480 BATCH=1
python3 scripts/build_dataset.py --config configs/pilot.json --stage media --time-budget 240 --batch 1
python3 scripts/build_dataset.py --config configs/pilot.json --stage game_understand --time-budget 240 --batch 1
make finalize   # dedup + splits + shards (+ hard holdout)
make stats && make report
```

- Reanudable: `reports/_state_<stage>.json` guarda el progreso por clave.
- **Escalar al volumen completo**: `configs/full.json` contiene los objetivos del brief (240k write / 360k understand + media/game). El coste está dominado por la verificación (~20-25 ejemplos/s con 2 workers para write; entender §5 del quality report). Para producción multi-día: máquina con más cores + toolchains completos (go, rustc, jdk, php, pwsh) + `--workers` acorde; los shards grandes deben publicarse vía Git LFS/Releases manteniendo este repo como centro reproducible.
- Lección del piloto (documentada en `QUALITY_REPORT.md` §5): varias familias tenían espacios de parámetros menores que el volumen solicitado; el dedup normalizado eliminó esos duplicados semánticos. Para escalar, primero ampliar la diversidad de parámetros por familia (tamaños, distribuciones, variantes de algoritmo, espacios de nombres), NO relajar el dedup.

## 9. Evaluación del propio dataset

`evaluators/` incluye:
- `mutation.py`: puntúa suites de tests matando mutantes reales;
- `benchmarks.py`: constructores de benchmarks internos (fix, predict, optimize con chequeo de equivalencia, vuln-detection) sobre el `hard_holdout`;
- `metrics.py`: compile rate, test pass rate y demás métricas del pipeline.

Limitaciones honestas: el grading de explicaciones usa ground truth autorado junto al código; los benchmarks de modelo requieren ejecutar el harness con las predicciones.

## 10. Limitaciones conocidas

1. Go/Rust/Java/PHP/PowerShell verificados estructuralmente (sin toolchain en el sandbox del piloto); sus records llevan `verification.method = "static_check"` y no cuentan como ejecutados.
2. GLSL sin GPU: verificación estructural + semántica autorada.
3. HTML/CSS no se renderizan.
4. Varias familias cubren menos volumen del solicitado tras el dedup (ver §8); prioridad absoluta a calidad sobre cantidad.
5. Los módulos 02/03 alcanzan 1.310/2.229 records (write+understand) tras el dedup de calidad; la arquitectura de familias + builders ya soporta el escalado. El módulo 04 estrenó en v0.6.0 con 1.153 records, el 05 en v0.7.0 con 968 y la extensión TS de vídeo en v0.8.0 con +638 publicados en media/re (write 100% ejecutado bajo Node/CPython + understand con evidencia real).

## 11. Licencia

MIT — ver `LICENSE`. Todos los datos son sintéticos y generados por el pipeline de este repositorio.

## 12. Estructura

```
AI-ku_superprogrammer/
├── README.md · LICENSE · DATASET_CARD.md · QUALITY_REPORT.md · CHANGELOG.md
├── docs/{CURRICULUM,OPUS_STYLE,ROADMAP,VIDEO_RESEARCH}.md
├── datasets/{write,understand}/{train,validation,test}/    # core
├── datasets/{media,game_engineering,reverse_engineering,agent_ops}/{write,understand}/{train,validation,test}/
├── datasets/hard_holdout/          # evaluación experta, NO usar en entrenamiento
├── datasets/_quarantine/           # fallidos: auditoría, nunca entrenar
├── schemas/{write,understand}.schema.json
├── generators/{core,registry,smoke}.py · generators/problems/ (banco multilenguaje)
├── generators/write/ (15 lenguajes + bases/craft/verify/systems/re/ops_families) · generators/media/ (families + video + opus) · generators/game/ (families + modding + crossover)
├── generators/understand/ (34 builders de tareas)
├── validators/ (executors por lenguaje, dedup, splits, filtros, schema_check)
├── evaluators/ (mutation, benchmarks, metrics)
├── scripts/ (build_dataset, finalize, make_stats, make_quality_report, records, build_*_delta, validate_*_ext, resplit_v070, fix_ids_v070)
├── configs/{pilot,full}.json · tests/ · reports/ · .github/workflows/ci.yml
```
