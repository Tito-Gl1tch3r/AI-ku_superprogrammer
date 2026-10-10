# CHANGELOG

## [0.9.1] — CI en verde (infra) + robustez de toolchain en py_git_forensics

Sin cambios en el contenido del dataset (24.525 records, 102 familias — intactos).

### Arreglado
- **CI llevaba rojo desde 4eb54e8 (v0.7.0) sin que nadie lo viera**: el workflow iba directo a `python -m pytest` sin instalar dependencias (`No module named pytest` en el runner). Ahora `ci.yml` instala `numpy`/`Pillow`/`pytest` desde el nuevo `requirements.txt` (con caché pip) antes de la suite y el smoke. El badge del README pasa a reflejar el estado real.
- **Runner sin TS funcional**: el Node del runner no lograba inicializar el WASM de amaro (type-stripping) bajo el `RLIMIT_AS` de 1536 MB del sandbox — la reserva es del TOOLCHAIN, no del código generado. Nuevo `run_node_ts()` en `validators/executors/base.py`: ante esa firma exacta reintenta una vez con techo de address-space elevado (tests, límites CPU/FSIZE, criterios de paso y timeout IDÉNTICOS; el reintento queda registrado en `details`). Aplicado en `verify_ts`, `run_ts_snippet` y la rama TS de `run_cli_for`. Además `ci.yml` fija Node 24 (`actions/setup-node`), el mismo major que el desarrollo local.
- **`py_git_forensics` ahora es robusto a la redacción de git**: el reporte de `git bisect` varía entre builds — "is the first bad commit" (p.ej. 2.47.3) vs "is the first 'bad' commit" con el término entrecomillado (p.ej. el git de ubuntu-24.04 en el runner). El template del solution parsea ambas variantes; el bisect convergía bien, era el parsing el que no.
- **Diagnóstico de smoke**: los fallos reportan stderr completo (hasta 2000 chars; antes 300, cortaba los tracebacks a mitad de frame y hacía el rojo de CI indiagnosticable desde los logs).

### Nota de re-verificación de terceros (honestidad sobre lo publicado)
Los records `py_git_forensics` ya publicados llevan el parse de UNA sola variante y re-verifican con gits cuyo reporte NO entrecomilla el término; en gits que lo entrecomillan su replay no converge. El contenido publicado NO se toca (disciplina append-only, snapshots SHA256 por id); los records generados a partir de v0.9.1 aceptan ambas. Es la primera dependencia de versión de git que se documenta — las verificaciones `executed` son siempre relativas al toolchain que las ejecutó.

### Añadido
- `requirements.txt` (numpy>=1.26, Pillow>=10.0, pytest>=8.0) y `CONTRIBUTING.md` (metodología GENERAR→EJECUTAR→COMPROBAR→FILTRAR→CONSERVAR, requisitos de una familia nueva, reglas de contenido y de publicación).

## [0.9.0] — Cierre del roadmap "superprogramadora": P2/P4 restantes + P5/P6/P7/P10/P11 + D-5

### Añadido (7 familias write en `AI-ku_superprogrammer_write`, todas con ejecución real como fuente de verdad)
- **`git_merge_conflict` (P2-rest, cierre total)**: el conflicto lo produce un `git merge` REAL (historia de 3 commits con fechas fijadas, dos ramas editando el mismo bloque contiguo); el task muestra el fichero con los markers tal y como git los dejó. La solución debe conservar AMBAS intenciones de rama y la suite ejecuta los tests de AMBAS ramas. Bugs plantados (resolver perdiendo una intención) auto-verificados contra la suite combinada.
- **`flaky_test_forensics` (P4-rest, cierre total)**: el módulo bajo test decide empates por orden de iteración de un set → flaky REAL dependiente de `PYTHONHASHSEED`. La evidencia se MIDE ejecutando el módulo roto en 41 seeds reales (seeds que discrepan, salidas distintas — nada inventado). La solución fija el orden first-seen y la suite re-ejecuta la llamada en 5 subprocessos con seeds distintos: cualquier drift de salida FALLA. Nota de entorno: el harness de verificación fija `PYTHONHASHSEED=0`, así que la determinismo se demuestra con subprocessos propios del suite.
- **`sql_schema_migration` (P5)**: migración SQLite v1→v2 sobre datos sucios reales (timestamps ISO con Z / offset numérico / naive, montos decimales como strings, duplicados exactos y con formato alternativo, valores inválidos): canonicalización UTC, montos a cents enteros (ROUND_HALF_UP), dedup sobre el valor NORMALIZADO conservando el id menor, rejects clasificados con precedencia bad_ts > bad_amount > duplicate, backup de v1 y rollback que restaura esquema y filas BYTE-EXACTOS — todo asertado fila a fila contra la referencia del generador.
- **`sdk_docs_integration` (P6)**: SDK ficticia "pagerfeed" (ficheros: docs.md como ÚNICO contrato + implementación de referencia exacta + integrador). La suite envuelve el cliente en un guard estricto que lanza `AttributeError` ante CUALQUIER atributo no documentado (alucinar superficie = fallo), cubre paginación por cursor hasta `None`, el error documentado `ValueError("too_long")` que debe respetarse sin capturarlo, `RateLimited` con presupuesto de reintentos (el intento original cuenta) y notas justo en el borde de 280 caracteres.
- **`repo_feature_insertion` (P7, experto)**: entrar en un repo ajeno (notewrap: paquete con registro de renderers, 6 ficheros existentes) y añadir una feature POR el punto de extensión. La suite materializa el repo intacto, aplica los ficheros del candidato y exige: comportamiento nuevo exacto, regresión completa (defaults públicos intactos, KeyError con todos los nombres conocidos) y check estructural (`__module__` del renderer registrado) que rechaza el hardcoding del nombre nuevo en el dispatcher. La importación del módulo nuevo la hace la suite — el registro ocurre al importar, como en los plugins reales.
- **`profile_guided_optimization` (P10)**: el task incrusta un excerpt de cProfile REAL medido en generación (ncalls/tottime/cumtime del hotspot sobre el workload de producción) junto al tiempo medido de la versión naive. La suite exige equivalencia exacta (casos fijados + workload seeded fresco) Y una valla de wall-clock medida: un arreglo cosmético sigue corriendo a velocidad naive y FALLA la valla. Dos escenarios (pares iguales O(n²)→O(n); top-k por escaneo repetido→sort/nlargest) con bugs cosméticos auto-verificados.
- **`doctest_authoring` (P11)**: documentar módulos con ejemplos doctest cuyas salidas se MIDEN en generación (repr real del REPL, escapes preservados); la suite ejecuta `doctest.testmod` + chequeo AST de cobertura (toda función pública con al menos un ejemplo). Un docstring que promete una salida no observada FALLA — el bug plantado miente en un ejemplo y se auto-verifica.

