# Data Model: Statistics

**No new tables.** Matches `architecture.md`'s existing, explicit decision: "Nothing is materialised.
Every figure is one or two indexed aggregates" and its "Tables that do NOT exist" list already rules out
a `stats_cache` table speculatively. This document instead defines the response *shapes* — what each
computed figure looks like once assembled — since there is no schema to define.

## Response shapes

### `TotalsOut`
| Field | Type | Source |
|---|---|---|
| `total_flights` | int | `COUNT(flights)` |
| `total_airtime_min` | int | `SUM(flights.duration_min)` |
| `total_distance_km` | float | `SUM(flights.distance_km)` |
| `total_alt_gain_m` | int | `SUM` of the computed `alt_gain_m` per flight (`research.md` — never the stored legacy value) |
| `avg_airtime_min` | float | `AVG(flights.duration_min)` |
| `avg_airtime_min_excl_training` | float | `AVG(flights.duration_min) WHERE NOT flight_categories.is_training` — the workbook's own "Average Airtime special" (`research.md`) |
| `avg_distance_km` | float | `AVG(flights.distance_km)` |

### `TimeBreakdownOut`
| Field | Type | Source |
|---|---|---|
| `by_year` | `dict[int, int]` | flight count per year |
| `by_month` | `dict[int, int]` | flight count per calendar month (1–12), across all years |
| `year_month_matrix` | `dict[int, dict[int, int]]` | year → month → count, the workbook's "Distribution over Time" block reproduced |

### `DistributionOut`
| Field | Type | Source |
|---|---|---|
| `duration_buckets` | `dict[str, int]` | `"<30min"`, `"30-60min"`, `"60-120min"`, `"120-180min"`, `">180min"` — boundaries taken directly from `Übersicht`'s own `# of Flights over Nmin` rows (`research.md`), not invented |
| `distance_buckets` | `dict[str, int]` | Round-number boundaries (implementation-time detail, `spec.md`'s Assumptions — no source precedent exists for these the way duration has one) |
| `altitude_buckets` | `dict[str, int]` | Same as `distance_buckets` |

### `PersonalBestOut`
| Field | Type | Notes |
|---|---|---|
| `label` | string | e.g. `"longest_airtime"`, `"max_altitude"`, `"highest_launch"`, `"lowest_launch"`, `"highest_landing"`, `"lowest_landing"`, `"longest_distance"`, `"shortest_distance"` — the exact eight from `Übersicht`'s `Flight Statistics` block |
| `value` | float | |
| `flight_id` | string | Always resolvable — ties break to the earliest flight by date, then by id (`research.md`) |

### `DimensionYearMatrixOut`
One shared shape for all five per-year matrices (FR-006), returned once per dimension:
| Field | Type | Notes |
|---|---|---|
| `dimension` | string | `"site"` \| `"region"` \| `"glider"` \| `"harness"` \| `"category"` |
| `rows` | `list[{name: str, id: str | null, by_year: dict[int, int], total: int}]` | `id` is null for a "not recorded" bucket (`spec.md`'s Edge Cases — a flight missing that dimension's field still counts, grouped separately, never silently dropped) |

### `LaunchTechniqueOut`
| Field | Type | Source |
|---|---|---|
| `forward` | int | `COUNT WHERE launch_technique = 'forward'` |
| `reverse` | int | `COUNT WHERE launch_technique = 'reverse'` |
| `reverse_pct` | float | Computed correctly over the full flight count — the workbook's own figure is a confirmed formula bug (stale range, `architecture.md`), reproduced correctly here, never matched to the wrong number |
| `hike_fly_total` | int | `COUNT WHERE flight_categories.is_hike_fly` |

### `IgcRollupOut`
| Field | Type | Source |
|---|---|---|
| `cumulative_thermal_climb_m` | float | `SUM(igc_segments.alt_change_m) WHERE kind = 'thermal'`, joined across the owner's tracks (`research.md`) — the headline figure the spreadsheet cannot produce |
| `tracks_uploaded` | int | For context — this rollup only ever covers flights with a track, per `spec.md`'s Assumptions |

### `BuddyYearMatrixOut`
Same shape as `DimensionYearMatrixOut` with `dimension = "buddy"`, computed only over existing
`flight_buddies` rows (`research.md` — never backfilled or reconciled against the workbook's own
"Buddys" tally or the frozen comment-scan proposals).

### `ProgressionOut`
| Field | Type | Source |
|---|---|---|
| `current_streak` | `{unit: "week"|"month", count: int}` | Consecutive periods with ≥1 flight, ending at the most recent |
| `ytd_pace` | `{this_year: int, same_point_prior_year: int}` | Flight count from Jan 1 to today's month/day, this year vs. the same window last year |
| `cumulative_series` | `list[{date: str, cumulative_count: int}]` | Running total by flight date, for a simple line chart |

## Relationships summary

No new tables, no new foreign keys. Every shape above is assembled by `core/stats.py` from existing
tables' data at request time:

```
flights ──(joins)── flight_categories, sites, regions, gliders, harnesses, flight_buddies/buddies
flights ──(0..1)── igc_tracks ──(1..*)── igc_segments
```
