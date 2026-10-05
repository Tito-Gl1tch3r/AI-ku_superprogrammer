# DATASET CARD — AI-ku_superprogrammer (v0.1.0)

## Identificación

- **Nombre**: AI-ku_superprogrammer
- **Versión**: 0.1.0 (piloto verificado)
- **Licencia**: MIT
- **Datasets incluidos**: `AI-ku_superprogrammer_write`, `AI-ku_superprogrammer_understand`, `AI-ku_superprogrammer_media`, `AI-ku_superprogrammer_game_engineering`
- **Propósito**: entrenar capacidades de programación profunda (escritura, comprensión, depuración, verificación, optimización), generación de medios por código e ingeniería de software de juegos con ingeniería inversa autorizada.

## Composición (v0.1.0)

| Dataset | Total | % verificado por ejecución | % con tests | % multi-file |
|---|---|---|---|---|
| write | 10.704 | 72.0% | 71.8% | 19.1% |
| understand | 3.043 | 86.3% | 53.1% | 0% |
| media (write+understand) | 545 | 93.2% | 92.3% | ~1% |
| game_engineering (write+understand) | 1.441 | 96.8% | 84.9% | ~30% |
| **Total** | **15.733** | | | |

- Dificultad: beginner/intermediate/advanced/expert con hard holdout experto separado.
- Procedencia: 100% sintético (generado por las familias de este repo, semilla registrada por ejemplo).
- Idioma del contenido: inglés.

## Proceso de generación

Familias parametrizadas deterministas → ejecución/compilación en sandbox (rlimits) → gates de calidad → dedup exacto+normalizado → splits agrupados por (familia, variante) → shards .jsonl.gz. Los intentos fallidos van a `datasets/_quarantine/` y jamás entrenan sin validación manual.

## Verificación por protocolo (Dataset 2 y extensiones)

- debugging: buggy falla (traceback real) + corregido pasa.
- traducción: ejecución de ambas implementaciones con salidas comparadas.
- optimización/refactor: equivalencia sobre entradas idénticas.
- testing: puntuación de mutación real.
- seguridad: evidencia en entorno controlado (sqlite en memoria, resolución de rutas); solo patrones defensivos.
- media: frames Pillow comparados byte a byte; determinismo como requisito.
- game: round-trips pack→parse→compare sobre formatos sintéticos propios.

## Sesgos y limitaciones

1. Síntesis basada en plantillas: mitigada con diversidad de parámetros, caps por familia y dedup normalizado; varias familias quedaron por debajo del volumen objetivo tras eliminar duplicados semánticos (decisión de calidad).
2. Lenguajes sin toolchain local (java, rust, go, php, powershell, glsl): `static_check`, señalados en cada record.
3. Ground truth de explicaciones/revisions autorado junto al código; el grading automático de estas tareas es aproximado.
4. Objetivos de juego: exclusivamente sintéticos/educativos; no hay contenido de juegos comerciales.

## Usos previstos y fuera de alcance

- Pretraining/fine-tuning de modelos que razonen sobre código y sistemas computacionales.
- FUERA DE ALCANCE: evasión de protecciones, cheats, ataques a servicios reales, reproducción de assets propietarios.

## Trazabilidad

Cada record lleva `provenance` (generator, versión, seed, fecha UTC, método) y `verification` (método, toolchain, evidencia). `reports/stats.json` y `reports/finalize_summary.json` permiten auditar los números completos.