### D-5 cerrado (hueco del audit de v0.7.0)
- `reports/attempts_history.json`: historial de intentos por lote recalculado desde los ledgers primarios (`datasets/_staging/` + `datasets/_quarantine/`, los únicos lugares donde el pipeline escribe intentos), con `scripts/build_attempts_history.py` re-ejecutable. Naturaleza de FLOOR documentada (los rebuilds completos rotaron ledgers antiguos) + estimados históricos citados con su fuente. El README ya no declara el hueco: remite al fichero.

### Números
- Batch 009: 729 attempts en staging → 353 duplicados honestos (espacios de variantes estrechos y deterministas colapsan: el conflicto git es idéntico por parámetros, el repo tiene 18 combinaciones título×kind) → **376 publicados** (train 303 · validation 16 · test 38 · hard_holdout 19 por la regla expert-hash del módulo 01). Por familia: git 21, flaky 68, sql 68, sdk 68, repo 15, profile 67, doctest 50.
- **Total: 24.525** (23.179 publicados + 1.346 `hard_holdout`). **102 familias**. pytest 30/30 (20 previos + 10 nuevos: forma de record ×7, replay de terceros desde shards, volúmenes mínimos, holdout expert); smoke ALL PASSED (102 familias); `scripts/validate_evolution_ext.py` GREEN (7/7 familias: muestras verdes + buggy-fail + determinismo de código); conteo independiente (`scripts/verify_counts_v080.py`): 0 ids duplicados, 0 solape holdout, stats == shards.
- Integridad del append: snapshot SHA256 por id antes/después (`scripts/verify_append_v090.py`) — los 14.097 records previos del módulo 01 quedaron BYTE-IDÉNTICOS, splits estables, 376 ids nuevos continuación del namespace.
- Infra: `generators/write/evolution_families.py` (7 familias), `scripts/build_evolution_delta.py` (build reanudable por conteo), `scripts/publish_py_v090.py` (append preservando ids), `scripts/verify_append_v090.py` (prueba de integridad), `tests/test_evolution_v090.py`.

## [0.8.0] — Extensión vídeo end-to-end (TS/Remotion) + cierres D-3/D-4 del audit

### Añadido
- **6 familias write de vídeo en TypeScript real** (`generators/media/ts_video_families.py`, `ts_beat_families.py`, `ts_project_family.py`; Node 24 type-stripping, imports `.ts` explícitos, TypeScript solo con tipos borranles):
  - `media_ts_theme`: theme.ts como única fuente de verdad visual (paleta/easings/fuentes); un hex crudo fuera del tema es defecto; ACCENTS con EXACTAMENTE un color — el turquesa Miku #39C5BB, nunca naranja. Variante accent_sweep: la regla "un acento por frame" como barrido mecanico.
  - `media_ts_motion_rules`: las reglas de motion-craft como invariants ejecutables sobre programas de tweens (entradas sin easing lineal, ninguna entrada de solo opacidad, tweens dentro de la composición; terminar EXACTAMENTE en el último frame es legal). El ease lineal en no-entradas NO se marca.
  - `media_ts_deterministic_render`: mulberry32 re-sembrado por frame (seed + t); los golden positions los calcula el modelo del generador Y una ejecución Node real del candidato — el record se descarta si discrepan; `Math.random()` y `Date.now()` quedan demostrados por tests de determinismo y de difference entre frames.
  - `media_ts_beat_grid`: la rejilla se MIDE del PCM real (numpy: envolvente de energía, picos, mediana de intervalos) con drift de tempo; cortes anclados a la rejilla MEDIDA con error <= 3 frames; el bug plantado (cortar por el BPM nominal) se sale de tolerancia por el drift acumulado.
  - `media_render_verify` (PIL): QA sobre una secuencia renderizada de verdad — frames vacíos (todo tinta), solape de cajas, píxel fuera de paleta (el naranja prohibido), corte brusco por diff medio; variante manifest_audit (fps/total_frames/duración contra el render real). make_buggy auto-verificado.
  - `media_ts_mv_project` (experto, multi-fichero): theme + timeline (rejilla medida) + scenes puras de matemática entera + compose(frame) -> stream de comandos; los golden probes los verifica una ejecución Node real contra el modelo independiente del generador; el test ESTRUCTURAL lee los fuentes y prohibe hex fuera de theme.ts. Todo proyecto completo -> hard_holdout.
