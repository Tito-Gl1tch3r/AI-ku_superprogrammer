# DATASET CARD — AI-ku_superprogrammer (v0.4.1)

## Identificación

- **Nombre**: AI-ku_superprogrammer
- **Versión**: 0.4.1 (piloto verificado; extensiones Universal Modder + Opus-mind/crossover; v0.4.1 = reordenación curricular de la documentación, datos idénticos a 0.4.0)
- **Licencia**: MIT
- **Datasets incluidos** (numeración = orden del curriculum, ver `docs/CURRICULUM.md`): `AI-ku_superprogrammer_understand` (00 · Code Comprehension), `AI-ku_superprogrammer_write` (01 · Code Writing), `AI-ku_superprogrammer_media` (02 · Opus 5.5 Generative Video), `AI-ku_superprogrammer_game_engineering` (03 · Opus 5.5 Game Mixes & Modding)
- **Propósito**: entrenar capacidades de programación profunda (escritura, comprensión, depuración, verificación, optimización), generación de medios por código e ingeniería de software de juegos con ingeniería inversa autorizada.

## Composición (datos de v0.4.0, idénticos en v0.4.1)

| Dataset | Total | % verificado por ejecución | % con tests | % multi-file |
|---|---|---|---|---|
| write | 13.697 | 74.1% | 73.5% | 22.7% |
| understand | 3.374 | 83.7% | 47.9% | 0% |
| media (write 877 + understand 433) | 1.310 | 98.0% | 73.0% | ~8.6% (write) |
| game_engineering (write 1.397 + understand 832) | 2.229 | 98.1% | 73.6% | ~18.4% (write) |
| **Total** | **20.610** | | | |

Incluye la extensión **MV** (v0.2.0): 407 records de motor de vídeo musical generativo (escenas, beat grid, karaoke word-synced, render offline determinista) cuyo color de señal por defecto es el turquesa Miku `#39C5BB` — identidad visual de AI-ku, nunca naranja.

Incluye la extensión **Opus-mind / crossover** (v0.4.0): 622 records que convierten en tareas verificadas los hábitos de trabajo extraídos por ingeniería inversa de la autoría de Opus 5.5 (pdoom-video es de autoría Opus; guía en `docs/OPUS_STYLE.md`): cadena de post-proceso HDR con orden significativo y halation turquesa, batching 2D determinista con suelo de hairline 4K, timing de planos por "reads" del espectador, puente de eventos crossover idempotente con rate-limit que difiere, escaneo de memoria por intersección de snapshots, y razonamiento frameIdx/paleta/logs de puente. Referencias conceptuales: mexicat/pdoom-video (MIT), JohnHeibel/ClaudeAnimationBase (MIT); código 100% original.

Incluye la extensión **Universal Modder** (v0.3.0): 489 records de metodología de modding verificable (recon con escalera de rutas y regla de rechazo anti-cheat+online, backup/diff/restore de saves con claims sha256, lint de publicación FAIL/WARN, oracle de trace-replay con semántica f32 y acciones t→t+1, razonamiento de rutas/gotchas de oracles/niveles de evidencia). Referencia conceptual: universal-modder de rehan_shei; código 100% original sobre objetivos sintéticos.

- Dificultad: beginner/intermediate/advanced/expert con hard holdout experto separado.
- Procedencia: 100% sintético (generado por las familias de este repo, semilla registrada por ejemplo).
- Idioma del contenido: inglés.

## Proceso de generación

Familias parametrizadas deterministas → ejecución/compilación en sandbox (rlimits) → gates de calidad → dedup exacto+normalizado → splits agrupados por (familia, variante) → shards .jsonl.gz. Los intentos fallidos van a `datasets/_quarantine/` y jamás entrenan sin validación manual.

## Verificación por protocolo (módulo 00 y extensiones)

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
- Curriculum de entrenamiento recomendado: **00 → 01 → 02 → 03** (primero entender, después escribir, al final crear como Opus 5.5) — etapas, mezclas con replay y criterios de avance en `docs/CURRICULUM.md`.
- FUERA DE ALCANCE: evasión de protecciones, cheats, ataques a servicios reales, reproducción de assets propietarios.

## Trazabilidad

Cada record lleva `provenance` (generator, versión, seed, fecha UTC, método) y `verification` (método, toolchain, evidencia). `reports/stats.json` y `reports/finalize_summary.json` permiten auditar los números completos.
