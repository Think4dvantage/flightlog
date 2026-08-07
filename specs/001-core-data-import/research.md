# Research: Core Data & Excel Import

Findings from inspecting `olddata/Flugbuch.xlsx` directly (via `openpyxl`, both `data_only=True` for
values and `data_only=False` for formulas) rather than trusting only the prose in
`.ai/context/architecture.md`. Confirms and sharpens that document; does not contradict it.

## Workbook structure (confirmed)

Sheets: `Übersicht` (summary), `Flugbuch` (600 flight rows, the import source), `Fitnessprogramm`,
`Groundhandling`, `Tandemflüge`, `Ziele` (all four v0.5, out of scope here), `DropDownData` (master
lists: 34 launches, 30 landings, 12 categories, 10 gliders, 8 harnesses — the closed reference sets the
aliaser normalizes source values onto).

`Flugbuch` columns, confirmed by direct read: `Datum, Startplatz, Höhe Startplatz, Landeplatz,
Höhe Landeplatz, Höhe diff., Flugzeit, Distanz, Kategorie, Max Alt, Altgain, Schirm, Gurtzeug, Startart,
Kommentar`. 600 data rows (row 2–601). `Datum` is a plain date with no time component — confirms "no
time-of-day on any flight" from `architecture.md`.

## Decision: region mapping is reconstructed from formulas, not read as data

- **Decision**: The workbook has no `region` column anywhere. `Übersicht`'s "Flight Area" block (12
  named regions, e.g. `Interlaken`, `Mürren`, `Adelboden-Lenk`) is itself a formula:
  `=SUM(C36,C37,C38,...)`, each addend a cell reference into the "Launch Statistics" block a few dozen
  rows above, where column A holds the actual launch-site name. The site→region mapping only exists
  implicitly, as *which row numbers a region's SUM formula references*. `core/aliases.py` will carry a
  `SITE_REGION` dict, hand-transcribed once from those formulas, as static data — not re-parsed from the
  workbook at import time.
- **Rationale**: Regions are a closed, essentially frozen set (they haven't changed since 2018). Parsing
  formula ASTs at import time to reconstruct the mapping on every run would be far more code for zero
  ongoing benefit — this is exactly the kind of one-time transcription the aliaser pattern exists for.
- **The known 596-vs-600 discrepancy has a confirmed root cause, not just a confirmed symptom** —
  refined during implementation once every region's formula was checked across every column, not just
  Interlaken's Total column: three launch rows (`Ober Burgfeldstand`, `Lauberhorn`, `Alp Unterburgfeld`)
  were added to the "Launch Statistics" block after the workbook's initial version. Two of them
  (`Ober Burgfeldstand` row 67, `Alp Unterburgfeld` row 69) were folded into every **yearly** column's
  Interlaken SUM formula but never into the Total column's; the third (`Lauberhorn`, row 68) was folded
  into the yearly Grindelwald formulas the same way. A fourth site, `Fiescheralp` (row 65), is
  genuinely unreferenced by any region formula in any column — checked exhaustively.
  `core/aliases.py`'s `SITE_REGION` is built from the more complete yearly formulas, so the importer's
  region reconciliation (FR-015) does **not** reproduce a flat "4 flights missing" — it reports
  `Interlaken` and `Grindelwald` computed *higher* than the stale Total column, and `Fiescheralp`'s one
  flight as a residual gap. See `architecture.md`'s Statistics section for the exact numbers this
  produces against the real workbook.

## Decision: generic per-account category seeding is out of scope for v0.2

- **Decision**: `users.seeded_at`-guarded generic category seeding (mentioned in `02-backend-conventions.md`
  as running from the register path) is not built out in this feature. The importer creates this pilot's
  real 12 categories (`Abgleiter`, `Bruchflug`, `Flugschule`, `Grundkurs`, `Hike&Fly`, `Prüfung`,
  `Schwarzflug`, `SiKu`, `Soaring`, `Startleiter`, `Thermikflug`, `XC`) directly against the one existing
  account.
- **Rationale**: There is exactly one pilot account, and it is getting its real categories from the
  import. A generic starter set only matters once self-registration is live (v0.8, currently flagged
  off) — building it now is designing for a hypothetical signup that cannot happen yet, which the
  constitution's minimal-scope principle rules out. The `seeded_at` column and its guard already exist
  from v0.1 and are left as reserved plumbing; nothing in v0.2 sets it.
- **Alternatives considered**: Seed a generic set now and have the importer merge into it. Rejected —
  it's speculative work with no consumer, and a merge step is exactly the kind of accidental-duplicate
  risk the idempotency requirement (FR-012) is trying to eliminate elsewhere.

## Decision: `openpyxl` pin is still current

- **Decision**: Keep `openpyxl (>=3.1.5,<4.0.0)`, already declared as the `importer` extra in
  `pyproject.toml`.
- **Rationale**: Verified against the PyPI JSON API directly (`https://pypi.org/pypi/openpyxl/json`) on
  2026-08-06: latest is `3.1.5`, matching the existing pin exactly. No drift to fix.

## Decision: `import_key` is `"xlsx:<row>"`, using openpyxl's own row index

- **Decision**: The dry-run/write importer reads `Flugbuch` with `openpyxl`'s `iter_rows`, and uses the
  1-based sheet row number (2–601) as the row identity baked into `import_key`.
- **Rationale**: `architecture.md` already establishes row order as the only stable identity, since date
  is not unique (117 multi-flight days) and there is no other natural key. Using the literal sheet row
  number rather than a recomputed 0-based counter means the key is stable even if a future re-import run
  reads the sheet with different pagination/batching logic — it's tied to a physical row, not an
  iteration index.

## Decision: buddy-name proposals use a simple name-matching pass over `Kommentar`, not NLP

- **Decision**: FR-017's buddy proposals come from matching known first names / nicknames (a small,
  pilot-maintained list, not a general named-entity recognizer) against the free-text `Kommentar` column,
  case-insensitively, word-boundary matched.
- **Rationale**: 600 rows of German free text from one person is not a corpus that justifies an NLP
  dependency. A maintained name list is auditable, has zero false-positive risk from unrelated words, and
  the pilot is the one who will review and accept/reject every proposal anyway (per the spec's
  acceptance criteria — proposals are never auto-created).
- **Alternatives considered**: A general NLP/NER library. Rejected as disproportionate to the input size
  and against the "don't design for hypothetical future requirements" principle — this project has no
  other use for NLP.