- **3 builders understand** (`generators/understand/video_builders.py`): `video_review_verdict` (veredicto de aceptación sobre un informe con frames REALES de un render defectuoso), `video_timeline_readout` (cortes/errores/anclas sobre la rejilla medida real; distractores basados en el BPM nominal) y `video_defect_locate` (localización por umbrales sobre stats reales por frame).
- `scripts/validate_video_ext.py`: GREEN — 6 familias con muestras verdes + buggy-fail + determinismo; builders con evidencia cotejada.

### Corregido (cierres D-3 y D-4 del audit de v0.7.0)
- **D-3 — re-verificación de terceros para bash/sql**: los 90 records bash/sql del módulo 01 llevan ahora `verification.fixtures` (`fixtures_origin: recaptured_v080`). Las semillas originales resultaron irrecuperables (scan de 5.8M semillas: 0 matches, documentado en `reports/fixture_recovery_v080.json`); las fixtures se RE-CAPTURARON ejecutando el código publicado sobre datos frescos de la forma correcta y capturando salidas/exit/rows reales como expectativas (respuestas SQL parametrizadas con `?` no re-ejecutables llevan sonda de setup). Tres tests de replay (`tests/test_fixtures_v080.py`) fijan la garantía: el payload publicado basta para re-verificar.
- **D-4 — holdout de re_understand**: delta expert (binarios ELF de 5-7 helpers, dificultad expert real) -> 103 records nuevos en hard_holdout; re_understand deja de tener 0 records de evaluación.
- Tests del pipeline y del smoke con presupuesto de reintentos determinista para familias con gates de generación honestos (medición de audio, harvest).

### Números
- Batch 007 (media): 612 write + 291 understand staged (+45 top-up defect_audit) -> +638 publicados tras dedup honesto (935 duplicados normalizados: las variantes cosméticas se colapsan — 24->37 render_verify, etc.). Batch 008 (re_understand expert): 103 -> 103 a holdout. **Total: 24.136** (22.815 publicados + 1.321 holdout). 95 familias. pytest 20/20 (13 base + 4 audit + 3 fixtures); smoke ALL PASSED (95 familias); validate_video_ext GREEN; `scripts/verify_counts_v080.py`: 0 ids duplicados, 0 solape holdout, stats == shards.


## [0.7.0] — Módulo 05 Agent Persistence + corrección de evaluación (audit externo)

### Añadido
- **Nuevo dataset `AI-ku_superprogrammer_agent_ops`** (`datasets/agent_ops/{write,understand}/`), módulo 05 del curriculum: 968 records (write 603 al 100% verificado por ejecución + understand 365 con evidencia cotejada) que entrenan a NO abandonar: monitorizar jobs largos hasta el final, no perder el entregable final de un objetivo compuesto y no declarar la victoria sin verificación.
- **4 familias write** (`generators/write/ops_families.py`, todas python ejecutado, bugs que fallan determinísticamente):
  - `ops_monitor_watchdog`: job subprocess REAL con log de progreso (PLAN N, steps, DONE, FATAL); el monitor hace polling y solo reporta `completed` con exit 0 + DONE + todos los pasos; detecta el impostor de éxito (DONE con log corto), crashes y FATAL con su causa.
  - `ops_two_stage_orchestrator`: objetivo compuesto real — sync contra manifest sha256 con verificación de cada byte, y SOLO entonces **ISO9660 real** (escritor en Python puro: PVD "CD001" en LBA 16, tablas de ruta L/M, registros de directorio, datos) verificada por read-back con parser independiente; un sync fallido nunca produce ISO (la fase 1 es prerrequisito, no la meta).
  - `ops_progress_supervisor`: reloj virtual sobre streams de eventos — checkpoints con result ok NO son finalización, done sin verify queda `unverified`, silencio > stall_after es stall con timestamp exacto, deadline absoluto; escenarios limpios/stall/timeout/done_error/done_no_verify/checkpoint-trap/stall-mid.
  - `ops_scope_elevation`: ante una spec mínima de juego, entrega la versión completa — lógica pura separada, UN mapa de input para teclado Y mando, pausa que congela, rampa de dificultad, persistencia de score y elevaciones declaradas por instancia (modo 3D, partículas, screen shake, combo); 6 arquetipos headless deterministas (breaker, snake, pong, flyer, memoria, asteroids). Sin benchmarks: arquetipos genéricos.
