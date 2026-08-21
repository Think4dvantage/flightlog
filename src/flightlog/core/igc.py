"""
libigc wrapper: parse, validate, analyze, and extract map/chart-ready segments from an IGC
file. Implements architecture.md's IGC analysis rules 1-7.

Two corrections made against the real installed `libigc` 1.2.0 source, not just its README —
see specs/003-igc-ingest-analysis/research.md:
  - Altitude-source selection is read from libigc's own `flight.alt_source` (it already runs a
    proper per-fix validity check on both the pressure and GNSS streams), never recomputed
    from raw fixes here.
  - `FlightParsingConfig` exposes exactly three thermal-detection parameters
    (`min_bearing_change_circling`, `min_time_for_bearing_change`, `min_time_for_thermal`) —
    not the four differently-named ones originally guessed. There is no separate glide-tuning
    parameter; a glide is simply the gap between two thermals.

`calibrate_altitude()` (v0.9.11) anchors a barometric track's absolute altitude to a known,
trusted launch elevation — see its own docstring for why this is a source-*agnostic* GNSS
question with a source-*specific* answer.

CPU-bound. 04-constraints.md's rule against blocking the event loop applies to an `async def`
handler calling this directly — every route in `api/routers/igc.py` is a plain sync `def`
instead (matching every other router in this app), so FastAPI's own threadpool dispatch
already keeps this off the event loop without an explicit `asyncio.to_thread` call.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from libigc import Flight, FlightParsingConfig

from flightlog.config import IgcParsingConfig

logger = logging.getLogger(__name__)

# Bump whenever the analysis algorithm or its tuning changes in a way that should make
# POST /api/admin/reanalyze reprocess existing tracks.
ANALYZER_VERSION = "2"

# libigc's own AltitudeSource.PRESSURE.value (confirmed against the installed 1.2.0 package,
# not guessed) — this is the literal string `analyze()` below stores in `alt_source`.
_PRESSURE_SOURCE = "PRESS"

# Not a cutoff that gates the correction — see calibrate_altitude()'s docstring for why a
# large offset is logged, never suppressed.
_LARGE_OFFSET_WARNING_M = 150.0

# Enough points for a smooth map line and barogram without re-parsing the raw file on
# ordinary viewing (architecture.md: track_simplified_json is "derived, regenerable").
SIMPLIFIED_TRACK_POINTS = 500

# A 10-second window for the instantaneous peak-climb figure (architecture.md rule 6) —
# separate from best_climb_ms, which is a thermal *average*, never the instantaneous peak.
PEAK_CLIMB_WINDOW_S = 10.0


class IgcInvalidError(Exception):
    """Raised when libigc rejects the file (`flight.valid` is False). `notes` carries
    libigc's own reasons, suitable for a 422 response's detail."""

    def __init__(self, notes: list[str]):
        self.notes = notes
        super().__init__("; ".join(notes) or "Invalid IGC file")


@dataclass
class FixPoint:
    lat: float
    lon: float
    alt_m: float | None
    at: datetime


@dataclass
class SegmentResult:
    kind: str  # thermal|glide|takeoff|landing|max_alt|top_of_climb
    start_offset_s: int
    start_at: datetime
    duration_s: int | None = None
    alt_change_m: float | None = None
    vertical_velocity_ms: float | None = None
    glide_ratio: float | None = None


@dataclass
class AnalysisResult:
    duration_s: int
    distance_km: float
    max_alt_igc_m: int
    alt_gain_igc_m: int
    thermal_count: int
    best_climb_ms: float | None
    peak_climb_ms: float | None
    glide_ratio: float | None
    alt_source: str
    track_simplified_json: str
    takeoff_fix: FixPoint
    landing_fix: FixPoint
    segments: list[SegmentResult] = field(default_factory=list)


def _build_config_class(cfg: IgcParsingConfig) -> type[FlightParsingConfig]:
    """`Flight.create_from_file` takes a config *class*, not an instance — it calls
    `config_class()` itself (research.md)."""

    class _TunedConfig(FlightParsingConfig):
        min_bearing_change_circling = cfg.min_bearing_change_circling
        min_time_for_bearing_change = cfg.min_time_for_bearing_change
        min_time_for_thermal = cfg.min_time_for_thermal

    return _TunedConfig


def _to_datetime(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _to_fix_point(fix) -> FixPoint:
    return FixPoint(lat=fix.lat, lon=fix.lon, alt_m=fix.alt, at=_to_datetime(fix.timestamp))


def _peak_climb_ms(fixes: list, window_s: float) -> float | None:
    """Best average vertical speed over any `window_s`-second span — a two-pointer sliding
    window over the time-ordered fix list, O(n)."""
    if len(fixes) < 2:
        return None
    best = None
    left = 0
    for right in range(len(fixes)):
        while fixes[right].timestamp - fixes[left].timestamp > window_s:
            left += 1
        dt = fixes[right].timestamp - fixes[left].timestamp
        if dt <= 0:
            continue
        v = (fixes[right].alt - fixes[left].alt) / dt
        if best is None or v > best:
            best = v
    return best


def _build_track_simplified_json(fixes: list, takeoff_ts: float) -> str:
    n = len(fixes)
    if n <= SIMPLIFIED_TRACK_POINTS:
        sampled = fixes
    else:
        step = (n - 1) / (SIMPLIFIED_TRACK_POINTS - 1)
        sampled = [fixes[round(i * step)] for i in range(SIMPLIFIED_TRACK_POINTS)]
    points = [
        [
            round(fix.timestamp - takeoff_ts),
            round(fix.lat, 6),
            round(fix.lon, 6),
            round(fix.alt, 1),
        ]
        for fix in sampled
    ]
    return json.dumps(points)


def parse_simplified_track(
    track_simplified_json: str | None,
) -> tuple[list[list[float]], list[int]]:
    """[[lon, lat, alt_m], ...] geometry + parallel offsets_s, from the stored
    [offset_s, lat, lon, alt_m] points (see _build_track_simplified_json). Shared by the
    authenticated and public GeoJSON responses so both stay in sync."""
    points = json.loads(track_simplified_json or "[]")
    coordinates = [[lon, lat, alt] for _offset, lat, lon, alt in points]
    offsets_s = [offset for offset, _lat, _lon, _alt in points]
    return coordinates, offsets_s


def analyze(path: str, parsing_config: IgcParsingConfig) -> AnalysisResult:
    """Parse and analyze an IGC file already written to disk. CPU-bound — see module
    docstring; callers must run this via `asyncio.to_thread`."""
    flight = Flight.create_from_file(path, config_class=_build_config_class(parsing_config))
    if not flight.valid:
        raise IgcInvalidError(flight.notes)

    takeoff_fix = flight.takeoff_fix
    landing_fix = flight.landing_fix
    flight_fixes = flight.fixes[takeoff_fix.index : landing_fix.index + 1]

    duration_s = round(landing_fix.timestamp - takeoff_fix.timestamp)
    distance_km = sum(
        flight_fixes[i].distance_to(flight_fixes[i - 1]) for i in range(1, len(flight_fixes))
    )
    max_alt_igc_m = round(max(fix.alt for fix in flight_fixes))
    # Same shape as the app's existing derived flights.alt_gain_m (max altitude minus
    # effective launch elevation) — here the "launch elevation" is the track's own takeoff
    # fix altitude, not a stored site elevation (architecture.md's "Derived values").
    alt_gain_igc_m = round(max_alt_igc_m - takeoff_fix.alt)

    # Rule 3: libigc flags *any* circling as a thermal, including descending spirals and
    # wingovers — both routine in paragliding. Keep only genuinely climbing circles.
    kept_thermals = [t for t in flight.thermals if t.alt_change() > 0]
    best_thermal = max(kept_thermals, key=lambda t: t.vertical_velocity(), default=None)
    best_climb_ms = best_thermal.vertical_velocity() if best_thermal else None
    peak_climb_ms = _peak_climb_ms(flight_fixes, PEAK_CLIMB_WINDOW_S)

    # Rule 5: an aggregate, over-ground ratio across descending glides only — one shallow
    # segment cannot inflate it the way a per-glide average could.
    descending_glides = [g for g in flight.glides if g.alt_change() < 0]
    total_glide_track_m = sum(g.track_length * 1000.0 for g in descending_glides)
    total_glide_descent_m = sum(-g.alt_change() for g in descending_glides)
    glide_ratio = (
        total_glide_track_m / total_glide_descent_m if total_glide_descent_m > 1e-7 else None
    )

    segments = [
        SegmentResult(
            kind="takeoff", start_offset_s=0, start_at=_to_datetime(takeoff_fix.timestamp)
        ),
        SegmentResult(
            kind="landing",
            start_offset_s=duration_s,
            start_at=_to_datetime(landing_fix.timestamp),
        ),
    ]
    max_alt_fix = max(flight_fixes, key=lambda f: f.alt)
    segments.append(
        SegmentResult(
            kind="max_alt",
            start_offset_s=round(max_alt_fix.timestamp - takeoff_fix.timestamp),
            start_at=_to_datetime(max_alt_fix.timestamp),
        )
    )
    if best_thermal is not None:
        segments.append(
            SegmentResult(
                kind="top_of_climb",
                start_offset_s=round(best_thermal.exit_fix.timestamp - takeoff_fix.timestamp),
                start_at=_to_datetime(best_thermal.exit_fix.timestamp),
            )
        )
    for thermal in kept_thermals:
        segments.append(
            SegmentResult(
                kind="thermal",
                start_offset_s=round(thermal.enter_fix.timestamp - takeoff_fix.timestamp),
                start_at=_to_datetime(thermal.enter_fix.timestamp),
                duration_s=round(thermal.time_change()),
                alt_change_m=thermal.alt_change(),
                vertical_velocity_ms=thermal.vertical_velocity(),
            )
        )
    for glide in flight.glides:
        segments.append(
            SegmentResult(
                kind="glide",
                start_offset_s=round(glide.enter_fix.timestamp - takeoff_fix.timestamp),
                start_at=_to_datetime(glide.enter_fix.timestamp),
                duration_s=round(glide.time_change()),
                alt_change_m=glide.alt_change(),
                glide_ratio=glide.glide_ratio(),
            )
        )
    segments.sort(key=lambda s: s.start_offset_s)

    logger.info(
        "IGC analyzed: duration=%ds distance=%.1fkm thermals=%d alt_source=%s",
        duration_s,
        distance_km,
        len(kept_thermals),
        flight.alt_source,
    )

    return AnalysisResult(
        duration_s=duration_s,
        distance_km=round(distance_km, 2),
        max_alt_igc_m=max_alt_igc_m,
        alt_gain_igc_m=alt_gain_igc_m,
        thermal_count=len(kept_thermals),
        best_climb_ms=best_climb_ms,
        peak_climb_ms=peak_climb_ms,
        glide_ratio=glide_ratio,
        alt_source=str(flight.alt_source),
        track_simplified_json=_build_track_simplified_json(flight_fixes, takeoff_fix.timestamp),
        takeoff_fix=_to_fix_point(takeoff_fix),
        landing_fix=_to_fix_point(landing_fix),
        segments=segments,
    )


def _shift_simplified_track(track_simplified_json: str, offset_m: float) -> str:
    """Re-stamps every point's stored altitude by a constant offset — the lat/lon/offset_s
    columns are untouched. `_build_track_simplified_json` is the only writer of this shape
    ([offset_s, lat, lon, alt_m]); this is the one place that ever rewrites it after the fact."""
    points = json.loads(track_simplified_json)
    shifted = [
        [offset_s, lat, lon, round(alt_m + offset_m, 1)] for offset_s, lat, lon, alt_m in points
    ]
    return json.dumps(shifted)


def calibrate_altitude(
    analysis: AnalysisResult, reference_launch_elev_m: float | None
) -> tuple[AnalysisResult, float | None]:
    """Anchors a barometric track's absolute altitude to a known, trusted launch elevation.

    A vario/GPS unit with the wrong QNH/altitude-reference set at launch produces a
    barometric trace that is perfectly smooth and passes libigc's own per-fix validity check
    (rate-of-change + bounds only) — it just sits at a roughly constant offset from reality
    for the whole flight. That offset is exactly what this corrects, using the launch site's
    own known elevation (already trusted more than a single GNSS fix — see architecture.md's
    "Coordinates are backfilled, never geocoded" section) as ground truth.

    Deliberately **PRESS-sourced tracks only**. A GNSS fix's error is per-fix noise, not a
    constant bias, so anchoring an entire GNSS-sourced track to one (possibly noisy) GNSS
    takeoff fix would trade a real, roughly-constant barometric offset for a new, unjustified
    one — the failure mode this function exists to fix doesn't apply to GNSS at all.

    Every figure derived from an altitude *difference* — `alt_gain_igc_m`, every segment's
    `alt_change_m`, `best_climb_ms`/`peak_climb_ms`, `glide_ratio` — is invariant under a
    constant shift by construction and is deliberately left untouched; only genuinely
    absolute readings (`max_alt_igc_m`, the takeoff/landing fixes, the simplified track's own
    altitude column) are shifted.

    No magnitude cutoff gates this correction — a huge offset is far more likely to mean the
    flight is attached to the wrong launch site than that this formula is wrong, and silently
    declining to correct it would hide that mismatch rather than surface it (this project's
    "report, never silently overwrite" stance — see architecture.md's Statistics section).
    It's logged instead, and the caller persists the applied offset (`alt_calibration_offset_m`)
    so it's visible on the flight's own IGC summary.

    Returns the (possibly unchanged) analysis and the offset actually applied — `None` when no
    correction was possible (no known launch elevation) or appropriate (GNSS-sourced)."""
    if reference_launch_elev_m is None or analysis.alt_source != _PRESSURE_SOURCE:
        return analysis, None

    offset_m = reference_launch_elev_m - analysis.takeoff_fix.alt_m
    if abs(offset_m) > _LARGE_OFFSET_WARNING_M:
        logger.warning(
            "Large altitude calibration offset (%.1fm) — check the launch site match", offset_m
        )

    calibrated = replace(
        analysis,
        max_alt_igc_m=round(analysis.max_alt_igc_m + offset_m),
        takeoff_fix=replace(analysis.takeoff_fix, alt_m=analysis.takeoff_fix.alt_m + offset_m),
        landing_fix=replace(analysis.landing_fix, alt_m=analysis.landing_fix.alt_m + offset_m),
        track_simplified_json=_shift_simplified_track(analysis.track_simplified_json, offset_m),
    )
    return calibrated, offset_m
