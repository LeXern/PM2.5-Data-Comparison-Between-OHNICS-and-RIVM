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


def test_read_sensor_accepts_other_columns_and_local_time(tmp_path):
    f = tmp_path / 'export.csv'
    f.write_text('Timestamp,PM2.5 (ug/m3)\n2026-11-08 10:00:00,5.0\n2026-11-08 10:01:00,6.0\n')
    df = colocation.read_sensor(f, 'Timestamp', 'PM2.5 (ug/m3)', 'Europe/Amsterdam')
    assert df['time'].iloc[0] == pd.Timestamp('2026-11-08T09:00:00Z') and list(df['pm25']) == [5.0, 6.0]
    with pytest.raises(SystemExit):
        colocation.read_sensor(f, 'time', 'pm25')


def test_reference_periods_only_for_their_station(tmp_path):
    p = tmp_path / 'periods.json'
    p.write_text('{"station": "NL10821", "periods": [{"name": "A", "start": "2026-01-01", "end": "2027-01-01"}]}')
    same = pd.DataFrame({'station': ['NL10821']})
    other = pd.DataFrame({'station': ['NL01908']})
    assert len(colocation.load_periods(p, same)) == 1
    assert colocation.load_periods(p, other) == []
    assert colocation.load_periods(Path('none')) == []


def test_html_report_is_self_contained(tmp_path):
    sensor, ref = _synthetic(hours=24 * 4)
    res = colocation.analyse(sensor, ref)
    figs = colocation.plot(res, tmp_path / 'fig', 'Sensor <A>', 'RIVM')
    out = tmp_path / 'report.html'
    colocation.write_report_html(res, out, 'Sensor <A>', 'RIVM', figs)
    page = out.read_text(encoding='utf-8')
    assert page.count('data:image/png;base64,') == 3
    assert 'Sensor &lt;A&gt;' in page and 'Sensor <A>' not in page
    assert 'src="http' not in page and '<link' not in page  # nothing loaded from elsewhere
    assert 'Bias (%)' in page and 'Orthogonal slope' in page


def test_files_with_different_dates_give_a_clear_fix():
    sensor, ref = _synthetic(hours=48)
    ref = ref.assign(time=ref['time'] + pd.Timedelta(days=30), station='NL10821')
    with pytest.raises(SystemExit) as e:
        colocation.analyse(sensor, ref)
    msg = str(e.value)
    assert 'cover different dates' in msg and '--station NL10821 --start 2026-10-01 --end 2026-10-03' in msg


def test_missing_file_lists_what_is_there(tmp_path):
    (tmp_path / 'rivm_NL10821_PM25.csv').write_text('time,value\n')
    with pytest.raises(SystemExit) as e:
        colocation.read_sensor(tmp_path / 'samenmeten_X_pm25.csv')
    assert 'does not exist' in str(e.value) and 'rivm_NL10821_PM25.csv' in str(e.value)
