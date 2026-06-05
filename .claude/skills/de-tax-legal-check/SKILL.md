---
name: de-tax-legal-check
description: Verify the German tax-law facts behind an Einkommensteuerbescheid analysis against primary sources before they enter a facts.json or report — § citations (EStG/AO/SolzG), the year-specific Grundfreibetrag (§32a), Sparer-Pauschbetrag, Solidaritätszuschlag-Freigrenze, the §33a Unterhalts-Höchstbetrag with its Ländergruppeneinteilung quarters, the Homeoffice-Tagespauschale rate/cap, and child allowances (Kinderfreibetrag/Kindergeld). Use whenever a German tax analysis cites a paragraph or a statutory amount, or asserts a year-specific threshold, so nothing is invented or stale. Companion to de-tax-analyzer.
---

# DE-Tax Legal Check

Enforce the "never invent tax law" rule with evidence. German tax thresholds change almost every year (Grundfreibetrag, Soli-Freigrenze, Sparer-Pauschbetrag, Tagespauschale, Unterhalts-Höchstbetrag), and § citations must match exactly. Confirm each against a primary source for the **specific tax year** before it goes into `facts.json` or a report.

## When to run

Run before finalizing Step 5 (Legal Analysis) and before any report ships, on:
- every `legal_references[]` citation and every `legal_basis` on a line_item/adjustment;
- every statutory **amount** the Bescheid applies that you state as a rule (not just as "printed"): Grundfreibetrag, Splitting doubling, Sparer-Pauschbetrag (1.000 € single / 2.000 € joint), Soli-Freigrenze, §33a Höchstbetrag and the Ländergruppe fraction, Tagespauschale (€/day and annual cap), Entfernungspauschale (€/km), Kinderfreibetrag and Kindergeld per child.

## How to verify

1. **Identify the tax year.** Thresholds are year-specific — a 2023 figure is wrong for 2024. Pin every check to the document's Veranlagungszeitraum.
2. **Search primary sources first** (priority order): Grundgesetz → Abgabenordnung (AO) → Einkommensteuergesetz (EStG) → EStR → BMF guidance → BFH decisions → reputable secondary commentary. Use `WebSearch`/web fetch on `gesetze-im-internet.de` (statute text), `bundesfinanzministerium.de` (BMF, Ländergruppeneinteilung, official tables), and `bzst.de`. Prefer the statute/BMF over blogs.
3. **For the Ländergruppeneinteilung** (the §33a foreign-maintenance cap), find the BMF letter in force for that year and read the country's group (1–4 → full / ¾ / ½ / ¼ of the Höchstbetrag). Example shape: 2024 Höchstbetrag 11.784 €; group 4 → ¼ → 2.946 €.
4. **Record the finding** for each item: cite Law · Section · the verified value/text · the source URL · the year it applies to · a confidence (High = explicit statute/BMF; Medium = likely; Low = uncertain). Put confirmed citations into `legal_references[]`; put any you could NOT confirm into `open_questions` and mark the related `confidence` Low — never upgrade an unverified citation.
5. **Do not invent.** If no reliable source confirms a citation or amount, write "No reliable legal citation identified" / "could not verify the YYYY value" rather than guessing. A plausible-looking § is still wrong if unverified.

## Output

A short verification table the analyst can paste into `facts.json`/the report:

```
Item · Year · Claimed · Verified value/citation · Source (URL) · Confidence
§33a Höchstbetrag (Tajikistan) · 2024 · 2.946 € · 11.784 € ÷ 4 (Ländergruppe 4) · BMF Ländergruppeneinteilung 2024 + §33a EStG · High
Soli-Freigrenze (Zusammenveranlagung) · 2024 · 36.260 € · … · SolzG §3 / BMF · …
```

Flag any mismatch between what the Bescheid applied and the verified value as a `validation_flag` (it may be a genuine FA error — or your figure may be stale; say which).

## Boundary

This skill verifies the *law and statutory amounts*. It does not recompute the assessment arithmetic — that is the analyzer's Step 3 and the `tax-verifier` subagent. Output remains educational, not legal advice.
