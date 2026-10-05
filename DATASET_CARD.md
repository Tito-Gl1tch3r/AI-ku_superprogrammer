# DATASET CARD — AI-ku_superprogrammer (v0.2.0)

## Identificación

- **Nombre**: AI-ku_superprogrammer
- **Versión**: 0.2.0 (piloto verificado; extensión MV + fix de dedup)
- **Licencia**: MIT
- **Datasets incluidos**: `AI-ku_superprogrammer_write`, `AI-ku_superprogrammer_understand`, `AI-ku_superprogrammer_media`, `AI-ku_superprogrammer_game_engineering`
- **Propósito**: entrenar capacidades de programación profunda (escritura, comprensión, depuración, verificación, optimización), generación de medios por código e ingeniería de software de juegos con ingeniería inversa autorizada.

## Composición (v0.2.0)

| Dataset | Total | % verificado por ejecución | % con tests | % multi-file |
|---|---|---|---|---|
| write | 13.697 | 74.1% | 73.5% | 22.7% |
| understand | 3.374 | 83.7% | 47.9% | 0% |
| media (write 647 + understand 302) | 949 | 93.2% | 76.4% | ~8% |
| game_engineering (write 861 + understand 618) | 1.479 | 96.2% | 73.6% | ~20% |
| **Total** | **19.499** | | | |

Incluye la extensión **MV** (v0.2.0): 407 records de motor de vídeo musical generativo (escenas, beat grid, karaoke word-synced, render offline determinista) cuyo color de señal por defecto es el turquesa Miku `#39C5BB` — identidad visual de AI-ku, nunca naranja.

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
- media: frames Pillow comparados byte a byte; determinismo como requisito; depuración de determinismo en el render path y razonamiento de timeline/karaoke con evidencia ejecutada.
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
