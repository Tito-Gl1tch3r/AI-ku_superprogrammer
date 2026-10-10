# Roadmap "Superprogramadora" — qué le falta a AI-ku (propuestas v0.5.0+)

> Pregunta que responde este documento: ¿qué capacidades nuevas, que NO cubren las 61 familias actuales, acercarían a AI-ku a ser una superprogramadora?
>
> Regla de oro respetada en cada propuesta: **nada se inventa** — cada idea incluye cómo se verifica con el pipeline existente (GENERAR → EJECUTAR → COMPROBAR → FILTRAR → CONSERVAR). Huecos detectados auditando el registro real de familias (v0.4.1), no adivinados.

> **Estado v0.7.0**: el módulo 05 · Agent Persistence está implementado y publicado como `AI-ku_superprogrammer_agent_ops` (968 records) — monitorización real de jobs, objetivos compuestos con ISO9660 real, supervisión de progreso y elevación de alcance; además se cerró la **Prioridad 0 del audit externo** (splits de re_write/re_understand, holdout de media "proyectos completos no vistos", métricas con método de verificación explícito, migración de IDs duplicados) y `docs/VIDEO_RESEARCH.md` prepara el salto TS/Remotion de P3. P5/P6/P7/P10/P11 siguen pendientes para v0.8+, y P3 queda con plan propuesto.

## Lo que YA sabe (para no proponer duplicados)

Comprensión y escritura en 14 lenguajes, debugging con prueba real, testing con mutación, optimización con timing, traducción entre lenguajes, seguridad defensiva, concurrencia básica (py_concurrency, go_concurrency_patterns), proyectos multi-fichero pequeños (~3-4 ficheros), vídeos generativos deterministas con identidad turquesa, modding metodológico y puentes crossover. Lo que sigue NO está en ningún sitio del dataset.

---

## Propuestas nuevas (priorizadas)

### P1 · Bucle de auto-reparación agéntica ✅ v0.5.0 (`iterative_repair`, logs reales multi-turno; la versión Dataset-5 completa de trayectorias largas queda abierta)

**Hueco**: el dataset entrena pasos aislados (escribir X, depurar Y) pero nunca la ITERACIÓN COMPLETA: borrador → ejecutar → leer el fallo real → hipótesis → parche → re-ejecutar → repetir hasta verde.

**Qué entrena**: agencia. Una superprogramadora no entrega un intento: converge. Además es el formato de despliegue real de AI-ku (bucle de herramientas), así que el entrenamiento coincide con el uso.

**Formato**: records multi-turno con el historial real de ejecuciones (command, salida, traceback VERDADERO del sandbox) y la decisión tomada en cada turno. La respuesta objetivo es el siguiente parche, no una explicación.

**Verificación (ya la tenemos)**: cada turno se ejecuta de verdad — el historial solo contiene observaciones reales del executor; el parche final pasa los tests y las tentativas intermedias fallan con el traceback registrado. Sin ejecución real no hay record.

**Familias**: `agent_fix_loop` (bug plantado, k≥2 turnos), `agent_build_up` (especificación que se revela por stages: v1 compila pero falla un edge → v2 lo cubre), `agent_regression_hunt` (combinar con P2-bisect).

### P2 · Git de verdad: bisect, conflictos, arqueología de repo ✅ parcial v0.5.0 (`py_git_forensics`: bisect con presupuesto + arqueología; merge conflicts pendientes)

**Hueco**: cero VCS en el dataset. Bisectar una regresión y resolver un merge conflict son habilidades de superprogramadora diarias y 100% verificables.

**Qué entrena**: localizar el commit culpable leyendo diffs; resolver conflictos preservando la intención de AMBAS ramas; navegar un repo desconocido con grep en vez de asumir.

**Verificación**: `git_bisect_hunt` — repo sintético con historia real de commits y bug plantado en el commit N; el ground truth ES N y se comprueba ejecutando el test en cada commit del historial (el mal candidato da una secuencia de bisect imposible). `git_merge_conflict` — el merge resuelto debe compilar y pasar los tests combinados de ambas ramas; los conflictos mal resueltos (perder un lado) fallan tests que existen en el repo. `repo_archaeology` — "¿en qué fichero vive X?" con respuesta única verificable por grep sobre el repo sintético.

### P3 · Testing de propiedades + shrinking ✅ v0.5.0 (`py_property_testing`)

**Hueco**: el testing actual puntúa suites contra mutantes; falta el otro pilar: PROPIEDADES (invariantes que deben cumplirse para cualquier entrada) y minimización de contraejemplos.

