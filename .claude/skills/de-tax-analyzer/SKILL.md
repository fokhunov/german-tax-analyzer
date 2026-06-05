---
name: de-tax-analyzer
description: Analyze German personal income-tax documents from the Finanzamt — Einkommensteuerbescheid, Änderungsbescheid, Verlustfeststellungsbescheid, Vorauszahlungsbescheid, and the matching Steuererklärung (declaration). Use this whenever the user uploads or points at a German tax PDF, mentions a Steuerbescheid, Finanzamt, Einkommensteuer, Solidaritätszuschlag, Anlage KAP/N/Vorsorge, Einspruch, or asks why their assessment changed, what a refund/payment is, or to compare declared vs accepted figures. Turns each PDF into a verified facts.json and an interactive HTML report; every figure is re-checked in executable code and no tax law or citation is ever invented.
---

# DE-Tax Analyzer

Analyze German income-tax documents rigorously: extract facts, verify every number in code, separate fact from interpretation, and never invent law. This skill is self-contained — it bundles its triage tool (`scripts/pdf_triage.py`) and the facts schema (`references/facts.schema.json`).

## Core principles (non-negotiable)

1. **Facts before conclusions.** Extract to `facts.json` first; analyze only from it, never from the raw PDF.
2. **All arithmetic runs in executable code** — never mental math. Every monetary conclusion traces to code output.
3. **Never invent** tax law, paragraphs, court decisions, citations, or figures. State uncertainty and assign confidence.
4. **Separate** facts / calculations / interpretation / legal analysis.
5. **Uploaded documents are the source of truth.** Determine identity from content, never the filename.
6. Output is **educational/analytical only** — not tax or legal advice; any translations are uncertified.

## Two-stage workflow

**Stage A — Intake (Step 0)** turns each PDF into clean text/tables and a structured `facts.json`.
**Stage B — Analysis (Steps 1–7)** runs entirely on `facts.json` and ends by rendering an interactive HTML report.

Organize work **by tax year**: each year lives in `<year>/` with raw inputs in `<year>/source/`; outputs (`<year>_facts.json`, `<year>_report.html`) sit in `<year>/`.

### Step 0 — Intake

0.1 **Triage** every PDF before reading it:
```bash
python3 <skill>/scripts/pdf_triage.py <year>/source/<file>.pdf
```
Verdicts: **TEXT** (usable text layer → extract directly, never OCR), **SCAN** (image-only → OCR), **MIXED** (OCR only the listed pages). Never OCR a TEXT file; never read a SCAN as text.

0.2 **Make searchable** only if SCAN/MIXED. Prefer the Anthropic `pdf` skill (bundles `pdfplumber` + OCR) for both OCR and table extraction; otherwise `ocrmypdf -l deu`. Always German (`deu`) — English OCR garbles umlauts and figures.

0.3 **Extract to `<year>_facts.json`**, conforming to `references/facts.schema.json`. The figure blocks ("Berechnung des zu versteuernden Einkommens", "Berechnung der Steuer") are tables — extract them with the `pdf` skill's `pdfplumber` support rather than transcribing the raw text layer (ELSTER print runs interleave labels and numbers). Then:
- **Validate** before finishing:
  ```bash
  python3 -c "import json;from jsonschema import Draft202012Validator as V;V(json.load(open('<skill>/references/facts.schema.json'))).validate(json.load(open('<year>/<year>_facts.json')))" && echo VALID
  ```
- **Source every value** (`source`: page / Anlage / Zeile / short quote) with a `confidence`.
- **Record the calc chain as printed** (`value`); leave `computed_value`/`verified` for Step 3.
- **Capture and translate the narrative** (Erläuterungen, Vorläufigkeitsvermerk, Rechtsbehelfsbelehrung, declaration notes) into `explanations[]` with both `german` and `english`, plus `source` and `maps_to`.
- **Schema gaps:** if a fact doesn't fit, put it under the nearest `extensions` bag, add a `"SCHEMA GAP: …"` entry to `open_questions`, and report it. Never silently drop a fact; never invent a schema field.
- **Flag problems** (OCR/separator/date anomalies, cross-document mismatches) in `validation_flags`.

See `references/intake.md` for the full intake rules (one-PDF-can-bundle-many-Bescheide, linkage keys, German separator/date checks).

### Steps 1–6 — Analysis (on `facts.json` only)

