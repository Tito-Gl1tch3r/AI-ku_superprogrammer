# Curriculum de entrenamiento — AI-ku

> El orden en que AI-ku aprende: **PRIMERO entender el código, DESPUÉS escribirlo, AL FINAL crear como Opus 5.5** (vídeos generativos y mezclas de juegos).
>
> Los nombres y paths físicos de los datasets no cambian (`AI-ku_superprogrammer_understand`, `_write`, `_media`, `_game_engineering`); la numeración 00–03 es el orden pedagógico de este curriculum y así se presenta en el README.

## Visión general

| # | Módulo | Dataset físico | Records | Etapa |
|---|--------|----------------|---------|-------|
| **00** | Code Comprehension | `AI-ku_superprogrammer_understand` | 3.374 | 1 — entender |
| **01** | Code Writing | `AI-ku_superprogrammer_write` | 13.697 | 2 — escribir |
| **02** | Opus 5.5 · Generative Video | `AI-ku_superprogrammer_media` | 1.310 | 3 — crear |
| **03** | Opus 5.5 · Game Mixes & Modding | `AI-ku_superprogrammer_game_engineering` | 2.229 | 3 — crear |

Total: **20.610 records verificados**. Los ejemplos `expert` de `datasets/hard_holdout/` quedan FUERA de las tres etapas y se reservan como gate de evaluación entre etapas.

---

## Etapa 1 — 00 · Code Comprehension (entender el código)

**Por qué va primero.** Antes de producir código, AI-ku debe saber LEERLO como un sistema: qué hace, por qué falla, qué efectos secundarios tiene y cómo se verifica. Las tareas de comprensión son más fáciles que las de producción (el contexto está dado) y construyen el vocabulario interno — trazas, invariantes, contratos de funciones — que la etapa 2 reutiliza al escribir. Es curriculum learning estándar: dominar la tarea receptiva antes que la productiva.

**Contenido** (14 task_types): explicación, trazas verificadas por ejecución, debugging (el buggy DEBE fallar y la corrección DEBE pasar, con traceback real), testing con puntuación de mutación, optimización con evidencia de tiempo, traducción entre lenguajes con equivalencia ejecutada, seguridad con demostración controlada, complejidad, revisión, predicción de fallos con comportamiento observado, refactor, comparación, arquitectura y selección de lenguaje.

**Mezcla sugerida**: 100% `understand` ( oversampling ~1.5× respecto a su tamaño natural). 1–3 épocas como punto de partida; ajustar por evaluación, no por fe.

**Criterio de avance**: evaluar con `evaluators/benchmarks.py` (fix / predict / optimize) sobre `hard_holdout`. Avanzar cuando las métricas de debugging y predicción de fallos alcancen meseta — no antes.

---

## Etapa 2 — 01 · Code Writing (escribir código)

**Por qué va segundo.** Con el vocabulario de lectura instalado, la tarea pasa de "completar snippets" a la cadena completa: OBJETIVO → REQUISITOS → RESTRICCIONES → ENTORNO → elección de lenguaje → implementación → test → verificación → corrección. El 74% de estos records fue verificado por ejecución real (compilación + tests), no por inspección.

**Contenido**: 14 lenguajes (Python, C, C++, JS, TS, Bash, SQL con verificación real; GLSL, HTML/CSS y Java/Rust/Go/PHP/PowerShell con `static_check` honesto), 22.7% proyectos multi-fichero, banco multilingüe de 13 problemas con CLI shims para equivalencia cruzada.

**Mezcla sugerida**: 70–80% `write` + 20–30% replay del módulo 00 (anti-olvido catastrófico: mezclar comprensión nueva en cada lote).

**Criterio de avance**: pass@1 y tasa de tests-verdes sobre los benchmarks write de `hard_holdout` en meseta, con especial atención a los proyectos multi-fichero (la capacidad que la etapa 3 más usa).

---

## Etapa 3 — 02 + 03 · El tocho de Opus 5.5 (crear como Opus)