**Qué entrena**: pensar en invariantes en vez de casos ("reverse(reverse(x)) == x"), distinguir propiedad correcta de propiedad trivial, y al fallar, ENCGERAR el caso mínimo que reproduce el fallo (shrinking).

**Verificación**: las propiedades objetivo se ejecutan con generadores seeded (determinista, como todo el pipeline); una propiedad mal elegida (trivial o tautológica) muere contra los mutantes del evaluador existente; el shrinking se puntúa por minimalidad del contraejemplo final comparada con el mínimo conocido.

**Familias**: `prop_invariant_design` (elegir propiedades que maten mutantes), `prop_shrink_trace` (dado el contraejemplo, producir el minimal y justificar cada reducción con re-ejecución real).

### P4 · Diseño tolerante a fallos ✅ v0.5.0 (`py_fault_resilience`; flaky-test forensics pendiente)

**Hueco**: nada de retries/backoff/idempotency-keys/circuit-breakers/timeout-budgeting como OBJETIVO de diseño. (El puente crossover usa idempotencia, pero como pieza de un dominio, no como habilidad general.)

**Qué entrena**: escribir código que falla BIEN bajo un entorno hostil: reintentos con jitter, no duplicar efectos (idempotencia), degradación elegante, presupuesto de timeouts que suma.

**Verificación**: inyector de fallos determinista (schedule seeded de timeouts, excepciones, particiones) — el código correcto completa la tarea a pesar del schedule y sin efectos duplicados; los bugs clásicos (retry sin idempotencia → doble cargo; backoff sin jitter → thrash sincronizado) se detectan porque el schedule los dispara. El observador registra el log real de eventos.

**Familias**: `resil_retry_idempotent`, `resil_circuit_breaker`, `flaky_test_forensics` (detectar y arreglar un test que falla 1/N veces con seeds registradas — probado ejecutándolo N veces).

### P5 · Evolución de esquemas y migraciones de datos

**Hueco**: SQL actual es consultoría (query_scenarios, rewrite, joins); nada de EVOLUCIONAR esquemas sin romper nada.

**Qué entrena**: migrar datos reales entre versiones de esquema manteniendo invariantes (nulos, índices únicos, backward compatibility), y escribir código que convive con DOS versiones del formato durante la transición.

**Verificación**: dataset sintético grande con datos "viejos" corruptos a propósito (duplicados casi-idénticos, huérfanos, zonas horarias mezcladas); la migración correcta produce el estado esperado fila a fila (comparación exacta) y rechaza/flaggea las filas inválidas de forma predecible; el round-trip migrar→roll-back restaura byte-idéntico.

### P6 · Leer documentación de API ficticia e integrar

**Hueco**: nunca se le da a AI-ku una ESPECIFICACIÓN/DOCS de una librería que no conoce y se le pide integrarla. En la realidad eso es el 50% del trabajo.

**Qué entrena**: extraer contratos de docs (firmas, errores, límites de tasa, paginación), no inventar endpoints, respetar lo que las docs dicen que falla.

**Verificación**: cada librería ficticia viene con su implementación de referencia en el sandbox (la "SDK real"); el código integrador se ejecuta contra ella — alucinar un método lanza AttributeError real; los casos borde documentados (rate limit 429, cursor de paginación) están en el test harness.

### P7 · Inserción de features a escala de repo

**Hueco**: los proyectos multi-fichero son de 3-4 ficheros creados de una pieza. Falta ENTRAR en un repo grande pre-existente (10-15 ficheros, 2-3k líneas) y añadir una feature tocando los contratos existentes sin romperlos.

**Qué entrena**: respetar arquitectura ajena (no refactorizar de paso), encontrar los puntos de extensión, mantener convenciones del repo que se leen en el código circundante.

**Verificación**: el repo sintético lleva su suite completa; la feature debe pasar sus tests nuevos Y los de regresión existentes; los anti-tests penalizan atajos (p.ej. duplicar lógica en vez de extender el módulo correcto — detectable porque el módulo correcto tiene el test que deja de recibir la llamada... o más simple: prohibición estructural verificable por diff).

### P8 · Trampas numéricas ✅ v0.5.0 (`py_numeric_robustness`)

**Hueco**: f32 aparece en el oracle de replay, pero nada general de: cancelación catastrófica, sumas de Kahan, overflow de enteros, comparación de floats, redondeo monetario.

**Qué entrena**: ver dónde muere la aritmética ingenua y arreglarla con la técnica estándar correcta.