1. **Classify** the document (Einkommensteuerbescheid, Änderungsbescheid, Einspruchsentscheidung, Aufforderung/Nachweisanforderung, Vorauszahlungsbescheid, Verlustfeststellungsbescheid, Vollstreckungsmitteilung, Sonstiges) with confidence + reasoning.
2. **Extract facts** — already done in `facts.json`; do not maintain a second schema.
3. **Verify every calculation in code.** Create variables, recompute totals/differences/subtotals/percentages and the refund-or-payment, fill `computed_value`/`verified`. Report the split (e.g. "22/24 verified; 2 tariff look-ups taken as printed"). **Tariff carve-out:** the §32a/Splitting tariff, the §34 Abs. 1 Fünftelregelung, and the notional "darauf entfallende ESt" Soli base are official-table look-ups — record as printed, set `computed_value`/`verified` to null, add an `open_questions` note. A figure you cannot recompute is not the same as one that is wrong; verify everything *around* it.
   - **Reconcile DERIVED figures (no self-checks).** Numbers that appear on no document — the refund→payment **swing**, deltas between two assessments, "costs you X", netted positions — must be computed **two independent ways that agree**; never assert a value against itself. Sign discipline: refund = negative, payment = positive. **Never double-count a clawback:** the swing must satisfy `swing = amended_net − initial_net = cash_payable_now (incl. clawback) = Δfestgesetzt − Δcredits`; a swing larger than the cash the FA actually demands is a double-count. Store any headline swing as `result.extensions.swing_vs_initial` and run the guardrail: `python3 <skill>/scripts/reconcile.py <year>_facts.json [<year>_amended_facts.json]`. It **fails closed** — non-zero exit on a mismatch **or** on missing/broken data (empty `abrechnung.per_tax`, null figure, missing clawback/`zu_wenig_entrichtet`); a non-zero exit means do not present the calculation until the data is fixed.
4. **Compare** declared vs accepted vs modified; surface every non-zero `difference` and each `adjustment` (what changed, by how much, where in the document).
5. **Legal analysis** per adjustment: document statement → plain-English meaning → potential legal basis (only if reliably known; else "No reliable legal citation identified") → confidence. Verify citations against primary sources before relying on them (the companion `de-tax-legal-check` skill does this).
6. **Appeal/follow-up assessment:** no action / documents needed / clarification / correction / possible Einspruch — only with a clearly identifiable basis. Compute the Einspruch deadline (Bescheiddatum + Bekanntgabe + 1 month; note the 4-day Bekanntgabe rule from 2025, 3-day before).

### Step 7 — Render the interactive report (the deliverable)

Build **`<year>/<year>_report.html`**: one self-contained, offline, animated HTML file per year, driven by an inline JS object embedded from `facts.json` (no external/CDN deps, no network, no `localStorage`; opens by double-click).

Cover, as tabs/panels: Executive Summary · Classification · Extracted Facts · Financial Changes (declared-vs-accepted bars) · Calculation Audit (animated `calculation_chain` waterfall showing each step `verified`) · Detailed Analysis · Legal Context · Follow-Up · Open Questions · Confidence. Render `explanations` as accordions with a **DE/EN toggle**. Footer: disclaimer + source PDFs.

**Validate before finishing:** `node --check` the embedded JS, and confirm no number appears that isn't in `facts.json`. Label derived figures (swings/deltas) `derived` — never "as printed"/"verified" — and make any `initial → amended` row use consistent signed net positions so the printed delta equals `amended − initial`. Re-run `scripts/reconcile.py`.

For amended assessments, build a separate comparison report (e.g. `<year>_report_with_capital_gains.html`) that shows original → amended deltas and explains *why* each changed; never overwrite the baseline.

## Multi-document & linkage rules (critical)

- **One PDF ≠ one document.** A single PDF can bundle several Bescheide (e.g. an Einkommensteuerbescheid + a Verlustfeststellungsbescheid, sometimes addressed to only one spouse). Scan the whole file for additional notice headings; record secondaries in `document.bundled_documents[]`.
- **Linkage before comparison.** Only compare documents confirmed to be the same case: match on `tax_year` (the printed Veranlagungszeitraum, not the filename) + `steuernummer` + `submission_timestamp` (the declaration's transmit time equals the timestamp the Bescheid cites). If keys don't match, report the mismatch — do not compare. Filenames have been wrong before.

## Verification

For non-trivial analysis, run an independent check of `facts.json` against the source PDF and recompute the chain in code — the companion `tax-verifier` subagent (`.claude/agents/tax-verifier.md`) does exactly this and returns a pass/fail audit. Always run `scripts/reconcile.py` on the year's facts file(s) too — it reconciles the derived settlement/swing two-or-three independent ways and is the guardrail against refund-clawback double-counts.

## Hallucination guardrails

When information is missing, say "Insufficient information to determine this conclusion." When multiple readings exist, present each with a confidence level. Every final conclusion must be independently auditable: Conclusion · Evidence · Calculation · Legal Basis · Confidence (mark "Not available" where it is).