**Por qué va al final.** Crear vídeos generativos y mezclas de juegos COMBINA las dos etapas anteriores: hay que leer código de motor (escenas, shaders, timelines) Y escribir escenas nuevas que encajen en una arquitectura determinista, añadiendo el conocimiento de dominio propio de cada módulo. Es la etapa más dependiente: sin las etapas 1–2, el modelo imita la forma sin entender el contrato de determinismo que la sostiene.

### 02 · Generative Video (`media`, 1.310 records)

- Motor MV: ventanas de escena end-exclusive, beat grid BPM→frames, karaoke word-synced, render offline con manifest sha256 (`media_mv_scene_engine`, `media_mv_karaoke`, `media_mv_project`).
- Hábitos extraídos por ingeniería inversa de la autoría de Opus 5.5 (ver `docs/OPUS_STYLE.md`): cadena de post con orden significativo (`media_mv_post_chain`), batching 2D determinista con suelo de hairline 4K (`media_mv_line_batch`), timing de planos por "reads" del espectador (`media_mv_shot_reads`).
- **Identidad visual**: turquesa Miku `#39C5BB` como color de señal por defecto en todo output — nunca naranja.

### 03 · Game Mixes & Modding (`game_engineering`, 2.229 records)

- Metodología universal de modding (recon → lab seguro → backup → oracle → publish-lint) con las reglas de seguridad dentro del ground truth: `refuse-online` es la respuesta correcta, redistribuir game files es FAIL, "funciona" sin run real se penaliza.
- Mezclas de juegos (crossovers): puentes de eventos deterministas entre dos juegos (`game_crossover_bridge`), recon de memoria por intersección de snapshots (`game_state_scan`), debugging de la primera divergencia (`crossover_event_debug`).

**Mezcla sugerida**: ~50% módulos 02+03 + ~30% replay de 00+01 + ~20% del otro módulo de la etapa (vídeo ↔ juegos, para reforzar la idea de MEZCLA). Los builders understand de dominio Opus (`mv_frameidx_pitfall`, `mv_palette_propagation`, `crossover_event_debug`, `mod_route_selection`, `mod_oracle_gotcha`, `mod_evidence_levels`, debug de determinismo) pueden incorporarse aquí filtrando por `provenance.generator`, aunque físicamente vivan en el dataset `understand`.

---

## Reglas generales del curriculum

1. **Replay anti-olvido en cada etapa**: ninguna etapa se entrena solo con datos nuevos; siempre se mezcla un porcentaje de etapas previas.
2. **hard_holdout nunca entrena**: es el gate de evaluación entre etapas. Si el gate no mejora, no se avanza de etapa.
3. **Filtrado por etapa posible sin re-generar**: cada record lleva `provenance.generator` y `dataset`, por lo que los lotes de cada etapa se pueden construir filtrando los shards existentes.
4. **Calidad > diversidad > cantidad**: si una etapa necesita más volumen, ampliar primero los espacios de parámetros de las familias (lección del piloto, `QUALITY_REPORT.md` §5), nunca relajar el dedup.
5. **Honestidad**: las mezclas y criterios de esta página son heurísticas de partida razonables, no afirmaciones validadas empíricamente; el arbitraje final es la evaluación sobre `hard_holdout`.

## Cómo construir los lotes de cada etapa

```python
import gzip, json, glob

def rows(pattern):
    for path in sorted(glob.glob(pattern, recursive=True)):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)

ALL = {
    "00": rows("datasets/understand/train/*.jsonl.gz"),
    "01": rows("datasets/write/train/*.jsonl.gz"),
    "02": rows("datasets/media/*/train/*.jsonl.gz"),
    "03": rows("datasets/game_engineering/*/train/*.jsonl.gz"),
}

# Ejemplo etapa 3: módulos 02+03 + los builders understand de dominio Opus
# (nombres auditados contra reports/stats.json / los propios shards)
OPUS_UNDERSTAND_GENERATORS = {
    "mv_frameidx_pitfall", "mv_palette_propagation",
    "media_mv_scene_engine", "media_mv_karaoke", "media_determinism",
    "crossover_event_debug",
    "mod_route_selection", "mod_oracle_gotcha", "mod_evidence_levels",
}

def is_opus_understand(r):
    return r["provenance"]["generator"] in OPUS_UNDERSTAND_GENERATORS
```
