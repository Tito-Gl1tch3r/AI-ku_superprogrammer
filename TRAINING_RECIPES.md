# Recetas de entrenamiento — qué carpetas usar para cada objetivo

Todas las recetas de esta página se construyen **desde la versión actual del repositorio**: no hace falta volver a versiones antiguas. Los datasets viven en carpetas separadas (`datasets/<nombre>/`) y el holdout usa shards con prefijo por módulo (`write-*`, `understand-*`, `ops-*`, `media-*`, `re-*`, `game-*`), así que cada receta se define eligiendo carpetas y prefijos — sin filtrar records uno a uno.

Desde **v2.1.0** el corpus está curado: los records con código solución idéntico están limitados a 15 escenarios por split (familia × split × payload de código) y las familias stub con menos de 4 records fueron retiradas. Los módulos protegidos — **media (vídeo vía código), reverse_engineering y understand** — no se tocaron. El manifiesto completo de eliminaciones (id a id, con motivo) está en `reports/curation_v210.json`.

## Las cuatro recetas

| Receta | Carpetas de datasets | Prefijos de holdout | Publicados | Holdout (eval) | Total |
|---|---|---|---:|---:|---:|
| **A · Código + Agentic** | `write` + `understand` + `agent_ops` | `write-*`, `understand-*`, `ops-*` | **13.350** | 657 | 14.007 |
| **B · A + Ingeniería inversa** | A + `reverse_engineering` | A + `re-*` | **14.467** | 796 | 15.263 |
| **C · B + Vídeo vía código** | B + `media` | B + `media-*` | **16.374** | 964 | 17.338 |
| **D · Superprogrammer completo** | las seis carpetas | todos | **17.808** | 1.122 | 18.930 |

Desglose por dataset (v2.1.0, publicados = train+validation+test):

| Dataset | train | validation | test | publicados | holdout | total |
|---|---:|---:|---:|---:|---:|---:|
| `write` (código) | 7.505 | 958 | 831 | 9.294 | 540 | 9.834 |
| `understand` (comprensión) | 2.957 | 249 | 270 | 3.476 | 48 | 3.524 |
| `agent_ops` (agentic) | — | — | — | 580 | 69 | 649 |
| `reverse_engineering` | — | — | — | 1.117 | 139 | 1.256 |
| `media` (vídeo vía código) | — | — | — | 1.907 | 168 | 2.075 |
| `game_engineering` | — | — | — | 1.434 | 158 | 1.592 |
| **Total** | | | | **17.808** | **1.122** | **18.930** |

(Los datasets de módulo — `agent_ops`, `reverse_engineering`, `media`, `game_engineering` — reparten sus publicados entre `train/validation/test` en sus propias subcarpetas `<dataset>/<write|understand>/<split>/`; la columna publica los agrega.)

## Receta A — "Código + Agentic" (recomendación para el objetivo declarado)

Entrena la cadena completa de programador: **escribir** código verificado en 14 lenguajes (`write`), **entender** código como sistema (`understand`) y **terminar el trabajo** con disciplina agéntica (`agent_ops`). Es el subconjunto que mantenía el foco original del proyecto antes de las extensiones de vídeo/juegos, y post-curation concentra 13.350 ejemplos verificados.

```
datasets/write/            + datasets/hard_holdout/write-*.jsonl.gz
datasets/understand/       + datasets/hard_holdout/understand-*.jsonl.gz
datasets/agent_ops/        + datasets/hard_holdout/ops-*.jsonl.gz
```

Nota: los records de juego headless de la elevación de alcance viven **dentro de `agent_ops`** — la receta A no necesita la carpeta `game_engineering`. Ingeniería inversa y vídeo no están en A, pero se añaden con una línea (recetas B/C).

## Cómo cargar una receta (Python)

```python
import glob, gzip, json

RECIPE_A = ["write", "understand", "agent_ops"]           # carpetas de la tabla
HOLDOUT_PREFIX = {"write": "write-", "understand": "understand-",
                  "agent_ops": "ops-", "reverse_engineering": "re-",
                  "media": "media-", "game_engineering": "game-"}

def load_recipe(folders, include_holdout=False):
    for folder in folders:
        yield from _load(f"datasets/{folder}/**/*.jsonl.gz")
        if include_holdout:
            yield from _load(f"datasets/hard_holdout/"
                             f"{HOLDOUT_PREFIX[folder]}*.jsonl.gz")

def _load(pattern):
    for p in glob.glob(pattern, recursive=True):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            for line in fh:
                yield json.loads(line)

# entrenamiento de la receta A:
records = list(load_recipe(RECIPE_A, include_holdout=False))
# gate de evaluación de la receta A (NO entrenar con esto):
eval_a  = list(load_recipe(RECIPE_A, include_holdout=True))
```

Criterio simple y sin errores: **elige carpetas** de la tabla (no filtres records) y el prefijo de holdout se deriva automáticamente por carpeta.

## Qué esperar de cada receta

- **A**: el núcleo de programadora — specs → código correcto verificado, comprensión/depuración, y persistencia de objetivos agénticos. 13.350 ejemplos, todos con verificación real o etiquetada por método (`executed`/`static_check`/`authored_verified`, ver `DATASET_CARD.md`).
- **B**: añade leer binarios ELF reales compilados en sandbox (parsers, objdump, reimplantación black-box) — la habilidad de leer lo compilado.
- **C**: añade vídeo programático real en TypeScript (timeline, render determinista por frames, beat grid medido de PCM, MV generativo multi-fichero) — la habilidad de crear con código.
- **D**: añade ingeniería de juegos/modding (formatos binarios sintéticos, saves, VM de scripting, puentes crossover) — el curriculum completo de `docs/CURRICULUM.md`.

El holdout de cada receta es el gate de evaluación entre etapas: no lo uses para entrenar. El orden pedagógico (00→05) y las mezclas por etapa siguen en `docs/CURRICULUM.md`.