- **3 builders understand** (`generators/understand/ops_builders.py`): `ops_goal_decomposition` (grafo completo de objetivos compuestos con entregable FINAL), `ops_failure_autopsy` (clase de fallo + línea decisiva + objetivo pendiente de transcripts que abandonan: abandono de monitorización / objetivo perdido / finalización prematura) y `ops_done_criteria` (veredicto YES/NO contra checklist log/exit/artefacto). Variación estructural por seed (nº de etapas, gates, contadores de plan, estados de artefacto) para sobrevivir al dedup normalizado.
- **Validador dedicado** `scripts/validate_ops_ext.py`: GREEN — 4 familias write con muestras verdes + buggy-fail 12/12 por familia + determinismo; 3 builders con 36/36 evidencia cotejada y schema.
- **`docs/VIDEO_RESEARCH.md`**: estudio de remotion-dev/skills, video-motion-craft (Apache-2.0) y claude-remotion-skill (MIT) como referencias de patrones para el salto TS/Remotion de P3 en v0.8.0 (reglas de motion, beat-sync aceptado antes del storyboard, bucle render→inspección→fix; paleta de señal por defecto #39C5BB).

### Corregido (Prioridad 0 del audit externo)
- **Splits con cobertura garantizada**: `assign_split` pasa a asignación por grupo `(family|variant)` con coverage fix-up determinista (≥1 grupo en validation y test por dataset). `re_understand` deja de ser 100% train (145/143/175) y `re_write` gana validation (26). Los grupos exactos se recuperaron por join con el staging del batch 005 (`scripts/resplit_v070.py`); `hard_holdout` intacto.
- **Política de holdout de media**: TODO record expert de media va a `datasets/hard_holdout` — los proyectos MV completos son el conjunto "proyectos no vistos": media_write 3→45, media_understand 0→3. El holdout preexistente (695+48+199+7+36) está byte-idéntico (verificado contra HEAD).
- **IDs duplicados entre kinds (desde v0.1.0)**: el contador de finalize se reiniciaba por (dataset, kind), así que media/game/re/ops tenían ids idénticos con contenido distinto entre write y understand (2.093 colisiones). Migración determinista a UN espacio de ids por dataset (`scripts/fix_ids_v070.py`, orden kind/language/family/seed).
- **finalize unificado**: la lógica de splits vive en `validators/splits.py` (hash + coverage fix-up + política de holdout por dataset); `finalize.py` ya no duplica el hashing.
- **Métricas honestas**: README/DATASET_CARD distinguen `executed`/`compiled_and_executed` vs `static_check` vs `authored_verified` por etapa, con porcentajes exactos por dataset en la CARD (ya no se presenta un único "% verificado" agregado).

### Auditoría adversarial post-build
- Auditoría integral en copia aislada sobre d4d8b81: integridad de 23.281 records (stats == shards exactos), sweep de schema sin violaciones, 0 duplicados/near-duplicates cruzando splits, re-ejecución fresca 114/114 (write), adversarial ops 120/120 verdes + buggy-fail 120/120, render MV determinista, ISO9660 validada con parser independiente (4/4), ELF validado con parser independiente (6/6), holdout disjunto por id y hash.
- **Tests que detectan política** (`tests/test_audit_gaps.py`, 4 tests nuevos — suite 17/17): cobertura mínima de splits, política de holdout de media, rechazo de records basura por el schema-checker y honestidad del sobreconteo de ejecución en make_stats. Demostrado con fault-injection: 4 huecos plantados ahora FALLAN los tests (antes pasaban en verde).
- **Reproducibilidad del re-split**: `reports/re_group_map.json` (1.225 grupos exactos por generator|seed) comprometido + fallback en `scripts/resplit_v070.py` — el re-split ya no depende del staging gitignored y es reproducible desde un clon fresco (splits content-idénticos verificados).
- `docs/VIDEO_RESEARCH.md`: pdoom-video promovido a fuente primaria para v0.8.0.
- Documentado para v0.7.1/v0.8.0 (sin migrar): fixtures bash/sql no publicadas (re-verificación de terceros), holdout expert de re_understand (0 experts hoy), total acumulado de intentos.

### Números
- 1.577 intentos nuevos → 1.109 staged (write 642 + understand 467; la primera pasada de understand se descartó por baja distintividad y se regeneró) → **968 publicados** en agent_ops (write 603: 39 dedup; understand 365: 102 dedup) → **23.281 total** (22.177 publicados + 1.104 holdout). 89 familias, 15 lenguajes. Tests 17/17 (13 + 4 de auditoría); smoke ALL PASSED (todas las familias); `scripts/validate_ops_ext.py` GREEN.

## [0.6.0] — Módulo 04 Reverse Engineering (ELF reales, binutils reales; inspirado en morluto/rea)

### Añadido
- **Nuevo dataset `AI-ku_superprogrammer_reverse_engineering`** (`datasets/reverse_engineering/{write,understand}/`), módulo 04 del curriculum: 1.153 records (write 690 + understand 463) sobre **binarios ELF x86-64 reales** compilados en el sandbox (`gcc -nostdlib -static`, build-id none, con/sin strip) con ground truth cosechado de binutils reales (readelf/nm/objdump/strings) y doble implementación (referencia vs solución) cotejada antes de aceptar cada record.
- **5 familias write** (`generators/write/re_families.py`, todas python ejecutado, bugs que fallan determinísticamente):
  - `re_elf_parser`: cabeceras ELF64, tabla de secciones vía .shstrtab, segmentos de programa y símbolos vía sh_link; la salida se valida contra readelf/nm reales.
  - `re_disasm_analysis`: bloques `objdump -d` reales; calls (desde _start), immediates, jump targets y huella de código.
  - `re_blackbox_reimpl`: transforms (rolling XOR, offset-add, keystream LCG, nibble rotation) reimplantados byte-exacto; la suite ejecuta el binario real en cada probe.
  - `re_version_diff`: dos builds reales con un parche mínimo (key bump, máscara XOR, drop del término posicional); modelo diferencial de ambos.
  - `re_strings_decode`: tablas XOR/rolling en .rodata; el decoder debe coincidir con el stdout REAL capturado del binario.
- **3 builders understand** (`generators/understand/re_builders.py`, evidencia 100% real): `re_disasm_readout` (respuesta verificada por reconstrucción byte-exacta del stdout real desde el modelo por-helper), `re_evidence_conclusion` (una conclusión soportada por salidas reales de readelf/nm; distractores que contradicen campos observables) y `re_tool_selection` (comando binutils correcto, verificado ejecutándolo contra el binario).
- Registro: `registry.py` (+1 módulo, +5 familias, DATASET_FAMILIES), `dispatch.py` (+3 builders), `records.py` (+dataset, prefix `re`), `finalize.py` (dir `reverse_engineering/` con shards prefijados `re-`), schemas write/understand (+dataset y +3 task_types), `make_stats.py` (+re_write/re_understand).
- `scripts/build_re_delta.py` (batch 005, SEED_BASE 20260701) y `scripts/validate_re_ext.py` (12 seeds/familia: muestras verdes, buggy siempre falla, determinismo de code+tests — el binario embebido incluido; builders con evidencia real y schema).

### Decisiones de calidad
- 1.225 staged → **1.153 publicados** (write 690: 71 duplicados normalizados eliminados con honestidad; understand 463). write al **100% verificado por ejecución**; 36 records expert del módulo a `hard_holdout` (total holdout: 988). Todos los binarios son objetivos sintéticos propios: sin DRM, sin malware, sin terceros (límites éticos del módulo en el README).

## [0.5.0] — Extensión Superprogrammer (bases/permisos, oficio de maestría, git forense)

### Añadido
- **7 familias write nuevas** (todas python, ejecución real, bugs que fallan determinista; módulos 00/01 del curriculum):
  - `py_number_bases` (`generators/write/bases_families.py`): conversión binario/hex/octal con padding canónico y prefijos, traducción chmod simbólico↔octal con setuid/setgid/sticky ('s'/'t' implican exec, 'S'/'T' no), umask como máscara (`base & ~umask`, nunca resta) y operaciones set/clear/toggle sobre palabras de permisos de 12 bits.
  - `py_mastery_refactor` (`generators/write/craft_families.py`): 4 clases de defecto (mutable default, bare except, `+=` en bucle, función-dios) con tests que inspeccionan la solución REAL vía `ast` — el smell debe desaparecer ESTRUCTURALMENTE y el comportamiento debe sobrevivir; totalmente parametrizado (nombres, separadores, fallbacks, dominios).
  - `py_fault_resilience` (ídem): backoff exponencial con factor 2/3, idempotencia exactly-once con retry único para fallos transitorios, circuit breaker closed/open/half-open con reset de racha por éxito; inyección de fallos determinista — el doble-cobro, el backoff plano y el breaker que nunca abre quedan demostrados por el schedule.
  - `py_property_testing` (`generators/write/verify_families.py`): diseño de propiedades EXACTAS (subsecuencia + igualdad de conjunto + orden de primera ocurrencia) que matan 4 mutantes plantados; las tautologías se rechazan por supervivencia de mutantes; shrinking ddmin con minimalidad verificada (todo elemento es necesario).
  - `py_numeric_robustness` (ídem): Kahan contra la batería `[1e16] + [1.0]*10000 + [-1e16]` (naive `+=` da 0.0), reparto de céntimos largest-remainder con pérdida cero, varianza de Welford contra cancelación catastrófica; ground truth por aritmética exacta (Fraction) y `statistics`. La batería de discriminación se comprueba EN la generación (si el naive no falla, el escenario se regenera).
  - `py_timezones_unicode` (`generators/write/systems_families.py`): recurrencia semanal por reloj LOCAL cruzando DST con zoneinfo (el offset UTC cambia, la hora local no; la batería exige ≥2 offsets locales), igualdad NFC+casefold (compuestos/descompuestos, ß/ss, sigma, ligaduras) y ordenación humana estable.
  - `py_git_forensics` (ídem): `git bisect` REAL vía subprocess sobre un repo sintético de 21 commits con fechas deterministas; presupuesto de ≤8 ejecuciones del checker (la búsqueda lineal no cabe); reset verificado a HEAD; arqueología de repo que distingue definiciones (class/def/assign) de re-exports y usos.
- **3 builders understand nuevos** (`generators/understand/superprogrammer.py`): `iterative_repair` (bucle agéntico multi-turno: draft con traceback REAL, fix plausible que sigue fallando con salida REAL, corrección verificada), `mastery_principles` (defecto→principio→reescribir, comportamiento verificado con sonda real) y `evidence_self_audit` (escalera creator_report < source_inspection < derived_comparison < synthetic_test < real_run aplicada a los claims propios; los logs real_run se producen en el sandbox en el momento de generar).
- Registro: `registry.py` (+4 módulos, +7 familias), `dispatch.py` (+3 builders), `schemas/understand.schema.json` (+3 enums). Validación: `scripts/validate_superprogrammer_ext.py` (16 seeds por familia: muestras verdes, bugs que fallan siempre, determinismo; builders con evidencia real).
- `scripts/build_superprogrammer_delta.py`: batch 004 write/understand con cuotas explícitas; SEED_BASE 20260601.

### Corregido
- **Bug de metadatos del piloto (v0.1.0)**: los records `optimize_two_sum` llevaban `verification.method = "identical inputs, both executed"` (texto libre fuera del enum del schema), por lo que 91 records legítimos se rechazaban en cada finalize. Reparados en staging (method=executed + nota de equivalencia) y el builder ya no usa la clave reservada `method` en verify_notes. Neto: +69 records recuperados (22 eran duplicados normalizados de records ya conservados).

### Decisiones de calidad
- 40.195 staged → **21.160 publicados** (write 14.097 · understand 3.524 · media 1.310 · game 2.229). La extensión aportó 859 staged → 481 publicados (write 400: 71-121 por familia; understand 81) — el dedup normalizado eliminó las variantes de espacio paramétrico pequeño con honestidad. 68 familias; los 557 records con `#39C5BB` intactos.

## [Unreleased] — Docs

- Nuevo `docs/ROADMAP.md`: 12 propuestas priorizadas de capacidades NUEVAS para AI-ku ("Superprogramadora") que no cubren las 61 familias actuales, auditadas contra el registro real — cada una con esquema de verificación concreto para el pipeline (P1 bucle agéntico multi-turno, P2 git/bisect/conflictos, P3 property-based testing + shrinking, P4 fault injection, P5 migraciones de esquema, P6 integración contra docs de API ficticia, P7 features a escala de repo, P8/P9 trampas numéricas/i18n, P10 optimización por perfil real, P11 doctests, P12 auto-auditoría con niveles de evidencia). Sin cambios de datos.

## [0.4.1] — Reordenación curricular (solo documentación, cero cambios de datos)

- **README reestructurado como plan de estudios numerado** en el orden en que AI-ku aprende: **00 · Code Comprehension** (1º entender el código) → **01 · Code Writing** (2º escribir código) → **02 · Opus 5.5 Generative Video** + **03 · Opus 5.5 Game Mixes & Modding** (3º, el tocho: crear vídeos y mezclas de juegos como Opus 5.5). Las secciones de referencia conceptual (pdoom-video / Opus-mind, Universal Modder / crossovers) quedan anidadas bajo sus módulos 02 y 03.
- **Nuevo `docs/CURRICULUM.md`**: etapas con justificación pedagógica del orden, contenido por módulo, mezclas de entrenamiento con replay anti-olvido, criterios de avance vía `hard_holdout`, y snippet funcional para construir los lotes de cada etapa filtrando shards por `dataset` + `provenance.generator` (nombres de generator auditados contra los shards reales).
- **Corregido**: la tabla de datasets del README arrastraba los counts de v0.3.0 (media 949 / game 1.968); ahora muestra los reales de v0.4.0 (media 1.310 / game 2.229), cuadrados con `reports/stats.json` y la DATASET_CARD. Referencias internas "Dataset 2/3/4" sustituidas por la numeración de módulos.
- Sin cambios en shards, hashes ni stats: los nombres y paths físicos de los datasets se mantienen estables por reproducibilidad; la numeración 00–03 es el orden pedagógico de presentación y entrenamiento.

## [0.4.0] — Extensión Opus-mind / crossover (ingeniería inversa de la autoría de Opus 5.5)

- **Nueva referencia**: se documenta en `docs/OPUS_STYLE.md` la ingeniería inversa de cómo trabaja Opus 5.5 al construir vídeos generativos y mods crossover: el propio `mexicat/pdoom-video` (MIT) es de autoría Opus (su `docs/ENGINE.md` es la guía operativa de agentes de escena: determinismo como contrato, paleta centralizada C_*/LIN.*/rgba(), LineBatch, cadena de post, píxeles lógicos vs físicos en 4K, etiqueta multi-agente), junto con la guía de animación de `JohnHeibel/ClaudeAnimationBase` (MIT: modelo de "reads", storyboard primero, principios de animación anti-código-mecánico) y la ola 2026 de crossovers (decompilar 2 juegos + puente en tiempo real).
- **5 familias write nuevas** (todas python, verificación real, bugs que fallan determinista):
  - `media_mv_post_chain` (`generators/media/opus_families.py`): cadena HDR exposure → bright-pass con knee suave → box blur separable → halation con tinte turquesa → viñeta → grano LCG → sRGB; bugs: blur antes del bright-pass (halo sobre todo), hard-clip del knee, grano tras cuantizar (no-op).
  - `media_mv_line_batch`: batching 2D determinista con orden total (z, seq, seg), manifest sha256 del lote ordenado y suelo de hairline en píxeles FÍSICOS (`HAIRLINE_PX / SCALE`); bugs: clave sin seq (interleave entre líneas con mismo z), suelo lógico constante (líneas 4K gordas).
  - `media_mv_shot_reads`: timing de planos desde "reads" del espectador (find → understand → hold, estrictamente secuenciales, hold final obligatorio, anticipación opcional); bugs: soltar el hold final, anticipación que solapa.
  - `game_crossover_bridge` (`generators/game/crossover_families.py`): puente determinista de eventos entre dos juegos-juguete — entrega idempotente por (chan, seq), FIFO por canal, rate limit que DIFIERE el overflow (nunca lo pierde); bugs: sin idempotencia (doble entrega), cola diferida nunca drenada, drenado global por seq (reordena canales).
  - `game_state_scan`: recon de memoria — scan little-endian de 4 bytes, intersección de dos snapshots para resolver la dirección viva (los decoys estáticos caen por el cambio), freeze con hash del imagen parcheada; bugs: unión en vez de intersección, write big-endian.
- **3 builders understand nuevos** (`generators/understand/opus.py`, evidencia real recalculada): `mv_frameidx_pitfall` (por qué `floor(t*60)` doble-expone dos estados dentro del shutter de un frame y `frameIdx(t)` no), `mv_palette_propagation` (radio de blast de un cambio en palette.ts: qué ficheros cambian de verdad, cuáles no y cuál cambia por un hex hardcodeado), `crossover_event_debug` (primera divergencia entre el log de entrega correcto y el desplegado + delta de inventario en B).
- Registro: `registry.py` (+2 módulos, +5 familias), `dispatch.py` (+3 task types), `schemas/understand.schema.json` (+3 enums).
- `scripts/build_opus_delta.py`: batch media 005 (write) + game 004 (write) + media 005 / game 003 (understand) con cuotas explícitas; SEED_BASE 20260301.
- 39.336 staged → **20.610 publicados** (write 13.697 · understand 3.374 · media 1.310 · game 2.229). Extensión publicada: 622 records (media write 230 · game write 178 · media understand 131 · game understand 83). 557 records llevan el literal `#39C5BB`. Tests 13/13; smoke FAIL=0 en las 61 familias; make_buggy de las 5 familias nuevas falla determinista (21-24/24 seeds).

## [0.3.0] — Extensión Universal Modder (metodología de modding verificable)

### Añadido
- **Extensión Universal Modder** en Dataset 4, inspirada en la metodología pública de [universal-modder](https://github.com/rehan-remade/universal-modder) (rehan_shei, sep 2026: recon → lab seguro → leer el código real → slice vertical → oracle → publicar → field note). Código 100% original, objetivos 100% sintéticos. 4 familias write nuevas (`generators/game/modding_families.py`):
  - `game_engine_recon` (115 records): fingerprinting de installs sintéticos por magias/markers (GDPC, UnityFS, pak 0x5A6F12E1, XNB+FNA, FORM, jars, par IL2CPP) + loaders (bepinex/ue4ss/tmodloader/fabric/smapi) + anti-cheat + strings online → escalera de rutas `refuse-online > loader-api > data > managed-patch > native-hook`.
  - `game_save_backup` (83): snapshot/diff/restore de saves con claims sha256 por operación y restauración que rechaza diffs stale (modelo `um backup`).
  - `game_publish_lint` (77): lint pre-release de paquetes de mods — FAIL por game file byte-idéntico (hash), `.env` y claves filtradas (sk-/ghp_/AKIA); WARN por artefactos de decompilador (FUN_/DAT_/sub_), rutas absolutas y README ausente (modelo `um publish check`).
  - `game_oracle_replay` (83): oracle trace-replay con semántica f32 cuantizada (`q32`), input polled después de física (acción en t surte efecto en t+1) y buff oculto plantado; el comparador fija `first_divergence` en orden fijo de variables.
- 3 builders understand nuevos (`generators/understand/modding.py`): `mod_route_selection` (decisión de ruta con reglas duras: la respuesta correcta ante anti-cheat+online es NEGARSE y ofrecer offline/official tools), `mod_oracle_gotcha` (síntoma→causa→fix de oracles rotos: capture congelado con SHA idénticos y CPU quemando, oracle de frame t/t+1, fake-host sobreestimado, sweep dorado que no puede fallar, screenshots no leídos) y `mod_evidence_levels` (etiquetado creator_report < design < source_inspection < derived_comparison < synthetic_test < real_run + trampas que parecen prueba sin serlo).
- `scripts/build_modding_delta.py` (batch 005/002 con cuotas explícitas) + registro de las familias en `registry.py`/`dispatch.py` y de los 3 nuevos `task_type` en `schemas/understand.schema.json`.
- Reglas de seguridad entrenadas DENTRO del ground truth: `refuse-online` es la respuesta correcta del dataset, redistribuir game files/decompilados es FAIL del lint, y "funciona" sin run real se penaliza en los niveles de evidencia.

### Decisiones de calidad
- 38.712 staged → **19.988 publicados** (write 13.697 · understand 3.374 · media 949 · game 1.968). La extensión aportó 644 staged → 489 publicados (358 write + 131 understand); el dedup normalizado eliminó los duplicados semánticos de los builders de baja entropía de escenario (retención 44-75% según familia).
- Corregidos durante el desarrollo: primer frame de divergencia del replay (el buff activo DURANTE el update hace diverger x y vx en el mismo frame → el orden fijo de variables decide el pin), escenario de backup donde remove se tragaba el change op, y reintentos en make_buggy para escenarios donde el bug no dispara (paquetes limpios en lint, muestras sin ruta data en recon).

## [0.2.0] — Extensión MV + corrección de dedup

### Añadido
- **Extensión MV (motor de vídeo musical generativo)** en Dataset 3, inspirada en la arquitectura conceptual de pdoom-video (código 100% original): 3 familias nuevas — `media_mv_scene_engine` (ventanas de escena end-exclusive, beat grid BPM→frames con desempate determinista, rampa de calor de la señal), `media_mv_karaoke` (estado de palabra activa con gaps explícitos, tipografía karaoke renderizada con Pillow) y `media_mv_project` (proyecto multi-file: paleta + timeline + karaoke + renderer puro + `render_all()` offline con manifest sha256 y tests de determinismo).
- **El color de señal por defecto de todas las familias MV es el turquesa Miku `#39C5BB`** (identidad visual de AI-ku; nunca naranja). 148 records publicados llevan el literal de color en su código; todos los proyectos MV lo usan.
- Builders understand MV con evidencia ejecutada: variante de depuración de determinismo en el render path (RNG global sin semilla → dos renders difieren → corrección verificada) y etapas de razonamiento `mv_timeline`/`mv_karaoke` con salidas observadas en sandbox.
- `scripts/build_mv_delta.py`: build delta con cuotas explícitas por familia reutilizando los workers del pipeline (verify + quality gates + formato de record).

### Corregido
- **`validators/dedup.py`**: `normalize()` colapsaba whitespace ANTES de strippear comentarios; al quedar todo el texto en una línea, `#[^\n]*` devoraba desde el primer `#` (incluidos literales hex como `'#39C5BB'` dentro de strings) hasta el final del blob completo, over-colapsando records distintos. Ahora los comentarios se strippean sobre el texto multi-línea original. Impacto medido: +3.739 records legítimamente distintos recuperados en el pilot (write 10.704→13.697, game 1.441→1.479, understand 3.043→3.374).
- **`scripts/finalize.py`**: los shards de `hard_holdout` compartían prefijo entre write y understand del mismo dataset (media/game), por lo que el segundo grupo BORRABA los shards del primero (7 records game-understand perdidos). Ahora el prefijo se califica por kind.
- **`scripts/make_stats.py`**: los records de hard_holdout se atribuían por prefijo de nombre de fichero (compartido entre kinds) → doble conteo (game_understand inflado 618→806). Ahora se atribuyen por los campos `(dataset, kind)` del propio record.

### Decisiones de calidad
- 38.068 staged → **19.499 publicados** (write 13.697 · understand 3.374 · media 949 · game 1.479): el dedup normalizado elimina duplicados semánticos; la retención MV tras parametrizar las familias (mid de rampa, tonos ember, letras/timings karaoke, jitter, dimensiones) fue del 59–77%.

## [0.1.0] — Piloto verificado

### Añadido
- Pipeline reproducible GENERAR → EJECUTAR → COMPROBAR → FILTRAR → CONSERVAR con reanudación por lotes (`scripts/build_dataset.py`).
- 49 familias generadoras en 14 lenguajes + banco multilingüe de 13 problemas (py/cpp/c/js/ts/bash) con CLI shims para equivalencia cruzada.
- Ejecutores con sandbox (rlimits): python, c (gcc), cpp (g++), js (node), ts (type-stripping), sql (sqlite), bash, validación estructural (html/css/powershell/glsl/genérico para lenguajes sin toolchain).
- Dataset 1 `write` (10.704 verificados) y Dataset 2 `understand` (3.043) con 14 tipos de tarea: debugging con prueba real de fallo/corrección, trazas verificadas por ejecución, traducción con equivalencia entre lenguajes, optimización con evidencia de tiempo, testing con puntuación de mutación, seguridad con demostración controlada, predicción de fallos con comportamiento observado, revisión, complejidad, refactor, comparación, arquitectura y selección de lenguaje.
- Dataset 3 `media` (545): timeline/easing, render determinista con Pillow (frames comparados byte a byte), análisis audio→datos→visual (envolventes, onsets, BPM→frames), lógica TS, shaders GLSL (estático), proyecto multi-file.
- Dataset 4 `game_engineering` (1.441): formatos binarios sintéticos con round-trip, saves TLV+crc32, atlas de sprites, conversión de coordenadas/cuaterniones, VM de scripting (assembler+intérprete), buses de eventos para modding con gates semver, proyecto de interoperabilidad entre motores; tareas de análisis con protocolo hipótesis→test→evidencia→conclusión.
- Deduplicación exacta + normalizada (identificadores posicionales), splits agrupados por (familia, variante), hard holdout experto, quarantine.
- Esquemas JSON, suite pytest (13 tests), Makefile, CI (GitHub Actions), estadísticas y quality report automáticos.

### Decisiones de calidad
- 37.482 generados → 15.733 publicados: los duplicados semánticos (familias con espacios de parámetros pequeños) se eliminaron en lugar de inflar el volumen.
- Lenguajes sin toolchain en el sandbox quedan en `static_check` y no cuentan como verificados por ejecución.
