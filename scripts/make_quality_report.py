#!/usr/bin/env python3
"""Generate QUALITY_REPORT.md from finalize summary + stats."""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    with open(os.path.join(ROOT, "reports", "stats.json")) as f:
        stats = json.load(f)
    fs_path = os.path.join(ROOT, "reports", "finalize_summary.json")
    fs = {}
    if os.path.exists(fs_path):
        with open(fs_path) as f:
            fs = json.load(f)

    def fmt(n):
        return f"{n:,}"

    lines = [
        "# QUALITY REPORT — AI-ku_superprogrammer",
        "",
        "> Generado automáticamente por `scripts/make_quality_report.py`. Todas las cifras",
        "> provienen de ejecuciones reales del pipeline (nada está inventado).",
        "",
        "## 1. Resumen ejecutivo",
        "",
    ]
    for stage, s in stats.items():
        lines += [
            f"- **{stage}**: {fmt(s['total'])} ejemplos publicados; "
            f"{s['pct_verified_executed']}% verificados por ejecución/compilación real, "
            f"{s['pct_verified_static']}% verificación estructural (lenguajes sin toolchain local).",
        ]
    lines += [
        "",
        "## 2. Protocolo de calidad aplicado",
        "",
        "1. **GENERAR → EJECUTAR → COMPROBAR → FILTRAR → CONSERVAR**: ningún ejemplo se publica",
        "   sin pasar por el validador de su lenguaje (compilador + tests reales, o verificación",
        "   estructural cuando no existe toolchain).",
        "2. **Quarantine**: los intentos fallidos (compilación, tests, calidad) van a",
        "   `datasets/_quarantine/` y NUNCA entran en train/validation/test (política del proyecto).",
        "3. **Deduplicación**: hash exacto + hash normalizado (identifiers mapeados a tokens",
        "   posicionales) — elimina copias literales y variantes cosméticas renombradas.",
        "4. **Familias con tope** (`family_cap`) para evitar flooding de plantillas.",
        "5. **Splits anti-contaminación**: agrupados por `(family, variant)` — plantillas",
        "   conceptuales enteras caen en un único split; el test nunca comparte plantilla con train.",
        "6. **Hard holdout**: grupos `expert` seleccionados por hash se apartan en",
        "   `datasets/hard_holdout/` y no se usan en generación ni en entrenamiento.",
        "7. **Evidence-based answers (Dataset 2)**: los fallos, timings, equivalencias y trazas",
        "   se observaron ejecutando código en sandbox — ver `verification.*` en cada record.",
        "",
        "## 3. Métricas de filtrado (finalize)",
        "",
    ]
    for stage, s in fs.items():
        lines += [
            f"### {stage}",
            "",
            f"- staged → kept: {fmt(s.get('staged', 0))} → **{fmt(s.get('kept', 0))}**",
            f"- duplicados eliminados (exacto+normalizado): {fmt(s.get('dupes_removed', 0))}",
            f"- recortados por family cap: {fmt(s.get('family_capped', 0))}",
            f"- rechazados por schema: {s.get('schema_rejected', 0)}",
            f"- splits: {json.dumps(s.get('splits', {}))}",
            f"- multi-file: {s.get('multi_file', 0)} | con tests: {s.get('with_tests', 0)}",
            "",
        ]
    lines += [
        "## 4. Cobertura de verificación por lenguaje",
        "",
        "| lenguaje | método | notas |",
        "|---|---|---|",
        "| python | ejecutado (subprocess + rlimits) | tests con asserts, marcador `__TESTS_PASSED__` |",
        "| c | gcc 14.2 -std=c11 -Wall -Wextra + ejecución | harness con assert.h |",
        "| cpp | g++ 14.2 -std=c++17 + ejecución | harness con cassert |",
        "| javascript | node 24 + assert | CommonJS `module.exports` |",
        "| typescript | node 24 type-stripping | sintaxis erasable obligatoria |",
        "| sql | sqlite en memoria | filas esperadas calculadas independientemente en Python |",
        "| bash | bash + fixtures en sandbox cwd | stdout/exit comparados |",
        "| html/css/powershell/go/rust/java/php | `static_check` estructural | sin toolchain en sandbox; el run full debe verificarlos con toolchains reales |",
        "",
        "## 5. Limitaciones conocidas (honestidad ante todo)",
        "",
        "- Síntesis basada en plantillas parametrizadas: la diversidad proviene de dominios,",
        "  algoritmos, errores y contextos distintos; los caps por familia y la dedup",
        "  normalizada mitigan el riesgo de variaciones cosméticas.",
        "- Lenguajes estáticos (`go`, `rust`, `java`, `php`, `powershell`): verificación",
        "  estructural; sus records llevan `verification.method = static_check` y NO cuentan",
        "  como ejecutados en las métricas.",
        "- HTML/CSS no se renderizan: la verificación es estructural (balance, atributos",
        "  requeridos, anti-patrones).",
        "- El grading de tareas de explicación/revisión usa ground truth autorado junto al",
        "  código; los benchmarks de auto-evaluación lo documentan y los puntajes de mutación",
        "  son reales.",
        "- Los benchmarks internos (`evaluators/`) son puntos de partida; un model eval real",
        "  requiere ejecutar el harness con las predicciones del modelo.",
        "",
        "## 6. Estadísticas detalladas",
        "",
        "Ver `reports/stats.md` y `reports/stats.json`.",
    ]
    out = os.path.join(ROOT, "QUALITY_REPORT.md")
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("written", out)


if __name__ == "__main__":
    main()
