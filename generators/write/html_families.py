"""Dataset-1 write families for HTML (STATIC verification only).

HTML artifacts cannot be rendered headlessly here, so candidates carry
verify_method="static_check". The static validator
(validators/executors/static_check.py::check_html) enforces:
  * strict tag balance via Python's HTMLParser,
  * no external <script src>, no inline on* event handlers,
  * every <img> carries alt, every <a> carries href,
  * every <form> carries action or id,
  * every checkbox/radio <input> carries id (label association).
Families therefore emit complete, semantic, accessible documents:
full doctype, lang attribute, meta viewport, label/for pairs, and
fieldset/legend groups for radio and checkbox choices. No scripts at all.

Determinism: every random decision flows from the rng passed to generate().
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, register


def _explain(purpose, approach, key_points, big_o_time, big_o_space, edge_cases):
    return {
        "purpose": purpose,
        "approach": approach,
        "key_points": key_points,
        "big_o_time": big_o_time,
        "big_o_space": big_o_space,
        "edge_cases": edge_cases,
    }


def _slug(label: str) -> str:
    return label.lower().replace(" ", "-").replace("'", "")


class HtmlSemanticPagesFamily(Family):
    """Full doctype documents with header/nav/main/article/footer structure."""
    NAME = "html_semantic_pages"
    LANGUAGE = "html"
    DOMAIN = "web"
    DIFFICULTIES = ("beginner", "intermediate")
    SUPPORTS = ("explanation",)

    SITES = (
        ("bakery", "Golden Crumb Bakery", ["Menu", "Ordering", "Story"],
         "Small-batch sourdough and seasonal pastries.",
         "The morning bake list changes with the seasons.",
         "Fresh rye loaves cooling on the rack"),
        ("portfolio", "Studio Nara", ["Work", "Process", "Contact"],
         "Editorial design for independent publishers.",
         "Every project starts with a paper prototype.",
         "Spread layouts pinned to the studio wall"),
        ("library", "Fern Hollow Library", ["Catalogue", "Events", "Membership"],
         "A neighbourhood lending library run by volunteers.",
         "Story hour fills the back room every Saturday.",
         "The reading room under the old oak shelves"),
        ("clinic", "Riverside Clinic", ["Services", "Team", "Visits"],
         "Primary care with same-week appointments.",
         "Nurse practitioners staff the walk-in desk.",
         "Reception desk at the riverside entrance"),
        ("workshop", "Cedar Joinery Works", ["Courses", "Tools", "Bookings"],
         "Weekend woodworking classes for adults.",
         "Class size is capped at eight benches.",
         "The bench room mid-way through a course"),
    )

    SENTENCES = (
        "Opening hours are listed below and updated each season.",
        "Visitors can reach the front desk by phone or the contact form.",
        "Accessibility is a standing agenda item at every planning meeting.",
        "Pricing pages list concessions alongside the standard rates.",
        "A short newsletter summarises what changed each month.",
        "Directions by bicycle and public transport are posted at the door.",
    )

    def generate(self, rng: random.Random) -> Candidate:
        kind, brand, labels, tagline, blurb, img_alt = rng.choice(self.SITES)
        n_sections = rng.randint(2, 3)
        labels = labels[:n_sections]
        year = rng.choice([2023, 2024, 2025])
        sentence = rng.choice(self.SENTENCES)
        aside_note = rng.choice(
            ["Gift vouchers are available at the counter.",
             "Follow the noticeboard for schedule changes.",
             "Volunteers keep the space running every week."])

        nav_items = "\n".join(
            f'        <li><a href="#{_slug(lbl)}">{lbl}</a></li>'
            for lbl in labels)
        sections_html = []
        for idx, lbl in enumerate(labels):
            slug = _slug(lbl)
            figure = (
                f'      <figure>\n'
                f'        <img src="images/{slug}.jpg" alt="{img_alt}">\n'
                f'        <figcaption>{img_alt}</figcaption>\n'
                f'      </figure>\n') if idx == 0 else ""
            sections_html.append(
                f'    <article id="{slug}">\n'
                f'      <h2>{lbl}</h2>\n'
                f'      <p>{blurb} {sentence}</p>\n'
                f'{figure}'
                f'    </article>\n')
        body_sections = "\n".join(s.rstrip("\n") for s in sections_html)
        doc = (
            f'<!DOCTYPE html>\n'
            f'<html lang="en">\n'
            f'<head>\n'
            f'  <meta charset="utf-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'  <title>{brand}</title>\n'
            f'</head>\n'
            f'<body>\n'
            f'  <header id="top">\n'
            f'    <h1>{brand}</h1>\n'
            f'    <p class="tagline">{tagline}</p>\n'
            f'    <nav aria-label="Primary">\n'
            f'      <ul>\n{nav_items}\n      </ul>\n'
            f'    </nav>\n'
            f'  </header>\n'
            f'  <main>\n{body_sections}\n'
            f'    <section id="notice">\n'
            f'      <h2>Notice board</h2>\n'
            f'      <p>{aside_note}</p>\n'
            f'    </section>\n'
            f'  </main>\n'
            f'  <aside aria-label="Related information">\n'
            f'    <h2>Good to know</h2>\n'
            f'    <p>{sentence}</p>\n'
            f'  </aside>\n'
            f'  <footer>\n'
            f'    <p><small>&copy; {year} {brand}. All rights reserved.</small></p>\n'
            f'    <p><a href="#top">Back to top</a></p>\n'
            f'  </footer>\n'
            f'</body>\n'
            f'</html>\n')
        task = (f"Build a complete semantic HTML5 page for '{brand}' ({kind}). "
                f"The document must include the doctype, lang attribute, charset "
                f"and viewport meta tags, a header with the site title and a nav "
                f"list linking to the {', '.join(labels)} sections plus a notice "
                f"board section inside main, an aside with extra information, and "
                f"a footer with a back-to-top link. Every anchor needs a matching "
                f"id, the image needs descriptive alt text, and no inline event "
                f"handlers or external scripts may appear.")
        expected = ("A strictly balanced, script-free document where the nav "
                    "anchors jump to their sections, the figure is described by "
                    "alt and figcaption, and the footer closes the page.")
        return Candidate(
            family=self.NAME, language="html", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected,
            code=doc, verify_method="static_check",
            notes={"explain": _explain(
                expected,
                "Landmark elements carry the page skeleton: header wraps title "
                "and nav, main holds the article/section content, aside and "
                "footer finish the document.",
                ["one h1 followed by section-level h2 elements keeps the "
                 "outline logical for screen readers",
                 "anchor hrefs target element ids, so navigation works without "
                 "any JavaScript",
                 "the img pairs alt text with a figcaption, giving two levels "
                 "of description",
                 "aria-label on nav and aside disambiguates multiple landmarks"],
                "O(n) in the number of sections being rendered", "O(n)",
                ["a single-section page still renders a complete nav and footer",
                 "the notice section is always present even when the site has "
                 "only two content sections",
                 "every anchor target id exists exactly once in the document"])},
            tags=["html", "semantic", kind], variant=kind,
            seed=rng.randrange(2 ** 31))


class HtmlFormsA11yFamily(Family):
    """Accessible forms: label/for pairs, fieldset groups, no inline handlers."""
    NAME = "html_forms_a11y"
    LANGUAGE = "html"
    DOMAIN = "web"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "code_review")

    FIELD_POOL = (
        ("text", "Full name", "fullname"),
        ("email", "Email address", "email"),
        ("tel", "Phone number", "phone"),
        ("url", "Website", "website"),
        ("number", "Requested quantity", "quantity"),
        ("date", "Preferred start date", "start_date"),
        ("password", "Account password", "password"),
    )
    RADIO_GROUPS = (
        ("contact_method", "Preferred contact method",
         [("method-email", "Email"), ("method-phone", "Phone call"),
          ("method-post", "Postal mail")]),
        ("ticket_tier", "Ticket tier",
         [("tier-standard", "Standard"), ("tier-supporter", "Supporter"),
          ("tier-student", "Student")]),
        ("visit_slot", "Visit slot",
         [("slot-morning", "Morning"), ("slot-afternoon", "Afternoon"),
          ("slot-evening", "Evening")]),
    )
    CHECK_GROUPS = (
        ("interests", "Interests",
         [("interests-news", "Newsletter"), ("interests-events", "Events"),
          ("interests-volunteering", "Volunteering")]),
        ("topics", "Topics to follow",
         [("topics-updates", "Product updates"), ("topics-tips", "Tips"),
          ("topics-research", "Research notes")]),
    )

    def generate(self, rng: random.Random) -> Candidate:
        purpose = rng.choice(["signup", "booking", "feedback", "membership"])
        form_id = f"{purpose}-form"
        heading = rng.choice(["Join the programme", "Reserve your place",
                              "Send us your details", "Create an account"])
        fields = rng.sample(self.FIELD_POOL, rng.randint(2, 4))
        radio_name, radio_legend, radio_opts = rng.choice(self.RADIO_GROUPS)
        check_name, check_legend, check_opts = rng.choice(self.CHECK_GROUPS)
        required_pick = rng.randint(0, len(fields) - 1)

        field_html = []
        for idx, (ftype, label, name) in enumerate(fields):
            required = " required" if idx == required_pick else ""
            extra = ""
            if ftype == "text":
                extra = ' autocomplete="name"'
            elif ftype == "email":
                extra = ' autocomplete="email"'
            field_html.append(
                f'      <div class="field">\n'
                f'        <label for="{name}">{label}</label>\n'
                f'        <input type="{ftype}" id="{name}" name="{name}"{required}{extra}>\n'
                f'      </div>')
        radio_html = "\n".join(
            f'        <div class="choice">\n'
            f'          <input type="radio" id="{opt_id}" name="{radio_name}" '
            f'value="{opt_id.rsplit("-", 1)[1]}"'
            f'{" checked" if i == 0 else ""}>\n'
            f'          <label for="{opt_id}">{opt_label}</label>\n'
            f'        </div>'
            for i, (opt_id, opt_label) in enumerate(radio_opts))
        check_html = "\n".join(
            f'        <div class="choice">\n'
            f'          <input type="checkbox" id="{opt_id}" name="{check_name}[]" '
            f'value="{opt_id.rsplit("-", 1)[1]}">\n'
            f'          <label for="{opt_id}">{opt_label}</label>\n'
            f'        </div>'
            for opt_id, opt_label in check_opts)
        cta = rng.choice(["Submit", "Send request", "Save details",
                          "Complete sign-up"])
        doc = (
            f'<!DOCTYPE html>\n'
            f'<html lang="en">\n'
            f'<head>\n'
            f'  <meta charset="utf-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'  <title>{heading}</title>\n'
            f'</head>\n'
            f'<body>\n'
            f'  <main>\n'
            f'    <h1>{heading}</h1>\n'
            f'    <p>All fields marked required must be filled in before the '
            f'form can be submitted.</p>\n'
            f'    <form id="{form_id}" action="/{purpose}/submit" method="post">\n'
            f'{chr(10).join(field_html)}\n'
            f'      <fieldset>\n'
            f'        <legend>{radio_legend}</legend>\n'
            f'{radio_html}\n'
            f'      </fieldset>\n'
            f'      <fieldset>\n'
            f'        <legend>{check_legend}</legend>\n'
            f'{check_html}\n'
            f'      </fieldset>\n'
            f'      <div class="field">\n'
            f'        <label for="message">Message</label>\n'
            f'        <textarea id="message" name="message" rows="4"></textarea>\n'
            f'      </div>\n'
            f'      <button type="submit">{cta}</button>\n'
            f'    </form>\n'
            f'  </main>\n'
            f'</body>\n'
            f'</html>\n')
        task = (f"Build an accessible HTML form page for a {purpose} flow. The "
                f"form must carry an id and a post action; every input needs a "
                f"label connected through for/id; the radio and checkbox groups "
                f"must each sit inside a fieldset with a legend, and every "
                f"checkbox or radio input must have its own id. Use native input "
                f"types ({', '.join(sorted(set(f[0] for f in fields)))}), mark "
                f"the required field with the required attribute, close with a "
                f"submit button, and never use inline event handlers or external "
                f"scripts.")
        expected = ("A strictly balanced, script-free form where screen readers "
                    "announce every field through its label, radio and checkbox "
                    "groups are grouped under their legends, and submission uses "
                    "a real button element.")
        return Candidate(
            family=self.NAME, language="html", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected,
            code=doc, verify_method="static_check",
            notes={"explain": _explain(
                expected,
                "Group related inputs in fieldsets with legends, bind labels to "
                "inputs via for/id, and rely on native input semantics instead "
                "of scripted widgets.",
                ["label for/id association makes every control announce its "
                 "name, including checkboxes and radios",
                 "fieldset/legend gives grouped choices a shared accessible "
                 "name, so context survives when the legend scrolls away",
                 "native types bring free keyboard support, validation hints "
                 "and autocomplete behaviour",
                 "the submit button keeps the form functional without any "
                 "JavaScript"],
                "O(n) in the number of form controls rendered", "O(n)",
                ["a form with one field still wraps it in the same labelled "
                 "structure",
                 "the first radio option is pre-selected so the group never "
                 "ships in an unanswerable state",
                 "the message textarea is optional and still fully labelled"])},
            tags=["html", "forms", "a11y", purpose], variant=purpose,
            seed=rng.randrange(2 ** 31))

    def review_variant(self, rng: random.Random):
        """Working but accessibility-flawed form for review practice."""
        fields = rng.sample(self.FIELD_POOL, 2)
        (ftype1, label1, name1), (ftype2, label2, name2) = fields
        flawed = (
            f'<!DOCTYPE html>\n'
            f'<html lang="en">\n'
            f'<head>\n'
            f'  <meta charset="utf-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'  <title>Quick signup</title>\n'
            f'</head>\n'
            f'<body>\n'
            f'  <main>\n'
            f'    <h1>Quick signup</h1>\n'
            f'    <form id="quick-signup" action="/signup/submit" method="post">\n'
            f'      <p>{label1}</p>\n'
            f'      <input type="{ftype1}" id="{name1}" name="{name1}" required>\n'
            f'      <p>{label2}</p>\n'
            f'      <input type="{ftype2}" id="{name2}" name="{name2}">\n'
            f'      <input type="radio" name="contact_method" value="email" '
            f'id="contact-email">\n'
            f'      <p>Email updates</p>\n'
            f'      <input type="radio" name="contact_method" value="post" '
            f'id="contact-post">\n'
            f'      <p>Postal updates</p>\n'
            f'      <button type="submit">Join</button>\n'
            f'    </form>\n'
            f'  </main>\n'
            f'</body>\n'
            f'</html>\n')
        cand = Candidate(
            family=self.NAME, language="html", domain=self.DOMAIN,
            difficulty="intermediate",
            task="Review this signup page for accessibility problems before it "
                 "ships. The form submits correctly today, but the team wants "
                 "the label associations, grouping semantics and heading "
                 "structure checked against WCAG basics.",
            expected_behavior="The form submits; the review targets labelling "
                              "and grouping semantics, not behaviour.",
            code=flawed, verify_method="static_check",
            notes={"explain": _explain(
                "A signup form whose controls are unlabelled and whose radio "
                "pair is ungrouped.",
                "Placeholders-in-paragraphs stand in for labels and the radio "
                "group sits bare in the form.",
                ["the form still submits because it uses a real button and a "
                 "post action",
                 "every control does have an id, so fixing labels is a "
                 "mechanical change",
                 "input types remain native, keeping keyboard behaviour intact"],
                "O(n) in the number of controls", "O(n)",
                ["screen readers announce the text inputs as unnamed fields",
                 "the radio pair reads as two unrelated controls without a "
                 "group name"])},
            tags=["html", "forms", "a11y", "review"],
            variant="signup|review", seed=rng.randrange(2 ** 31))
        issues = [
            {"kind": "a11y", "severity": "high",
             "why": "text inputs have no label element bound via for/id, so "
                    "screen readers announce them with no accessible name",
             "better": "wrap each prompt in <label for=...> targeting the "
                       "input's id"},
            {"kind": "a11y", "severity": "high",
             "why": "the radio pair is not wrapped in a fieldset/legend, so "
                    "users never hear that the two options are one question",
             "better": "group them in <fieldset><legend>Contact method</legend>"
                       "</fieldset> with labels per option"},
            {"kind": "a11y", "severity": "medium",
             "why": "visual-only prompts in <p> elements break down as soon as "
                    "styling is removed or a reader navigates by form controls",
             "better": "replace the <p> prompts with real labels tied to the "
                       "controls they describe"},
        ]
        return cand, issues


class HtmlDataTablesFamily(Family):
    """Data tables with caption, scoped th headers, thead/tbody/tfoot."""
    NAME = "html_data_tables"
    LANGUAGE = "html"
    DOMAIN = "web"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation",)

    DATASETS = (
        ("rainfall", "Monthly rainfall", ["Month", "Rainfall (mm)"],
         [("January",), ("February",), ("March",)], "mm"),
        ("roster", "Squad roster", ["Player", "Position", "Goals"],
         [("Harper", "Forward"), ("Quinn", "Midfield"), ("Riley", "Defender"),
          ("Sable", "Goalkeeper")], "goals"),
        ("inventory", "Server inventory", ["Hostname", "Cores", "Memory (GB)"],
         [("edge-01", "4"), ("edge-02", "4"), ("db-01", "8"), ("db-02", "8")],
         "GB"),
        ("library", "Top borrowed titles", ["Title", "Author", "Loans"],
         [("The Lark Line", "E. Moreau"), ("Salt Roads", "T. Ihara"),
          ("Paper Compass", "J. Okafor")], "loans"),
    )

    def generate(self, rng: random.Random) -> Candidate:
        key, title, columns, base_rows, unit = rng.choice(self.DATASETS)
        year = rng.choice([2023, 2024, 2025])
        caption = f"{title} for {year}"
        num_col_idx = len(columns) - 1  # last column is numeric

        rows_html = []
        numeric_total = 0
        for row in base_rows:
            cells = list(row)
            value = rng.randint(1, 99)
            numeric_total += value
            cells.append(str(value))
            row_cells = "\n".join(
                f'          <td>{c}</td>' for c in cells[1:])
            rows_html.append(
                f'        <tr>\n'
                f'          <th scope="row">{cells[0]}</th>\n'
                f'{row_cells}\n'
                f'        </tr>')
        body_rows = "\n".join(rows_html)
        head_cells = "\n".join(
            f'          <th scope="col">{col}</th>' for col in columns)
        foot_label_span = len(columns) - 1
        foot_label = (f"Total {unit} recorded in {year}"
                      if foot_label_span == 1 else
                      f"Combined {unit} across {len(base_rows)} rows")
        if foot_label_span == 1:
            foot_row = (
                f'          <th scope="row">{foot_label}</th>\n'
                f'          <td>{numeric_total}</td>')
        else:
            foot_row = (
                f'          <th scope="row" colspan="{foot_label_span}">'
                f'{foot_label}</th>\n'
                f'          <td>{numeric_total}</td>')
        doc = (
            f'<!DOCTYPE html>\n'
            f'<html lang="en">\n'
            f'<head>\n'
            f'  <meta charset="utf-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'  <title>{title}</title>\n'
            f'</head>\n'
            f'<body>\n'
            f'  <main>\n'
            f'    <h1>{title}</h1>\n'
            f'    <p>Figures are recorded in {unit}. The footer row sums the '
            f'numeric column.</p>\n'
            f'    <table>\n'
            f'      <caption>{caption}</caption>\n'
            f'      <thead>\n'
            f'        <tr>\n{head_cells}\n        </tr>\n'
            f'      </thead>\n'
            f'      <tbody>\n{body_rows}\n      </tbody>\n'
            f'      <tfoot>\n'
            f'        <tr>\n{foot_row}\n        </tr>\n'
            f'      </tfoot>\n'
            f'    </table>\n'
            f'  </main>\n'
            f'</body>\n'
            f'</html>\n')
        col_list = ", ".join(columns)
        task = (f"Build an accessible HTML data table page titled '{title}'. The "
                f"table needs a caption reading '{caption}', a thead row whose "
                f"cells are th scope=col for the columns {col_list}, a tbody "
                f"where each row opens with a th scope=row entry name, and a "
                f"tfoot summary that totals the numeric column ({numeric_total} "
                f"in this dataset). Wrap the table in main with a short "
                f"introductory paragraph and keep the document script-free with "
                f"balanced tags throughout.")
        expected = (f"A captioned table where column headers use th scope=col, "
                    f"row headers use th scope=row, and the tfoot reports the "
                    f"sum {numeric_total} for the numeric column.")
        return Candidate(
            family=self.NAME, language="html", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected,
            code=doc, verify_method="static_check",
            notes={"explain": _explain(
                expected,
                "Semantic table structure: caption first, scoped headers in "
                "thead, row headers per body row, and a summary footer row.",
                ["th scope=col and scope=row let screen readers announce each "
                 "cell against its correct header",
                 "the caption sits inside the table so it stays bound to it "
                 "when the page is excerpted",
                 "tfoot gives assistive tech a stable summary row even before "
                 "the body finishes reading"],
                "O(rows * columns) cells rendered", "O(rows * columns)",
                ["a one-column numeric table still renders thead, tbody and "
                 "tfoot correctly",
                 "the footer total is precomputed, so no scripting is needed",
                 "every row keeps the same cell count as the header row"])},
            tags=["html", "tables", key], variant=key,
            seed=rng.randrange(2 ** 31))


register(globals(), HtmlSemanticPagesFamily)
register(globals(), HtmlFormsA11yFamily)
register(globals(), HtmlDataTablesFamily)
