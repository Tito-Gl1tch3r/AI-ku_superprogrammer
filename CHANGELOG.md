# CHANGELOG

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
