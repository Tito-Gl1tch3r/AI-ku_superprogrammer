# VIDEO RESEARCH — fuentes para el salto de vídeo end-to-end (v0.8.0)

> Nota de investigación, v0.7.0. Tres repositorios de "skills de agente" para
> vídeo, estudiados como **referencias conceptuales** para la Prioridad 3 del
> roadmap (convertir el módulo de vídeo en una capacidad de extremo a extremo
> nativa TS/JS). Nada de su código se copia al dataset; los patrones que
> describen se convertirán en familias sintéticas verificadas propias, con la
> paleta de señal por defecto del proyecto: **turquesa #39C5BB (Miku teal),
> nunca naranja**.

## 0. Fuente primaria: mexicat/pdoom-video (la que sirve para hacerlo)

[pdoom-video](https://github.com/mexicat/pdoom-video) es el proyecto del que
salió todo lo demás: es la **referencia arquitectónica primaria** del módulo 02
desde v0.2.0 (motor de escenas → timeline determinista → render offline) y el
objeto de la ingeniería inversa de v0.4.0 (`docs/OPUS_STYLE.md` documenta sus
hábitos convertidos en familias verificadas). Para v0.8.0 es la **prioridad
número uno** de las fuentes: el salto TS/Remotion debe empezar por portar SU
arquitectura (escenas reutilizables, timeline como dato, render puro
verificable, paleta como constante — el `SIGNAL #39C5BB` ya es herencia de esa
línea) al ecosistema TS/Three.js del proyecto real. Orden de estudio para
v0.8.0: (1) pdoom-video (arquitectura), (2) video-motion-craft (craft),
(3) claude-remotion-skill (bucle de revisión), (4) remotion-dev/skills (API).

## 1. Las tres fuentes

| Repo | Qué es | Licencia |
|---|---|---|
| [remotion-dev/skills](https://github.com/remotion-dev/skills) | Skills oficiales de Remotion para agentes (`remotion-best-practices`, `-create`, `-markup`, `-render`, `-captions`, `-maps`, …): convenciones de composiciones, timing, audio, transiciones, fuentes, render | Remotion (repo privado del paquete; documentación pública) |
| [vibegameengine/video-motion-craft](https://github.com/vibegameengine/video-motion-craft) | Skill "craft" cinematográfico: 12 reglas innegociables de motion design + referencias (beat-sync, shot vocabulary, sound design, game capture, review checklist) | Apache-2.0 |
| [haidrrrry/claude-remotion-skill](https://github.com/haidrrrry/claude-remotion-skill) | Skill MIT con el bucle **render → inspeccionar fotogramas → arreglar → re-render** codificado como paso obligatorio | MIT |

El diagnóstico compartido por las tres: **el cuello de botella no es el código,
es el craft de motion design**. Sin calibración, un modelo produce easing
lineal, fades de solo opacidad, entradas simultáneas, fondos planos y silencio
— el look de "vídeo AI barato".

## 2. Patrones que faltan en AI-ku y cómo se convierten en familias

### 2.1 Reglas de movimiento como checks verificables (de video-motion-craft)

Las 12 reglas son sorprendentemente **testeables en la capa lógica** de una
composición TS: se puede afirmar que cada `interpolate` lleva clamps y curva,
que las entradas animan 2–3 propiedades, que los staggers son de 3–6 frames y
que no hay `Math.random()` sin semilla. Familias candidatas (TS, lógica
verificable headless con el executor TS existente):

- `media_ts_motion_rules` — detectar/reescribir composiciones que violan las
  reglas (easing lineal, fade solitario, stagger ausente) y verificar que la
  versión corregida pasa los checks estructurales.
- `media_ts_theme` — disciplina `theme.ts`: paleta/easings/springs/fuentes en
  un único archivo; un hex dentro de un componente es un defecto. El theme por
  defecto del proyecto usa #39C5BB como color de señal/acento único (T2:
  "un acento por frame").
- `media_ts_deterministic_render` — prohibir `Date.now()`/`Math.random()`,
  exigir PRNG con semilla fija (mulberry32) y render reproducible; el check
  compara dos renders simulados fotograma a fotograma.

### 2.2 Beat-sync con rejilla aceptada ANTES del storyboard

El flujo de video-motion-craft es "música primero": la rejilla de beats se
calcula (librosa/beat_track + corrección), se **acepta con error ≤ 3 frames**
y solo entonces se guioniza; los timestamps viven en segundos flotantes y se
convierten a frames UNA vez. Esto conecta con lo que ya entrenamos
(`media_audio_analysis`, `media_mv_karaoke`): la familia nueva sería
`media_ts_beat_grid` — construir la rejilla a partir de un análisis dado,
anclar cada corte a un beat y verificar el error de corte en frames.

### 2.3 El bucle de revisión visual como record

Las tres fuentes insisten en lo mismo que ya entrenamos como honestidad de
evidencia: **un render no verificado no se entrega**. claude-remotion-skill lo
codifica como bucle obligatorio; video-motion-craft añade un checklist de
aceptación con informe por fotograma (`code ✗ (frame 615)`) y la idea de un
**revisor con contexto limpio**. Familias candidatas:

- `media_ts_render_verify` — pipeline completo: render determinista → extraer
  fotogramas clave → comprobar dimensiones/fps/duración/audio/vacíos →
  corregir → re-render (el simulador headless ejecuta la lógica de escena y
  las comprobaciones de salida).
- `media_ts_review_report` (understand) — dado un informe de revisión con
  hallazgos por frame, decidir si la entrega pasa el checklist y qué se debe
  re-renderizar; distractores = informes sin números de frame ("looks fine").

### 2.4 Skills oficiales Remotion: el mapa de capacidades

`remotion-markup` (composiciones/animación/layout/tipografía/audio/timing) y
`remotion-render` (CLI, stills, concurrencia) dan el índice de temas para
proyectar el plan de estudios TS de v0.8.0 sin inventar la API: las familias
deben usar la API REAL de Remotion (@remotion/cli, useVideoConfig, interpolate,
spring, OffthreadVideo, Sequence, Audio) verificada contra la documentación,
nunca APIs inventadas — el mismo principio que P6 (integrar APIs desconocidas
leyendo sus contratos).

## 3. Plan propuesto para v0.8.0 (P3 del roadmap)

1. **Base TS**: `media_ts_theme`, `media_ts_motion_rules`,
   `media_ts_deterministic_render` (lógica pura, executor TS ya existente).
2. **Timeline real**: `media_ts_beat_grid` (rejilla aceptada antes del
   storyboard; cortes anclados con error ≤ 3 frames).
3. **Render + revisión**: `media_ts_render_verify` +
   `media_ts_review_report` (bucle render→inspección→fix como record).
4. **Proyectos completos**: ampliar `media_mv_project` a variante TS/Remotion
   multifichero (tema + escenas + timeline + render config) — y CADA proyecto
   experto completo va al hard_holdout por la política v0.7.0.
5. **Paleta**: #39C5BB como acento por defecto en todos los themes (ya es el
   `SIGNAL_HEX` del repo; los 557+ records existentes lo llevan).

## 4. Prohibiciones (coherencia con la ética del repo)

- Cero código copiado de los tres repos: son referencias de PATRONES; todo el
  material del dataset sigue siendo sintético y generado por las familias.
- Sin objetivos de terceros ni assets con copyright en los ejemplos: los
  proyectos de ejemplo usan geometría/texto/audio generados en el sandbox.
- Rocket League no aparece en ningún record (es benchmark); la "elevación de
  alcance" se entrena con arquetipos genéricos (ver `ops_scope_elevation`).
