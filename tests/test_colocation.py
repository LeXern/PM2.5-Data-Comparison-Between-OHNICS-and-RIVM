from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pm25colocation import colocation


# ---------- co-location ----------
def _synthetic(lag_h=0, slope=1.2, offset=-1.0, hours=24 * 14, seed=1):
    rng = np.random.default_rng(seed)
    t_end = pd.date_range('2026-10-01T01:00Z', periods=hours, freq='1h')
    truth = 6 + 4 * np.sin(np.arange(hours) / 9) + rng.gamma(2, 1.5, hours)
    ref = pd.DataFrame({'time': t_end, 'value': truth})
    # sensor stamps its hour at the start (one hour earlier than the reference), plus any extra lag
    sensor = pd.DataFrame({'time': t_end - pd.Timedelta(hours=1) - pd.Timedelta(hours=lag_h),
                           'pm25': slope * truth + offset + rng.normal(0, 0.2, hours)})
    return sensor, ref


def test_stats_recover_known_line():
    x = np.linspace(1, 20, 200)
    s = colocation.stats(x, 1.25 * x - 2)
    assert s['ols_slope'] == pytest.approx(1.25) and s['ols_intercept'] == pytest.approx(-2)
    assert s['orth_slope'] == pytest.approx(1.25) and s['r2'] == pytest.approx(1)


def test_alignment_finds_the_time_convention():
    sensor, ref = _synthetic(lag_h=1)
    res = colocation.analyse(sensor, ref)
    assert res['lag_h'] == 1
    hourly = res['stats'].query("period == 'all' and resolution == 'hourly'").iloc[0]
    assert hourly['ols_slope'] == pytest.approx(1.2, abs=0.02) and hourly['r2'] > 0.99


def test_aggregation_needs_enough_hours():
    sensor, ref = _synthetic(hours=24 * 3)
    res = colocation.analyse(sensor, ref, lag=0)
    daily = res['pairs']['daily']
    assert len(daily) in (2, 3) and res['pairs']['4-hourly'].shape[0] >= 16


def test_periods_split_the_statistics():
    sensor, ref = _synthetic()
    periods = [{'name': 'A', 'start': '2026-10-01', 'end': '2026-10-08'},
               {'name': 'B', 'start': '2026-10-08', 'end': '2026-10-20'}]
    st = colocation.analyse(sensor, ref, periods=periods)['stats']
    assert set(st['period']) == {'all', 'A', 'B'}
