"""
core/igc.py::calibrate_altitude() — pure-logic tests, no DB (06-testing-conventions.md's
duck-typing convention, here against the real `AnalysisResult`/`FixPoint` dataclasses directly
rather than a `SimpleNamespace`, since they're already plain data with no ORM behind them).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from flightlog.core.igc import AnalysisResult, FixPoint, calibrate_altitude

_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def _analysis(
    alt_source="PRESS",
    takeoff_alt_m=1900.0,
    landing_alt_m=1351.0,
    max_alt_igc_m=2431,
    alt_gain_igc_m=531,
):
    track_points = [
        [0, 46.5, 7.5, takeoff_alt_m],
        [300, 46.5, 7.5, max_alt_igc_m],
        [602, 46.5, 7.5, landing_alt_m],
    ]
    return AnalysisResult(
        duration_s=602,
        distance_km=1.0,
        max_alt_igc_m=max_alt_igc_m,
        alt_gain_igc_m=alt_gain_igc_m,
        thermal_count=1,
        best_climb_ms=1.5,
        peak_climb_ms=2.0,
        glide_ratio=5.0,
        alt_source=alt_source,
        track_simplified_json=json.dumps(track_points),
        takeoff_fix=FixPoint(lat=46.5, lon=7.5, alt_m=takeoff_alt_m, at=_AT),
        landing_fix=FixPoint(lat=46.5, lon=7.5, alt_m=landing_alt_m, at=_AT),
        segments=[],
    )


def test_calibrate_shifts_absolute_altitude_to_known_launch_elevation():
    """The pilot's own reported case: a barometric sledder shows less than the known,
    trusted launch elevation because the QNH/altitude reference was off at takeoff."""
    analysis = _analysis(
        takeoff_alt_m=1488.0, landing_alt_m=1200.0, max_alt_igc_m=1488, alt_gain_igc_m=0
    )

    calibrated, offset_m = calibrate_altitude(analysis, reference_launch_elev_m=1588.0)

    assert offset_m == 100.0
    assert calibrated.takeoff_fix.alt_m == 1588.0  # now matches the known launch elevation
    assert calibrated.max_alt_igc_m == 1588  # a no-climb sledder: max == corrected launch elevation
    assert calibrated.landing_fix.alt_m == 1300.0


def test_calibrate_shifts_the_simplified_track_altitude_column_only():
    analysis = _analysis()
    calibrated, offset_m = calibrate_altitude(analysis, reference_launch_elev_m=2000.0)

    assert offset_m == 100.0  # 2000 - 1900
    points = json.loads(calibrated.track_simplified_json)
    assert [p[3] for p in points] == [2000.0, 2531.0, 1451.0]
    # lat/lon/offset_s columns are untouched.
    assert [p[:3] for p in points] == [[0, 46.5, 7.5], [300, 46.5, 7.5], [602, 46.5, 7.5]]


def test_calibrate_never_touches_difference_based_figures():
    """alt_gain_igc_m, climb rates and glide ratio are all differences over altitude — a
    constant shift cancels out of every one of them by construction."""
    analysis = _analysis()
    calibrated, _ = calibrate_altitude(analysis, reference_launch_elev_m=2000.0)

    assert calibrated.alt_gain_igc_m == analysis.alt_gain_igc_m == 531
    assert calibrated.best_climb_ms == analysis.best_climb_ms
    assert calibrated.peak_climb_ms == analysis.peak_climb_ms
    assert calibrated.glide_ratio == analysis.glide_ratio


def test_calibrate_skips_gnss_sourced_tracks():
    """A GNSS fix's error is per-fix noise, not a constant bias — anchoring the whole track
    to one GNSS takeoff fix would trade a real barometric offset for an unjustified one."""
    analysis = _analysis(alt_source="GNSS")
    calibrated, offset_m = calibrate_altitude(analysis, reference_launch_elev_m=2000.0)

    assert offset_m is None
    assert calibrated is analysis


def test_calibrate_skips_when_no_reference_elevation_known():
    analysis = _analysis()
    calibrated, offset_m = calibrate_altitude(analysis, reference_launch_elev_m=None)

    assert offset_m is None
    assert calibrated is analysis


def test_calibrate_applies_a_large_offset_anyway_but_logs_it(caplog):
    """No magnitude cutoff gates the correction — see the function's own docstring for why a
    huge offset is more likely a wrong-launch-site match than a wrong formula, and should be
    surfaced (via the log and the persisted offset), never silently declined."""
    analysis = _analysis()
    with caplog.at_level(logging.WARNING):
        calibrated, offset_m = calibrate_altitude(analysis, reference_launch_elev_m=2500.0)

    assert offset_m == 600.0
    assert calibrated.max_alt_igc_m == 3031
    assert "Large altitude calibration offset" in caplog.text
