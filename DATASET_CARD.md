# DATASET CARD — AI-ku_superprogrammer (v0.6.0)

## Identificación

- **Nombre**: AI-ku_superprogrammer
- **Versión**: 0.6.0 (módulo 04 Reverse Engineering: ELF reales compilados en sandbox + binutils reales; inspirado en morluto/rea, MIT)
- **Licencia**: MIT
- **Datasets incluidos** (numeración = orden del curriculum, ver `docs/CURRICULUM.md`): `AI-ku_superprogrammer_understand` (00 · Code Comprehension), `AI-ku_superprogrammer_write` (01 · Code Writing), `AI-ku_superprogrammer_media` (02 · Opus 5.5 Generative Video), `AI-ku_superprogrammer_game_engineering` (03 · Opus 5.5 Game Mixes & Modding), `AI-ku_superprogrammer_reverse_engineering` (04 · Reverse Engineering)
- **Propósito**: entrenar capacidades de programación profunda (escritura, comprensión, depuración, verificación, optimización), generación de medios por código, ingeniería de software de juegos con modding autorizado y lectura de binarios (ingeniería inversa sobre objetivos propios sintéticos).

## Composición (v0.6.0)

| Dataset | Total | % verificado por ejecución | % con tests | % multi-file |
|---|---|---|---|---|
| write | 14.097 | — | — | — |
| understand | 3.524 | — | — | 0% |
| media (write 877 + understand 433) | 1.310 | 98.0% | 73.0% | ~8.6% (write) |
| game_engineering (write 1.397 + understand 832) | 2.229 | 98.1% | 73.6% | ~18.4% (write) |
| reverse_engineering (write 690 + understand 463) | 1.153 | 59.9% (write: 100%) | 59.9% | 0% |
| **Total** | **22.313** | | | |

Incluye la extensión **Reverse Engineering** (v0.6.0, módulo 04): 1.153 records sobre **binarios ELF reales** (compilados en el sandbox con `gcc -nostdlib -static`, 1,5-9 KB, con y sin símbolos) con ground truth cosechado de binutils reales: parsers de cabecera/secciones/símbolos verificados contra `readelf`/`nm`, análisis del disassembly real de `objdump -d` (calls, immediates, jump targets, huella), reimplantación black-box de transforms byte-exacta (la suite ejecuta el binario real en cada probe), diff diferencial entre dos builds con parche mínimo, y strings ofuscadas cuya decodificación debe coincidir con el stdout real capturado. Understand con evidencia 100% real: readout de disassembly verificado por reconstrucción byte-exacta del stdout, conclusiones seleccionadas por evidencia observada y selección de comando binutils verificada ejecutándolo. **Inspirado en [morluto/rea](https://github.com/morluto/rea) (MIT)**; datasets 100% sintéticos, cero código copiado. Solo objetivos propios: sin DRM, sin malware, sin terceros.

Incluye la extensión **MV** (v0.2.0): 407 records de motor de vídeo musical generativo (escenas, beat grid, karaoke word-synced, render offline determinista) cuyo color de señal por defecto es el turquesa Miku `#39C5BB` — identidad visual de AI-ku, nunca naranja.

Incluye la extensión **Opus-mind / crossover** (v0.4.0): 622 records que convierten en tareas verificadas los hábitos de trabajo extraídos por ingeniería inversa de la autoría de Opus 5.5 (pdoom-video es de autoría Opus; guía en `docs/OPUS_STYLE.md`): cadena de post-proceso HDR con orden significativo y halation turquesa, batching 2D determinista con suelo de hairline 4K, timing de planos por "reads" del espectador, puente de eventos crossover idempotente con rate-limit que difiere, escaneo de memoria por intersección de snapshots, y razonamiento frameIdx/paleta/logs de puente. Referencias conceptuales: mexicat/pdoom-video (MIT), JohnHeibel/ClaudeAnimationBase (MIT); código 100% original.

Incluye la extensión **Superprogrammer** (v0.5.0): 7 familias write + 3 builders understand (481 records publicados tras dedup) que enseñan el oficio de superprogramadora — bases numéricas y permisos Linux (octal chmod con bits especiales), refactor de nivel maestro con gates AST, patrones de resiliencia (backoff/idempotencia/circuit breaker) contra inyección de fallos determinista, property-based testing con mutantes y shrinking, aritmética robusta (Kahan, céntimos sin pérdida, Welford), trampas DST/unicode, y `git bisect` real con presupuesto de ejecuciones — más el bucle agéntico de auto-reparación con logs 100% reales, los principios de maestría y la auto-auditoría con escalera de evidencia. Además, la reparación de un bug de metadatos del piloto (verification.method no-enum en optimize_two_sum) recuperó 69 records legítimos. Detalle: `docs/ROADMAP.md`.

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
