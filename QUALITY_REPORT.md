# QUALITY REPORT — AI-ku_superprogrammer

> Generado automáticamente por `scripts/make_quality_report.py`. Todas las cifras
> provienen de ejecuciones reales del pipeline (nada está inventado).

## 1. Resumen ejecutivo

- **write**: 14,097 ejemplos publicados; 74.9% verificados por ejecución/compilación real, 25.1% verificación estructural (lenguajes sin toolchain local).
- **understand**: 3,524 ejemplos publicados; 84.0% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **media_write**: 877 ejemplos publicados; 98.9% verificados por ejecución/compilación real, 1.1% verificación estructural (lenguajes sin toolchain local).
- **media_understand**: 433 ejemplos publicados; 89.4% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **game_write**: 1,397 ejemplos publicados; 100.0% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **game_understand**: 832 ejemplos publicados; 92.5% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).

## 2. Protocolo de calidad aplicado

1. **GENERAR → EJECUTAR → COMPROBAR → FILTRAR → CONSERVAR**: ningún ejemplo se publica
   sin pasar por el validador de su lenguaje (compilador + tests reales, o verificación
   estructural cuando no existe toolchain).
2. **Quarantine**: los intentos fallidos (compilación, tests, calidad) van a
   `datasets/_quarantine/` y NUNCA entran en train/validation/test (política del proyecto).
3. **Deduplicación**: hash exacto + hash normalizado (identifiers mapeados a tokens
   posicionales) — elimina copias literales y variantes cosméticas renombradas.
4. **Familias con tope** (`family_cap`) para evitar flooding de plantillas.
5. **Splits anti-contaminación**: agrupados por `(family, variant)` — plantillas
   conceptuales enteras caen en un único split; el test nunca comparte plantilla con train.
6. **Hard holdout**: grupos `expert` seleccionados por hash se apartan en
   `datasets/hard_holdout/` y no se usan en generación ni en entrenamiento.
7. **Evidence-based answers (Dataset 2)**: los fallos, timings, equivalencias y trazas
   se observaron ejecutando código en sandbox — ver `verification.*` en cada record.

## 3. Métricas de filtrado (finalize)

### AI-ku_superprogrammer_game_engineering|understand

- staged → kept: 1,863 → **832**
- duplicados eliminados (exacto+normalizado): 1,031
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 698, "validation": 15, "test": 112, "hard_holdout": 7}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_game_engineering|write

- staged → kept: 2,142 → **1,397**
- duplicados eliminados (exacto+normalizado): 745
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 991, "validation": 181, "test": 26, "hard_holdout": 199}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_media|understand

- staged → kept: 979 → **433**
- duplicados eliminados (exacto+normalizado): 546
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 287, "validation": 9, "test": 137, "hard_holdout": 0}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_media|write

- staged → kept: 2,819 → **877**
- duplicados eliminados (exacto+normalizado): 1,942
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 792, "validation": 20, "test": 62, "hard_holdout": 3}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_understand|understand

- staged → kept: 8,145 → **3,524**
- duplicados eliminados (exacto+normalizado): 4,621
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 2957, "validation": 249, "test": 270, "hard_holdout": 48}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_write|write

- staged → kept: 24,247 → **14,097**
- duplicados eliminados (exacto+normalizado): 10,150
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 11167, "validation": 942, "test": 1293, "hard_holdout": 695}
- multi-file: 0 | con tests: 0

## 4. Cobertura de verificación por lenguaje

| lenguaje | método | notas |
|---|---|---|
| python | ejecutado (subprocess + rlimits) | tests con asserts, marcador `__TESTS_PASSED__` |
| c | gcc 14.2 -std=c11 -Wall -Wextra + ejecución | harness con assert.h |
| cpp | g++ 14.2 -std=c++17 + ejecución | harness con cassert |
| javascript | node 24 + assert | CommonJS `module.exports` |
| typescript | node 24 type-stripping | sintaxis erasable obligatoria |
| sql | sqlite en memoria | filas esperadas calculadas independientemente en Python |
| bash | bash + fixtures en sandbox cwd | stdout/exit comparados |
| html/css/powershell/go/rust/java/php | `static_check` estructural | sin toolchain en sandbox; el run full debe verificarlos con toolchains reales |

## 5. Limitaciones conocidas (honestidad ante todo)

- Síntesis basada en plantillas parametrizadas: la diversidad proviene de dominios,
  algoritmos, errores y contextos distintos; los caps por familia y la dedup
  normalizada mitigan el riesgo de variaciones cosméticas.
- Lenguajes estáticos (`go`, `rust`, `java`, `php`, `powershell`): verificación
  estructural; sus records llevan `verification.method = static_check` y NO cuentan
  como ejecutados en las métricas.
- HTML/CSS no se renderizan: la verificación es estructural (balance, atributos
  requeridos, anti-patrones).
- El grading de tareas de explicación/revisión usa ground truth autorado junto al
  código; los benchmarks de auto-evaluación lo documentan y los puntajes de mutación
  son reales.
- Los benchmarks internos (`evaluators/`) son puntos de partida; un model eval real
  requiere ejecutar el harness con las predicciones del modelo.

## 6. Estadísticas detalladas

Ver `reports/stats.md` y `reports/stats.json`.