**Verificación**: entradas adversarias deterministas (p.ej. sumar 1e16 + 1 diez mil veces) donde la versión ingenua produce un resultado DEMOSTRABLEMENTE distinto del exacto (calculado con aritmética exacta del propio script de ground truth); la corrección (Kahan, Decimal para dinero, dígitos de guard) converge al valor exacto dentro de la tolerancia documentada.

### P9 · Trampas de i18n ✅ v0.5.0 (`py_timezones_unicode`)

**Hueco**: cero. Y es una de las mayores fuentes de bugs reales del mundo.

**Qué entrena**: agendar eventos cruzando DST, normalizar unicode antes de comparar (NFC vs NFD — "café" puede ser 2 byte-strings distintos), collation y casefold, ordenar por reglas de locale.

**Verificación**: 100% ejecutable — las comparaciones de strings byte a byte y los timestamps cruzando la frontera DST dan respuestas únicas y comprobables; el ground truth se calcula con `datetime`/`unicodedata` estándar.

### P10 · Optimización guiada por perfil, no por intuición

**Hueco**: la optimización actual compara versiones con timing; falta LEER UN PERFIL REAL y tocar el hotspot verdadero.

**Qué entrena**: interpretar salida de cProfile/contadores de allocaciones; resistirse a optimizar lo que no manda (el 3% que crees vs el 80% que manda); verificar que la versión rápida sigue siendo correcta.

**Verificación**: se genera el perfil REAL (cProfile en el sandbox, determinista con seeds) del programa lento; el ground truth identifica el hotspot medido; una solución que optimiza otra cosa NO reduce el tiempo total por debajo del umbral (medido de verdad) y por tanto falla; la equivalencia se verifica como en optimization actual.

### P11 · Documentación viva con ejemplos ejecutables

**Hueco**: AI-ku nunca escribe docs. Formato doctest: los ejemplos de la doc deben ejecutarse y dar la salida escrita.

**Qué entrena**: escribir para humanos sin mentir — el error clásico de LLM es documentar comportamiento que el código no tiene.

**Verificación**: los bloques de ejemplo se extraen y ejecutan (doctest real); una doc que promete una salida distinta de la observada FALLA; la cobertura doc (cada API pública documentada) es comprobable por AST.

### P12 · Auto-auditoría con niveles de evidencia ✅ v0.5.0 (`evidence_self_audit`)

**Hueco**: `mod_evidence_levels` lo inicia para modding; falta generalizarlo a SU PROPIO código: AI-ku declarando "funciona" debe citar la evidencia (real_run > synthetic_test > derived_comparison > source_inspection > creator_report).

**Qué entrena**: la honestidad epistémica como habilidad: dada una afirmación propia anterior + el log real, auto-clasificar el nivel de evidencia y degradar la afirmación si no hay run real. Es la versión ejecutable de "entender el código que está escribiendo o auditando".

**Verificación**: los pares (afirmación, log) son sintéticos pero los logs son REALES (generados por el executor); clasificar mal un real_run como "sin evidencia" o un creator_report como "verificado" es fallo objetivo con respuesta única.

---

## Recomendación v0.5.0 (si hay que elegir 5)

1. **P1 bucle agéntico** — cambia el tipo de record (multi-turno con ejecución real), es el salto estructural más grande hacia "superprogramadora".
2. **P2 git/bisect/conflictos** — hueco total, verificación sólida, utilidad diaria.
3. **P3 propiedades + shrinking** — complementa la mutación existente; muy difícil de "atrapar" sin entender de verdad.
4. **P4 tolerancia a fallos** — el código que sobrevive a fallos es la firma de un ingeniero senior.
5. **P12 auto-auditoría** — pequeño, barato, y ata TODO el dataset con la identidad de AI-ku (evidencia antes que afirmación).

Estado v0.5.0: P1/P3/P4/P8/P9/P12 implementados, P2 parcial (falta merge conflicts), P5/P6/P7/P10/P11 en la ola v0.6.0 junto con el escalado de volumen de los configs/full.json; P8-P11 son familias puntuales baratas de añadir a cualquier batch.

## Notas de identidad (aplican a toda extensión)

- Contenido del dataset en inglés, docs en español, licencia MIT, calidad > diversidad > cantidad.
- Todo lo verificable se verifica; lo no ejecutable se marca `static_check` honesto.
- El color de señal de cualquier output visual sigue siendo el turquesa Miku `#39C5BB` — nunca naranja.
- Seguridad: solo objetivos sintéticos, patrones defensivos, `refuse-online` correcto ante anti-cheat+online.
