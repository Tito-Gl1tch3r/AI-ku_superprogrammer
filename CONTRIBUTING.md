# Contribuir a AI-ku_superprogrammer

Gracias por el interés. Este repositorio es un dataset **100% sintético y verificado por ejecución**; la regla número uno es que **nada entra sin verificarse de verdad**. Esta guía resume cómo montar el entorno, cómo se valida cada cambio y qué disciplinas hacen que el dataset sea fiable.

## Entorno

Requisitos: Python 3.12+ (desarrollado y verificado en 3.12) y git.

```bash
python -m pip install -r requirements.txt
make test    # suite del pipeline (pytest)
make smoke   # genera+verifica muestras de TODAS las familias
```

Ambos comandos deben pasar antes de cualquier PR. `make smoke` es la prueba de vida del pipeline completo: recorre todas las familias con el mismo código GENERAR → EJECUTAR → COMPROBAR que produce los shards publicados.

## Metodología del pipeline

Todo el contenido se produce con el ciclo **GENERAR → EJECUTAR → COMPROBAR → FILTRAR → CONSERVAR**:

1. **GENERAR** — un builder sintetiza enunciado, código solution y variantes buggy (`make_buggy`).
2. **EJECUTAR** — se ejecuta de verdad: se compila, se corren los tests del fixture, se mide lo que haga falta (PCM, cProfile, semillas de `PYTHONHASHSEED`, renders reales con Pillow, merges reales de git).
3. **COMPROBAR** — la solución debe pasar sus propios tests y el buggy debe **fallarlos**; si un `make_buggy` pasa la suite, se descarta y se siembra otro defecto.
4. **FILTRAR** — dedup honesto (los duplicados se cuentan y se rechazan, nunca se fuerza la cifra), quarantine para todo lo que no verifique.
5. **CONSERVAR** — solo lo verificado se publica, con splits anti-contaminación y holdout para expertos.

## Añadir una familia nueva

Una familia vive en `generators/<área>/<familia>.py` y debe cumplir:

- **Verificación real**: define qué significa "correcto" ejecutándolo (tests que corren, código que compila, output medido). `static_check` solo se acepta para lenguajes sin toolchain en el entorno, y se declara como tal en `verification.method`.
- **make_buggy autoverificante**: cada variante buggy debe fallar la suite real antes de publicarse; el builder lo comprueba en generación, no a mano.
- **Determinismo**: semillas explícitas; si el código depende del orden de iteración de un set, pin de semilla de hash o estructura ordenada.
- **Registro honesto**: ni inflar cifras ni rebuscar para justificar un diseño; si un espacio de variantes es estrecho y colapsa bajo dedup, se publica el número real.
- **Splits**: los expertos (`expert=True`) van a `hard_holdout` según la política vigente; los grupos nuevos van por hash-bucketing.

Ejecuta `make test && make smoke` y añade la familia a la tabla de `CURRICULUM.md` y a `DATASET_CARD.md` si cambia los recuentos.

## Reglas de contenido

- **Todo sintético**: cero contenido copiado de repos, tutorials o benchmarks reales; las referencias a obras protegidas son solo categorías (p. ej. "mezclas estilo sky-rocket arena"), nunca ejemplos literales.
- **Paleta de los ejemplos media**: acento turquesa `#39C5BB`; nunca naranja por defecto.
- **Honestidad de métricas**: los tiempos y mediciones que aparecen en los records se miden en generación, no se inventan; el histórico de intentos por lote está en `reports/attempts_history.json`.

## Publicación de versiones

Los shards publicados son **append-only** (los publishers preservan ids/splits/contenido previos y lo demuestran con snapshots SHA256 por id). Cada versión actualiza `CHANGELOG.md`, `DATASET_CARD.md`, `CITATION.cff` y crea tag anotado + GitHub Release. Si tocas scripts de publicación, añade la prueba de integridad correspondiente (`verify_append_*`).

## Reportar problemas

Abre un issue con: familia/record afectado (`id` del record), qué verificaste tú mismo (comando + output) y qué esperabas. Los issues que demuestren un record no verificable se tratan como incidencia de calidad P0 y se corrigen con test de regresión.
