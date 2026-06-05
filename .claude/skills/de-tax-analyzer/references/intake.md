# Intake reference — detailed rules

Read this during Step 0 when extracting a document to `facts.json`. The SKILL.md has the summary; this file has the edge cases that have bitten real documents.

## One PDF can bundle several Bescheide

ELSTER print runs routinely append extra notices after the Einkommensteuerbescheid — most commonly a `Verlustfeststellungsbescheid` (gesonderte Feststellung des verbleibenden Verlustvortrags, § 10d EStG), often addressed to only one spouse and with its own Rechtsbehelfsbelehrung. An Änderungsbescheid may also bundle a `Vorauszahlungsbescheid` (future-year prepayments) and an amended Verlustfeststellung.

During classification, scan the **whole** file for additional notice headings ("Bescheid über …", a fresh Rechtsbehelfsbelehrung, a new Form.-Nr.), not just page 1. Model the primary notice with `document.doc_type`; record each secondary in `document.bundled_documents[]` (doc_type, title, pages, addressee, legal_basis, key_values, source). Put headline figures where they belong too (e.g. a loss carryforward in a `verlust` line_item). Never silently drop a bundled notice; flag it in the intake summary.

## Linkage before comparison (mandatory)

Compare two documents only after confirming they are the same case. **Determine identity from content, never the filename.** Join only when these match:
- `tax_year` — the Veranlagungszeitraum printed inside, NOT the filename or issue year.
- `steuernummer`.
- `submission_timestamp` — the declaration's transmit time equals the timestamp the Bescheid cites ("Dieser Festsetzung habe ich Ihre Daten zugrunde gelegt, die mir am … übermittelt wurden"). If unavailable, fall back to tax_year + steuernummer and flag the weaker match.

Record the confirmed pairing in `linkage.related_documents` with `match_basis`. If the keys do NOT match, report the mismatch — do not compare. (A file once named `2023-declaration.pdf` was actually the 2022 return, identifiable only by its submission timestamp.)

## German monetary & date checks

- **Separators:** German uses `.` for thousands and `,` for decimals. Watch for OCR errors like `"1.500,00 €"` misread as `"15000 €"`. Where a value's raw string is ambiguous, store it in the line's `raw_value`.
- **Signs:** distinguish refund (Erstattung, money to taxpayer) from payment (Nachzahlung, money from taxpayer). A Bescheid's "verbleibende Steuer" is negative for a refund.
- **Settlement clawback:** an Änderungsbescheid adds back any refund already paid from the prior Bescheid, so its demand can exceed the pure tax increase. Do not present "amended result minus original result" as the impact — that double-counts the refund. Report net cash (received minus paid) and the tax increase separately.
- **Dates:** verify the issue date and any derived deadline are plausible. Einspruch deadline = Bescheiddatum + Bekanntgabe + 1 month. Bekanntgabe by ordinary post = 3rd day after posting through 2024; **4th day from 2025** onward (law change).
- **Citations:** capture each legal citation exactly as printed (e.g. `§ 9 EStG`, `§ 173 AO`); never normalize or invent.

## Confidence scoring

Assign separately and record in `confidence`:
- **OCR:** high (clean native text layer) / medium (minor extraction uncertainty) / low (scan issues, missing text, handwriting).
- **Calculation:** high (all figures verified) / medium (some inferred) / low (incomplete data).
- **Legal:** high (explicit, verified citation) / medium (likely interpretation) / low (uncertain basis).

If a figure cannot be read reliably, set the affected line's `confidence` to `low` and record the issue in `validation_flags`.
