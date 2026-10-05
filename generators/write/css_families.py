"""Dataset-1 write families for CSS (STATIC verification only).

CSS artifacts cannot be rendered headlessly here, so candidates carry
verify_method="static_check". The static validator
(validators/executors/static_check.py::check_css) enforces:
  * balanced braces (depth walk plus count match),
  * every declaration inside a rule block looks "prop: value;" — a colon
    per declaration line,
  * at most a handful of !important (these families use zero).
Families therefore emit canonical modern CSS: every declaration ends with
a semicolon, custom properties live on :root and are consumed via var(),
and no comments appear inside declaration blocks (comments between rules
are fine and are used sparingly for sectioning).

Determinism: every random decision flows from the rng passed to generate().
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, register


def _fill(template: str, **kw) -> str:
    """Substitute {token} placeholders; literal CSS braces stay untouched."""
    out = template
    for key, value in kw.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def _explain(purpose, approach, key_points, big_o_time, big_o_space, edge_cases):
    return {
        "purpose": purpose,
        "approach": approach,
        "key_points": key_points,
        "big_o_time": big_o_time,
        "big_o_space": big_o_space,
        "edge_cases": edge_cases,
    }


class CssLayoutFlexgridFamily(Family):
    """Flexbox navigation plus a responsive card grid."""
    NAME = "css_layout_flexgrid"
    LANGUAGE = "css"
    DOMAIN = "web"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "comparison")

    SITES = ("Canopy Desk Goods", "Fieldnote Outdoor", "Halo Coffee Roasters",
             "Loom Textile Studio", "Nimbus Bike Hire")

    def generate(self, rng: random.Random) -> Candidate:
        site = rng.choice(self.SITES)
        grid_mode = rng.choice(["auto_fit", "fixed"])
        min_card = rng.choice([200, 220, 240, 260])
        cols = rng.choice([2, 3, 4])
        gap = rng.choice(["0.75rem", "1rem", "1.25rem", "1.5rem"])
        section_gap = rng.choice(["2rem", "2.5rem", "3rem"])
        border = rng.choice(["#d4d4d8", "#cbd5e1", "#d6d3d1", "#e4e4e7"])
        radius = rng.choice(["0.375rem", "0.5rem", "0.75rem"])

        if grid_mode == "auto_fit":
            grid_columns = (f"repeat(auto-fit, minmax({min_card}px, 1fr))")
            grid_note = ("auto-fit reflows the column count as the viewport "
                         "narrows")
        else:
            grid_columns = f"repeat({cols}, minmax(0, 1fr))"
            grid_note = (f"a fixed {cols}-column track list that stays even on "
                         f"wide screens")
        css = _fill(
            "/* Flex header nav and grid card shelf for {site}. */\n"
            ".site-header {\n"
            "  display: flex;\n"
            "  align-items: center;\n"
            "  justify-content: space-between;\n"
            "  flex-wrap: wrap;\n"
            "  gap: {gap};\n"
            "  padding: 0.75rem 1.25rem;\n"
            "}\n\n"
            ".site-nav ul {\n"
            "  display: flex;\n"
            "  flex-wrap: wrap;\n"
            "  gap: 0.5rem {gap};\n"
            "  list-style: none;\n"
            "  margin: 0;\n"
            "  padding: 0;\n"
            "}\n\n"
            ".brand {\n"
            "  font-weight: 700;\n"
            "  letter-spacing: 0.02em;\n"
            "}\n\n"
            ".shelf {\n"
            "  display: grid;\n"
            "  grid-template-columns: {grid_columns};\n"
            "  gap: {section_gap};\n"
            "  padding: {section_gap} 1.25rem;\n"
            "}\n\n"
            ".card {\n"
            "  display: flex;\n"
            "  flex-direction: column;\n"
            "  gap: {gap};\n"
            "  border: 1px solid {border};\n"
            "  border-radius: {radius};\n"
            "  padding: 1rem;\n"
            "}\n\n"
            ".card-title {\n"
            "  margin: 0;\n"
            "  font-size: 1.05rem;\n"
            "}\n\n"
            ".card-body {\n"
            "  margin: 0;\n"
            "  color: #52525b;\n"
            "}\n\n"
            ".card-footer {\n"
            "  margin-top: auto;\n"
            "  display: flex;\n"
            "  justify-content: flex-end;\n"
            "}\n",
            site=site, gap=gap, grid_columns=grid_columns,
            section_gap=section_gap, border=border, radius=radius)
        task = (f"Write the layout stylesheet for '{site}': a flexbox site header "
                f"that keeps the brand and the nav list on one wrap-friendly row "
                f"(space-between, gap {gap}), and a card shelf built on CSS grid "
                f"with {grid_note} and gap {section_gap}. Cards flex vertically "
                f"with a border, {radius} radius and a footer pushed to the bottom "
                f"via margin-top: auto. Every declaration must end with a "
                f"semicolon and no !important may appear.")
        expected = ("Header and nav share one flex row that wraps on narrow "
                    "screens; the shelf lays cards on the chosen grid tracks; "
                    "each card is a column flex box with its footer pinned down.")
        return Candidate(
            family=self.NAME, language="css", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected,
            code=css, verify_method="static_check",
            notes={"explain": _explain(
                expected,
                "One flex formatting context for the header row and one grid "
                "formatting context for the shelf; cards reuse flex-column to "
                "align their footers.",
                ["flex-wrap on the header lets long nav lists drop to a second "
                 "row instead of overflowing",
                 "minmax(0, 1fr) tracks keep fixed grids from blowing out on "
                 "long words inside cards",
                 "margin-top: auto inside a flex column pins the card footer "
                 "without absolute positioning",
                 "gap replaces margin hacks for both the flex and grid gaps"],
                "O(1) at paint time; layout work is per rendered element",
                "O(1) stylesheet size",
                ["a viewport narrower than min_card collapses auto-fit tracks "
                 "to a single column",
                 "a card with little content still fills its track height and "
                 "keeps the footer at the bottom"])},
            tags=["css", "layout", "flexbox", "grid"],
            variant=grid_mode, seed=rng.randrange(2 ** 31))


class CssResponsiveThemesFamily(Family):
    """Custom properties on :root consumed via var(), plus media queries."""
    NAME = "css_responsive_themes"
    LANGUAGE = "css"
    DOMAIN = "web"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "comparison")

    THEMES = (
        ("paper", "#b45309", "#fffbeb", "#fef3c7"),
        ("meadow", "#15803d", "#f0fdf4", "#dcfce7"),
        ("dusk", "#6d28d9", "#f5f3ff", "#ede9fe"),
        ("frost", "#0369a1", "#f0f9ff", "#e0f2fe"),
        ("clay", "#b91c1c", "#fef2f2", "#fee2e2"),
    )
    DARK_BG = ("#0f172a", "#111827", "#1c1917")
    BREAKPOINTS = (40, 48, 56, 64)

    def generate(self, rng: random.Random) -> Candidate:
        theme_name, accent, page_bg, surface = rng.choice(self.THEMES)
        dark_bg = rng.choice(self.DARK_BG)
        bp = rng.choice(self.BREAKPOINTS)
        radius = rng.choice(["0.25rem", "0.5rem", "0.75rem"])
        css = _fill(
            "/* {theme_name} theme: tokens on :root, dark mode and a narrow\n"
            "   viewport adjustment via media queries. */\n"
            ":root {\n"
            "  --bg: {page_bg};\n"
            "  --surface: {surface};\n"
            "  --fg: #1f2937;\n"
            "  --muted: #6b7280;\n"
            "  --accent: {accent};\n"
            "  --radius: {radius};\n"
            "}\n\n"
            "body {\n"
            "  margin: 0;\n"
            "  background: var(--bg);\n"
            "  color: var(--fg);\n"
            "  font-family: system-ui, sans-serif;\n"
            "  line-height: 1.5;\n"
            "}\n\n"
            "a {\n"
            "  color: var(--accent);\n"
            "}\n\n"
            ".panel {\n"
            "  background: var(--surface);\n"
            "  border: 1px solid var(--muted);\n"
            "  border-radius: var(--radius);\n"
            "  padding: 1rem 1.25rem;\n"
            "}\n\n"
            ".meta {\n"
            "  color: var(--muted);\n"
            "  font-size: 0.875rem;\n"
            "}\n\n"
            "@media (max-width: {bp}rem) {\n"
            "  body {\n"
            "    font-size: 0.9375rem;\n"
            "  }\n"
            "  .panel {\n"
            "    border-radius: 0;\n"
            "  }\n"
            "}\n\n"
            "@media (prefers-color-scheme: dark) {\n"
            "  :root {\n"
            "    --bg: {dark_bg};\n"
            "    --surface: #1f2937;\n"
            "    --fg: #e5e7eb;\n"
            "    --muted: #9ca3af;\n"
            "  }\n"
            "}\n",
            theme_name=theme_name, page_bg=page_bg, surface=surface,
            accent=accent, radius=radius, bp=bp, dark_bg=dark_bg)
        task = (f"Author a '{theme_name}' theme stylesheet driven entirely by "
                f"custom properties: declare --bg, --surface, --fg, --muted, "
                f"--accent ({accent}) and --radius on :root, consume every one of "
                f"them through var() in the body, link, panel and meta rules, "
                f"then add a max-width: {bp}rem media query that shrinks the base "
                f"font and squares the panel corners, plus a "
                f"prefers-color-scheme: dark block that retunes the tokens for a "
                f"{dark_bg} page background. Every declaration ends with a "
                f"semicolon.")
        expected = ("Light mode paints from the :root tokens; below the "
                    f"{bp}rem breakpoint typography tightens and panels square "
                    "off; dark mode swaps the token values so every var() "
                    "consumer follows automatically.")
        return Candidate(
            family=self.NAME, language="css", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected,
            code=css, verify_method="static_check",
            notes={"explain": _explain(
                expected,
                "Define the palette once as custom properties, reference it "
                "with var(), and retheme by reassigning tokens inside media "
                "queries instead of restating every rule.",
                ["reassigning tokens in the dark block re-themes every "
                 "consumer in one place",
                 "var() keeps rules free of raw hex values, so accents can be "
                 "A/B tested by editing a single line",
                 "the narrow-viewport query adjusts typography and geometry "
                 "without duplicating colour work",
                 "rem-based breakpoint keeps the switch aligned with user font "
                 "preferences"],
                "O(1) at paint time; cascade resolution is per element",
                "O(1) stylesheet size",
                ["viewports exactly at the breakpoint take the mobile styles, "
                 "since max-width is inclusive",
                 "users forcing light mode keep the original tokens even on "
                 "dark system settings",
                 "an undefined var() fallback is never needed because every "
                 "token is declared on :root"])},
            tags=["css", "theme", "custom-properties", theme_name],
            variant=theme_name, seed=rng.randrange(2 ** 31))


class CssAnimationsStatesFamily(Family):
    """Transitions, hover/focus-visible states and @keyframes from/to."""
    NAME = "css_animations_states"
    LANGUAGE = "css"
    DOMAIN = "web"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "code_review")

    PALETTE = (
        ("#1d4ed8", "#1e40af", "#60a5fa"),
        ("#047857", "#065f46", "#34d399"),
        ("#b45309", "#92400e", "#fbbf24"),
        ("#7c3aed", "#5b21b6", "#a78bfa"),
    )
    DURATIONS = (120, 160, 200, 240, 320)
    KEYFRAMES = ("rise", "pop-in", "fade-up", "settle")

    def generate(self, rng: random.Random) -> Candidate:
        accent, accent_hover, focus_ring = rng.choice(self.PALETTE)
        dur = rng.choice(self.DURATIONS)
        enter = rng.choice(self.DURATIONS)
        kf = rng.choice(self.KEYFRAMES)
        offset = rng.choice(["6px", "8px", "10px"])
        scale = rng.choice(["0.96", "0.97", "0.98"])
        css = _fill(
            "/* Interactive states: transitions on hover/focus-visible and a\n"
            "   one-shot {kf} entrance for panels. */\n"
            ".button {\n"
            "  background: {accent};\n"
            "  color: #ffffff;\n"
            "  padding: 0.5rem 1rem;\n"
            "  border: 0;\n"
            "  border-radius: 0.375rem;\n"
            "  transition: background {dur}ms ease, transform {dur}ms ease;\n"
            "}\n\n"
            ".button:hover {\n"
            "  background: {accent_hover};\n"
            "  transform: translateY(-1px);\n"
            "}\n\n"
            ".button:focus-visible {\n"
            "  outline: 2px solid {focus_ring};\n"
            "  outline-offset: 2px;\n"
            "}\n\n"
            ".button:active {\n"
            "  transform: scale({scale});\n"
            "}\n\n"
            ".panel {\n"
            "  animation: {kf} {enter}ms ease-out both;\n"
            "}\n\n"
            "@keyframes {kf} {\n"
            "  from {\n"
            "    opacity: 0;\n"
            "    transform: translateY({offset});\n"
            "  }\n"
            "  to {\n"
            "    opacity: 1;\n"
            "    transform: translateY(0);\n"
            "  }\n"
            "}\n\n"
            "@media (prefers-reduced-motion: reduce) {\n"
            "  .panel {\n"
            "    animation: none;\n"
            "  }\n"
            "  .button {\n"
            "    transition: none;\n"
            "  }\n"
            "}\n",
            kf=kf, accent=accent, accent_hover=accent_hover,
            focus_ring=focus_ring, dur=dur, enter=enter, offset=offset,
            scale=scale)
        task = (f"Style an interactive button and panel set: the button carries a "
                f"{dur}ms background/transform transition, darkens to "
                f"{accent_hover} on hover, shows a visible {focus_ring} outline "
                f"ring only on :focus-visible keyboard focus, and compresses "
                f"slightly on :active. Panels enter once with a {enter}ms "
                f"@keyframes animation named {kf} that runs from opacity 0 and "
                f"translateY({offset}) to full opacity. Add a "
                f"prefers-reduced-motion block that disables the animation and "
                f"the transition. No !important anywhere.")
        expected = ("Hover and active states animate smoothly through the "
                    "transition; keyboard focus alone raises the outline ring; "
                    "panels play the entrance keyframes once (fill both) unless "
                    "reduced motion is requested.")
        return Candidate(
            family=self.NAME, language="css", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected,
            code=css, verify_method="static_check",
            notes={"explain": _explain(
                expected,
                "Transitions handle state deltas on the button, a from/to "
                "keyframe pair handles the one-shot panel entrance, and the "
                "reduced-motion query turns both off.",
                [":focus-visible rings keyboard users only, leaving mouse "
                 "clicks ring-free",
                 "animation-fill-mode both holds the from state before the "
                 "animation starts and the to state afterwards",
                 "transitions are declared on the base rule so both enter and "
                 "exit directions animate",
                 "prefers-reduced-motion is honoured without media-query "
                 "duplication of the component rules"],
                "O(1) at paint time; animation work is compositor-side",
                "O(1) stylesheet size",
                ["touch devices get the hover colour without a sticky transform "
                 "since the transform is transition-dependent",
                 "reduced-motion users still see the final panel state because "
                 "fill mode is dropped along with the animation",
                 "rapid tabbing only re-runs the outline ring, never the "
                 "panel animation"])},
            tags=["css", "animation", "states"], variant=kf,
            seed=rng.randrange(2 ** 31))

    def review_variant(self, rng: random.Random):
        """Working stylesheet with motion-accessibility flaws for review."""
        accent, accent_hover, focus_ring = rng.choice(self.PALETTE)
        css = _fill(
            "/* Review variant: same visual result, rougher motion story. */\n"
            ".button {\n"
            "  background: {accent};\n"
            "  color: #ffffff;\n"
            "  padding: 0.5rem 1rem;\n"
            "  border: 0;\n"
            "  border-radius: 0.375rem;\n"
            "  transition: all 400ms ease;\n"
            "}\n\n"
            ".button:hover {\n"
            "  background: {accent_hover};\n"
            "  transform: translateY(-2px);\n"
            "}\n\n"
            ".button:focus {\n"
            "  outline: none;\n"
            "}\n\n"
            ".button:focus-visible {\n"
            "  outline: 2px solid {focus_ring};\n"
            "}\n\n"
            ".panel {\n"
            "  animation: bounce-in 600ms ease-in-out infinite alternate;\n"
            "}\n\n"
            "@keyframes bounce-in {\n"
            "  from {\n"
            "    opacity: 0;\n"
            "    transform: scale(0.9);\n"
            "  }\n"
            "  to {\n"
            "    opacity: 1;\n"
            "    transform: scale(1.02);\n"
            "  }\n"
            "}\n",
            accent=accent, accent_hover=accent_hover, focus_ring=focus_ring)
        cand = Candidate(
            family=self.NAME, language="css", domain=self.DOMAIN,
            difficulty="intermediate",
            task="Review this stylesheet before it ships. Visually the buttons "
                 "change on hover and the panels bounce in, but the team wants "
                 "a pass on focus handling, motion sensitivity and transition "
                 "hygiene before release.",
            expected_behavior="The styles apply as written; the review targets "
                              "focus accessibility, motion preferences and the "
                              "transition property choice.",
            code=css, verify_method="static_check",
            notes={"explain": _explain(
                "A hover-animated button plus an infinitely bouncing panel.",
                "One blanket transition and an infinite keyframe loop keep the "
                "CSS short but ignore user preferences.",
                ["the panel animation runs forever, which is the review's "
                 "headline problem",
                 "focus handling is split across two rules with one resetting "
                 "the outline entirely",
                 "transition: all covers properties nobody asked to animate"],
                "O(1) at paint time", "O(1) stylesheet size",
                ["motion-sensitive users get a permanently moving panel",
                 "keyboard users may see no visible focus depending on rule "
                 "order"])},
            tags=["css", "animation", "states", "review"],
            variant="states|review", seed=rng.randrange(2 ** 31))
        issues = [
            {"kind": "a11y", "severity": "high",
             "why": "the panel animation loops infinitely with alternate "
                    "direction, so the page never stops moving",
             "better": "run the entrance once with fill-mode both and wrap it "
                       "in a prefers-reduced-motion guard"},
            {"kind": "a11y", "severity": "high",
             "why": "outline: none on :focus removes the visible focus "
                    "indicator for browsers where :focus-visible never matches",
             "better": "style only :focus-visible, or pair outline: none with "
                       "an equivalent box-shadow ring"},
            {"kind": "maintainability", "severity": "medium",
             "why": "transition: all animates every animatable property, so a "
                    "future margin change starts sliding for free",
             "better": "list the intended properties explicitly: background, "
                       "transform"},
            {"kind": "style", "severity": "low",
             "why": "a 400ms duration is long for a hover delta and feels "
                    "laggy on repeated interactions",
             "better": "drop to the 120-200ms band used across the design "
                       "system"},
        ]
        return cand, issues


register(globals(), CssLayoutFlexgridFamily)
register(globals(), CssResponsiveThemesFamily)
register(globals(), CssAnimationsStatesFamily)
