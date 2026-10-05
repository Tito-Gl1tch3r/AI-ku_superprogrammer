# AI-ku_superprogrammer

**Dataset de entrenamiento de nivel profesional para AI-ku: de "escribir código" a COMPRENDER sistemas computacionales.**

> TL;DR: 4 datasets (programación · razonamiento sobre código · medios generados por código · ingeniería de juegos/RE), pipeline **GENERAR → EJECUTAR → COMPROBAR → FILTRAR → CONSERVAR**, verificación real por compilación/ejecución, splits anti-contaminación, quarantine para todo lo no verificado. Licencia MIT. Piloto v0.1.0: **15.733 ejemplos verificados** de 37.482 generados (el resto: duplicados semánticos eliminados por las reglas anti-basura — ver `QUALITY_REPORT.md`).

---

## 1. Objetivo

AI-ku no debe aprender a "completar snippets". Este repositorio entrena la cadena completa:

```
OBJETIVO → REQUISITOS → RESTRICCIONES → ENTORNO → ELECCIÓN DE LENGUAJE
→ IMPLEMENTACIÓN → TEST → VERIFICACIÓN → CORRECCIÓN/OPTIMIZACIÓN
```

El resultado buscado: dado *"este programa falla en X"*, AI-ku debe comprender el programa, localizar el fallo, explicar la causa, corregirlo, verificar la corrección, detectar efectos secundarios y optimizar — tratando el código como un SISTEMA que se comprende, no como texto que se imita.

## 2. Los cuatro datasets

| # | Dataset | Qué entrena | Records |
|---|---------|-------------|---------|
| 1 | `AI-ku_superprogrammer_write` (`datasets/write/`) | Especificación → código correcto y testeado | 10.704 |
| 2 | `AI-ku_superprogrammer_understand` (`datasets/understand/`) | Explicación, trazas, debugging verificado, testing, optimización, traducción, seguridad, complejidad, revisión, predicción de fallos | 3.043 |
| 3 | `AI-ku_superprogrammer_media` (`datasets/media/`) | Vídeo programático: timeline, easing, render determinista por frames, análisis audio→datos→visual, shaders, pipelines offline | 545 |
| 4 | `AI-ku_superprogrammer_game_engineering` (`datasets/game_engineering/`) | Formatos binarios sintéticos, serialización de saves, atlases, conversión de sistemas de coordenadas, VM de scripting, plugins/modding, interoperabilidad entre motores, análisis con hipótesis→test→evidencia | 1.441 |

Cada dataset tiene splits `train/`, `validation/`, `test/` en shards `.jsonl.gz` de 2.000 records. Los ejemplos `expert` seleccionados por grupo viven aparte en `datasets/hard_holdout/` y **no** se usan en generación ni entrenamiento.

### Referencia conceptual (Dataset 3)

[pdoom-video](https://github.com/mexicat/pdoom-video) se estudia como **arquitectura conceptual** (frames generados por lógica de escena, relación determinista timeline↔salida, render offline): se aprende el principio general, no el proyecto. No se copia código ni assets.

### Límites éticos (Dataset 4)

Solo objetivos **sintéticos** generados por el propio pipeline, formatos de juguete propios, superficies de modding oficialmente extensibles y patrones defensivos. **Nunca**: DRM, assets propietarios, cheats online, evasión de anti-cheat, acceso no autorizado.

## 3. Lenguajes y cobertura

| Lenguaje | Verificación | | Lenguaje | Verificación |
|---|---|---|---|---|
| Python 3.12 | ejecución real + tests | | Bash | ejecución con fixtures |
| C (gcc 14.2, -Wall -Wextra) | compilación + ejecución | | SQL (SQLite) | filas esperadas calculadas en Python |
| C++17 (g++ 14.2) | compilación + ejecución | | HTML/CSS | validador estructural |
| JavaScript (Node 24) | ejecución + assert | | TypeScript (Node 24, type-stripping) | ejecución (sintaxis erasable) |
| GLSL ES 3.0 | validador estructural | | Java/Rust/Go/PHP/PowerShell | `static_check` (sin toolchain local; ver `configs/full.json` para el run full) |

## 4. Metodología y verificación

1. **GENERAR** — familias parametrizadas (49 familias, 14 lenguajes) con semilla registrada por ejemplo.
2. **EJECUTAR** — cada ejemplo pasa por el executor de su lenguaje en sandbox (subprocess + rlimits: CPU, memoria, tamaño de fichero, timeout).
3. **COMPROBAR** — tests con asserts; Dataset 2 añade protocolos propios:
   - *debugging*: la versión con bug DEBE fallar (se registra el traceback real) y la corregida DEBE pasar;
   - *traducción*: ambas implementaciones se ejecutan sobre las mismas entradas y se comparan salidas;
   - *optimización/refactor*: equivalencia verificada sobre entradas idénticas;
   - *testing*: puntuación de mutación real (`evaluators/mutation.py`);
   - *seguridad*: impacto demostrado en entorno controlado (sqlite en memoria, resolución de rutas) — nunca contra objetivos reales;
   - *media*: frames renderizados con Pillow y comparados byte a byte (determinismo);
   - *game*: round-trips pack→parse→compare sobre blobs sintéticos.
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

Recomendación de mezcla para entrenamiento (ver §9): 1×write, 1.5×understand, 0.5×media, 0.5×game; curriculum beginner→expert; hard_holdout reservado para evaluación.

## 7. Cómo ejecutar validadores / tests

```bash
make smoke    # genera+verifica muestras de las 49 familias
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
5. Dataset 3/4 están en versión piloto (545/1.441 records write); la arquitectura de familias + builders ya soporta el escalado.

## 11. Licencia

MIT — ver `LICENSE`. Todos los datos son sintéticos y generados por el pipeline de este repositorio.

## 12. Estructura

```
AI-ku_superprogrammer/
├── README.md · LICENSE · DATASET_CARD.md · QUALITY_REPORT.md · CHANGELOG.md
├── datasets/{write,understand}/{train,validation,test}/    # core
├── datasets/{media,game_engineering}/{write,understand}/{train,validation,test}/
├── datasets/hard_holdout/          # evaluación experta, NO usar en entrenamiento
├── datasets/_quarantine/           # fallidos: auditoría, nunca entrenar
├── schemas/{write,understand}.schema.json
├── generators/{core,registry,smoke}.py · generators/problems/ (banco multilenguaje)
├── generators/write/ (14 lenguajes) · generators/media/ · generators/game/
├── generators/understand/ (14+ builders de tareas)
├── validators/ (executors por lenguaje, dedup, splits, filtros, schema_check)
├── evaluators/ (mutation, benchmarks, metrics)
├── scripts/ (build_dataset, finalize, make_stats, make_quality_report, records)
├── configs/{pilot,full}.json · tests/ · reports/ · .github/workflows/ci.yml
```
