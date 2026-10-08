# QUALITY REPORT — AI-ku_superprogrammer

> Generado automáticamente por `scripts/make_quality_report.py`. Todas las cifras
> provienen de ejecuciones reales del pipeline (nada está inventado).

## 1. Resumen ejecutivo

- **write**: 13,697 ejemplos publicados; 74.1% verificados por ejecución/compilación real, 25.9% verificación estructural (lenguajes sin toolchain local).
- **understand**: 3,374 ejemplos publicados; 83.7% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **media_write**: 647 ejemplos publicados; 98.5% verificados por ejecución/compilación real, 1.5% verificación estructural (lenguajes sin toolchain local).
- **media_understand**: 302 ejemplos publicados; 84.8% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **game_write**: 1,219 ejemplos publicados; 100.0% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **game_understand**: 749 ejemplos publicados; 91.7% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).

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

- staged → kept: 1,780 → **749**
- duplicados eliminados (exacto+normalizado): 1,031
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 639, "validation": 15, "test": 88, "hard_holdout": 7}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_game_engineering|write

- staged → kept: 1,964 → **1,219**
- duplicados eliminados (exacto+normalizado): 745
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 813, "validation": 181, "test": 26, "hard_holdout": 199}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_media|understand

- staged → kept: 846 → **302**
- duplicados eliminados (exacto+normalizado): 544
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 171, "validation": 2, "test": 129, "hard_holdout": 0}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_media|write

- staged → kept: 2,589 → **647**
- duplicados eliminados (exacto+normalizado): 1,942
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 562, "validation": 20, "test": 62, "hard_holdout": 3}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_understand|understand

- staged → kept: 7,948 → **3,374**
- duplicados eliminados (exacto+normalizado): 4,483
- recortados por family cap: 0
- rechazados por schema: 91
- splits: {"train": 2890, "validation": 175, "test": 261, "hard_holdout": 48}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_write|write

- staged → kept: 23,585 → **13,697**
- duplicados eliminados (exacto+normalizado): 9,888
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 10846, "validation": 915, "test": 1245, "hard_holdout": 691}
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
