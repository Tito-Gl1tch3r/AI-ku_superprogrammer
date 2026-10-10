# QUALITY REPORT — AI-ku_superprogrammer

> Generado automáticamente por `scripts/make_quality_report.py`. Todas las cifras
> provienen de ejecuciones reales del pipeline (nada está inventado).

## 1. Resumen ejecutivo

- **write**: 14,097 ejemplos publicados; 74.9% verificados por ejecución/compilación real, 25.1% verificación estructural (lenguajes sin toolchain local).
- **understand**: 3,524 ejemplos publicados; 84.0% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **media_write**: 1,365 ejemplos publicados; 99.3% verificados por ejecución/compilación real, 0.7% verificación estructural (lenguajes sin toolchain local).
- **media_understand**: 710 ejemplos publicados; 54.5% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **game_write**: 1,397 ejemplos publicados; 100.0% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **game_understand**: 832 ejemplos publicados; 92.5% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **re_write**: 690 ejemplos publicados; 100.0% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **re_understand**: 566 ejemplos publicados; 0.0% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **ops_write**: 603 ejemplos publicados; 100.0% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).
- **ops_understand**: 365 ejemplos publicados; 0.0% verificados por ejecución/compilación real, 0.0% verificación estructural (lenguajes sin toolchain local).

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

### AI-ku_superprogrammer_agent_ops|understand

- staged → kept: 467 → **365**
- duplicados eliminados (exacto+normalizado): 102
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 265, "validation": 33, "test": 42, "hard_holdout": 25}
- multi-file: 0 | con tests: 0

### AI-ku_superprogrammer_agent_ops|write

- staged → kept: 642 → **603**
- duplicados eliminados (exacto+normalizado): 39
- recortados por family cap: 0
- rechazados por schema: 0
- splits: {"train": 450, "validation": 69, "test": 38, "hard_holdout": 46}
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
