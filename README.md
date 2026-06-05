# german-tax-analyzer

Turn your German income-tax documents into a clear, verified report. Drop in the declaration
you filed and the assessment (**Steuerbescheid**) you got back from the Finanzamt, ask Claude
to analyze them, and get an interactive `report.html` that shows — figure by figure, every
number re-checked in code — what you declared, what the Finanzamt accepted, what changed, and
why.

> ⚠️ Educational and analytical only — **not** tax or legal advice. Any translations are uncertified.

## What you need

- **[Claude Code](https://claude.com/claude-code)**
- **Python 3.8+** with two libraries — and, only for *scanned* PDFs, **OCRmyPDF** with the German pack.

**macOS (Homebrew):**

```bash
brew install python ocrmypdf tesseract-lang   # tesseract-lang adds the German pack
pip3 install pypdf jsonschema
```

## How to use

### 1. Add your documents

Create the tax-year folder and put your PDFs in its `source/`:

```bash
mkdir -p 2024/source
```

Copy in **the declaration you submitted** and **the Bescheid you received** from the Finanzamt, e.g.:

```
2024/source/2024_declaration.pdf   ← what you filed
2024/source/2024_bescheid.pdf      ← what the Finanzamt sent back
```

### 2. Start Claude in the project root

```bash
claude
```

### 3. Ask Claude to analyze

Just describe it in plain language — name the year and the documents. For example:

> Analyze my 2024 taxes. I put the declaration I filed and the Steuerbescheid I received from
> the Finanzamt in `2024/source/`. Compare what I declared against what they accepted, verify
> every figure, and build the report.

Other things you can ask:

- "Why is my refund smaller than I expected?"
- "An Änderungsbescheid arrived — drop it in `2024/source/` and tell me what changed and what I owe now."
- "Is there a basis for an Einspruch, and what's the deadline?"

### 4. Open your report

Claude saves two files in the year folder:

- `2024/2024_facts.json` — the extracted, verified data, and
- `2024/2024_report.html` — an interactive, self-contained report.

Open the report in any browser (no dependencies, works offline):

```bash
open 2024/2024_report.html
```

## Project structure

Everything is organized **by tax year**. The shared tooling lives under `.claude/`; your
private documents and the generated outputs live in each `<year>/` folder.

```
german-tax-analyzer/
├── README.md            ← you are here
├── CLAUDE.md            ← the full analysis workflow Claude follows
├── .claude/
│   ├── skills/
│   │   ├── de-tax-analyzer/      ← the workflow + shared tooling
│   │   │   ├── scripts/          ← pdf_triage.py, reconcile.py
│   │   │   └── references/       ← facts.schema.json, intake.md
│   │   └── de-tax-legal-check/   ← § citation / statutory-amount verifier
│   └── agents/tax-verifier.md    ← independent calculation-audit subagent
└── <year>/              ← e.g. 2024/
    ├── source/          ← your declaration + Bescheid PDFs
    ├── <year>_facts.json            ← extracted, verified data
    └── <year>_report.html           ← the interactive report
```

Your `<year>/` folders are git-ignored — **personal tax data is never published.** Only the
reusable tooling and the empty `20xx/` example structure are tracked.

## How it works

When you ask, Claude follows the workflow in **[`CLAUDE.md`](CLAUDE.md)**: it triages and (if
needed) OCRs each PDF, extracts a structured `facts.json`, **re-checks every number in
executable code**, compares declared vs accepted, flags anything disputable together with its
legal basis, and renders the report. It never invents tax law, citations, or figures, and it
states its confidence. The full, authoritative rules — including the figure-verification and
derived-figure reconciliation guardrails — live in `CLAUDE.md`.
