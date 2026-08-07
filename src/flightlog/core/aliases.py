"""
Normalization tables for the Excel importer.

All of this is hand-transcribed, once, from `olddata/Flugbuch.xlsx`'s `DropDownData` sheet (the
34 launches / 30 landings / 12 categories / 10 gliders / 6 harnesses master lists) and its
`Übersicht` sheet's "Flight Area" SUM formulas (site-to-region mapping — see
specs/001-core-data-import/research.md). Every string below was verified byte-for-byte against a
direct `openpyxl` read of the real workbook, not copied from a summarized view — this file already
caught two of its own transcription typos that way (Möntschelenalp with ö not ü; Därstetten with ä
not ü) before landing.

Data, not inline conditionals, so the importer's dry-run report can enumerate hit counts per table
(FR-013). Every dict maps a source-data spelling variant to the canonical name from DropDownData. A
value that matches nothing here or in the canonical lists is reported as unresolved by the importer
— never guessed.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------------------
# Canonical master lists, verbatim from DropDownData. German source data — never translated.
# ---------------------------------------------------------------------------------------

CANONICAL_LAUNCHES = [
    "Amisbühl",
    "Axalp Windegg",
    "Bergbo",
    "Birg",
    "Breitlauenen",
    "Brienzer Rothorn",
    "Chalet",
    "Därstetten Geeristein",
    "Fiescheralp",
    "First",
    "Hohwald",
    "Jungfraujoch",
    "Luegibrüggli",
    "Marbachegg",
    "Metschstand",
    "Metschstand Bise",
    "Möntschelenalp",
    "Niederhorn",
    "Niesen",
    "Alp Oberburgfeld",
    "Pfingstegg",
    "Riggisalp",
    "Schiltgrat",
    "Schilthorn",
    "Schwandfeldspitz",
    "Sulegg",
    "Tschentenalp",
    "Weissenstein",
    "Wurmegg",
    "Männlichen",
    "First Oben",
    "Ober Burgfeldstand",
    "Lauberhorn",
    "Alp Unterburgfeld",
]

CANONICAL_LANDINGS = [
    "Adelboden Boden",
    "Adelboden Oey",
    "Adelboden Sportzentrum",
    "Beatenberg",
    "Blumenstein",
    "Brienz",
    "Därstetten",
    "Fiesch",
    "Flugplatz Inti",
    "Grindelwald Grund",
    "Höhenmatte",
    "Interlaken Ost",
    "Inti Kläranlage",
    "Lehn",
    "Lobhornhütte",
    "Marbach Talstation",
    "Metschbahn",
    "Mettlengasse8",
    "Oberdorf",
    "Ringgenberg Buechmätteli",
    "Schiltgrat",
    "Schwandfeldspitz",
    "Schwarzsee",
    "Spiez",
    "Stechelberg",
    "Suppenboden",
    "Unterseen im Bitz",
    "Vorsass",
    "Wilderswil Wydi",
    "Zweilütschinen",
]

CANONICAL_CATEGORIES = [
    "Abgleiter",
    "Bruchflug",
    "Flugschule",
    "Grundkurs",
    "Hike&Fly",
    "Prüfung",
    "Schwarzflug",
    "SiKu",
    "Soaring",
    "Startleiter",
    "Thermikflug",
    "XC",
]

CANONICAL_GLIDERS = [
    "(Dumbo) Advance Alpha 6 28",
    "(Ragnar) Advance Epsilon 9 28",
    "(SIMI) Advance Alpha 6 31",
    "Advance Alpha 5 31",
    "Advance Alpha 6 28",
    "Advance Epsilon 9 28",
    "GIN Atlas 2 M",
    "Nova ION 6 M",
    "(Sophie) Advance Epsilon 9 31",
    "(Margritli) Advance Epsilon DLS 31",
]

CANONICAL_HARNESSES = [
    "Advance Easyness 1",
    "Advance Easyness 2",
    "Advance Easyness 3",
    "Advance Lightness 3",
    "Advance Progress 3",
    "Advance Strapless",
]

# ---------------------------------------------------------------------------------------
# Spelling-variant aliases actually present in Flugbuch's 600 rows, found by direct,
# byte-verified inspection (research.md). Each key is a source value that does NOT
# exactly match its canonical list above; each value is the canonical name it resolves to.
# ---------------------------------------------------------------------------------------

SITE_ALIASES = {
    "BergBo": "Bergbo",
}

GLIDER_ALIASES = {
    "Gin Atlas 2 M": "GIN Atlas 2 M",
    "NOVA ION 6 M": "Nova ION 6 M",
}

HARNESS_ALIASES = {
    "Advance Easynes 3": "Advance Easyness 3",
}

CATEGORY_ALIASES: dict[str, str] = {}

# "Advance Success 2" (3 flights in the source) is deliberately absent from
# HARNESS_ALIASES — it is retired gear not in DropDownData's current master list, not a
# misspelling of anything there. The importer reports it as unresolved (FR-014); it must
# never be guessed onto the nearest canonical name.

# Flugbuch's "Startart" column: f = forward (default when blank), r = reverse. One row
# uses uppercase "F" — case-insensitive lookup handles it without a dedicated alias entry.
LAUNCH_TYPE_MAP = {
    "f": "forward",
    "r": "reverse",
}

# ---------------------------------------------------------------------------------------
# Category flags — is_hike_fly / is_training, per architecture.md's "flags, not string
# matching" rule.
# ---------------------------------------------------------------------------------------

CATEGORY_FLAGS = {
    "Abgleiter": {"is_hike_fly": False, "is_training": False},
    "Bruchflug": {"is_hike_fly": False, "is_training": False},
    "Flugschule": {"is_hike_fly": False, "is_training": True},
    "Grundkurs": {"is_hike_fly": False, "is_training": True},
    "Hike&Fly": {"is_hike_fly": True, "is_training": False},
    "Prüfung": {"is_hike_fly": False, "is_training": True},
    "Schwarzflug": {"is_hike_fly": False, "is_training": False},
    "SiKu": {"is_hike_fly": False, "is_training": True},
    "Soaring": {"is_hike_fly": False, "is_training": False},
    "Startleiter": {"is_hike_fly": False, "is_training": True},
    "Thermikflug": {"is_hike_fly": False, "is_training": False},
    "XC": {"is_hike_fly": False, "is_training": False},
}

# ---------------------------------------------------------------------------------------
# Site-to-region mapping, hand-transcribed from Übersicht's "Flight Area" SUM formulas —
# see research.md for the row-by-row derivation. Landings are not region-mapped in the
# source data; only launches get a region.
#
# The mapping below is reconstructed from the YEARLY columns (D through L), not the Total
# column (C) — the two disagree, and the yearly columns are the more complete, more
# recently maintained ones. When "Ober Burgfeldstand", "Lauberhorn" and "Alp
# Unterburgfeld" were added to the workbook, whoever maintained it updated every year's
# SUM formula to include the new launch rows but forgot the Total column, which still
# only sums the original set. That is the exact, confirmed mechanism behind the
# documented 596-vs-600 discrepancy (architecture.md) — not a mystery gap, a stale range.
#
# "Fiescheralp" is the one launch genuinely unreferenced by ANY region formula, in any
# column — checked exhaustively, not just in the Total column. Its one flight is left
# unmapped (None) here on purpose. The importer's region reconciliation (FR-015) is
# expected to still show a residual 1-flight gap after reproducing the other 3.
# ---------------------------------------------------------------------------------------

SITE_REGION = {
    "Luegibrüggli": "Interlaken",
    "Bergbo": "Interlaken",
    "Chalet": "Interlaken",
    "Amisbühl": "Interlaken",
    "Hohwald": "Interlaken",
    "Niederhorn": "Interlaken",
    "Breitlauenen": "Interlaken",
    "Alp Oberburgfeld": "Interlaken",
    "Sulegg": "Interlaken",
    "Ober Burgfeldstand": "Interlaken",  # yearly formulas only — missing from the Total column
    "Alp Unterburgfeld": "Interlaken",  # yearly formulas only — missing from the Total column
    "Wurmegg": "Mürren",
    "Schiltgrat": "Mürren",
    "Schilthorn": "Mürren",
    "Birg": "Mürren",
    "First": "Grindelwald",
    "Jungfraujoch": "Grindelwald",
    "Pfingstegg": "Grindelwald",
    "Männlichen": "Grindelwald",
    "First Oben": "Grindelwald",
    "Lauberhorn": "Grindelwald",  # yearly formulas only — missing from the Total column
    "Möntschelenalp": "Gantrischgebiet",
    "Weissenstein": "Jura",
    "Brienzer Rothorn": "Brienz",
    "Axalp Windegg": "Brienz",
    "Niesen": "Niesen",
    "Metschstand Bise": "Adelboden-Lenk",
    "Schwandfeldspitz": "Adelboden-Lenk",
    "Tschentenalp": "Adelboden-Lenk",
    "Metschstand": "Adelboden-Lenk",
    "Marbachegg": "Marbach",
    "Riggisalp": "Schwarzsee",
    "Därstetten Geeristein": "Därstetten",
    "Fiescheralp": None,  # genuinely unreferenced anywhere — see note above
}

# ---------------------------------------------------------------------------------------
# Known first names for buddy proposals (FR-017), found by frequency analysis of
# Flugbuch's Kommentar column: capitalized words that recur across multiple flights in a
# "flew with <name>" context, verified by reading the surrounding sentence for each —
# never a generic named-entity recognizer (research.md explains why: 600 rows of one
# person's German free text does not justify an NLP dependency, and a maintained list is
# auditable while an NER model's misses/false-positives are not).
#
# This is intentionally short and specific to this pilot's actual flying partners, not a
# general German-name gazetteer — a name that isn't here yet is simply not proposed. The
# pilot adds names to this list as new buddies show up in future comments; that is a
# config change, not a re-run of frequency analysis.
# ---------------------------------------------------------------------------------------

KNOWN_BUDDY_NAMES = [
    "Tom",
    "Ueli",
    "Simon",
    "Susi",
    "Tigi",
    "Jürg",
    "Beni",
]
