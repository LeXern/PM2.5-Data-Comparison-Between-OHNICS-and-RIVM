"""Compare a low-cost sensor with a reference station over a co-location period.

    python -m pm25colocation.colocation --sensor data/raw/ohnics_7d.csv --reference data/raw/rivm_NL10821_PM25.csv
        [--periods config/reference_periods.json] [--lag auto|<hours>] [--out results] [--figures figures]

Steps
1. Bring the sensor to the reference time base. For sensor data at one hour or finer,
   values are averaged into hours stamped at the END of the hour, like Luchtmeetnet.
   Coarser sensor data (4-hourly, daily) is compared with the reference averaged over
   the same intervals.
2. Find the time offset that best aligns the two series (whole hours, -2..+3) unless
   --lag fixes it. A non-zero lag usually means a different timestamp convention.
3. Aggregate the hourly pairs to 4-hourly and daily means (at least 75 % of hours present).
4. Report n, means, bias, RMSE, MAE, R2, ordinary least squares and orthogonal
   (Deming, lambda = 1) regression for each resolution and each reference period,
   plus the median sensor/reference ratio by concentration band.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BANDS = [(0, 5), (5, 10), (10, np.inf)]
MIN_FRACTION = 0.75


# ---------- statistics ----------
def stats(ref: pd.Series | np.ndarray, sensor: pd.Series | np.ndarray) -> dict:
    x, y = np.asarray(ref, float), np.asarray(sensor, float)
    m = ~(np.isnan(x) | np.isnan(y))
    x, y = x[m], y[m]
    out = {'n': int(len(x))}
    if len(x) < 3:
        return out
    slope, intercept = np.polyfit(x, y, 1)
    r = np.corrcoef(x, y)[0, 1]
    sxx, syy, sxy = np.var(x, ddof=1), np.var(y, ddof=1), np.cov(x, y)[0, 1]
    o_slope = (syy - sxx + np.sqrt((syy - sxx) ** 2 + 4 * sxy ** 2)) / (2 * sxy)
    out.update(ref_mean=x.mean(), sensor_mean=y.mean(), bias=(y - x).mean(),
               rel_bias_pct=(y.mean() / x.mean() - 1) * 100 if x.mean() else np.nan,
               rmse=np.sqrt(((y - x) ** 2).mean()), mae=np.abs(y - x).mean(), r2=r ** 2,
               ols_slope=slope, ols_intercept=intercept,
               orth_slope=o_slope, orth_intercept=y.mean() - o_slope * x.mean())
    return out


def ratio_by_band(pairs: pd.DataFrame, bands=BANDS, min_ref: float = 0.5) -> pd.DataFrame:
    p = pairs[pairs['ref'] > min_ref]
    rows = []
    for lo, hi in bands:
        sel = p[(p['ref'] >= lo) & (p['ref'] < hi)]
        rows.append({'band': f'{lo:g}–{hi:g}' if np.isfinite(hi) else f'≥{lo:g}', 'n': len(sel),
                     'median_ratio': (sel['sensor'] / sel['ref']).median() if len(sel) else np.nan})
    return pd.DataFrame(rows)


# ---------- alignment ----------
def step_of(df: pd.DataFrame) -> pd.Timedelta:
    return df['time'].sort_values().diff().median()


def hourly_sensor(sensor: pd.DataFrame, col: str = 'pm25') -> pd.Series:
    """Average sub-hourly or hourly sensor values into hours stamped at the end of the hour."""
    s = sensor.set_index('time')[col]
    return s.resample('1h', label='right', closed='left').mean().dropna()


def pairs_hourly(sensor: pd.DataFrame, ref: pd.DataFrame, lag_h: int, col: str = 'pm25') -> pd.DataFrame:
    s = hourly_sensor(sensor, col)
    s.index = s.index + pd.Timedelta(hours=lag_h)
    r = ref.set_index('time')['value']
    return pd.concat([r.rename('ref'), s.rename('sensor')], axis=1, join='inner').dropna()


def pairs_coarse(sensor: pd.DataFrame, ref: pd.DataFrame, lag_h: int, col: str = 'pm25') -> pd.DataFrame:
    """Sensor values stamped at the start of each interval, compared with the reference mean over that interval."""
    step = step_of(sensor)
    need = int(round(step / pd.Timedelta(hours=1)))
    r = ref.set_index('time')['value']
    rows = []
    for t, v in sensor.set_index('time')[col].items():
        start = t + pd.Timedelta(hours=lag_h)
        window = r[(r.index > start) & (r.index <= start + step)]  # reference hours ending inside the interval
        if len(window) >= MIN_FRACTION * need and not np.isnan(v):
            rows.append({'time': start, 'ref': window.mean(), 'sensor': v})
    return pd.DataFrame(rows).set_index('time') if rows else pd.DataFrame(columns=['ref', 'sensor'])


def make_pairs(sensor: pd.DataFrame, ref: pd.DataFrame, lag_h: int) -> pd.DataFrame:
    return pairs_hourly(sensor, ref, lag_h) if step_of(sensor) <= pd.Timedelta(hours=1) else pairs_coarse(sensor, ref, lag_h)


def best_lag(sensor: pd.DataFrame, ref: pd.DataFrame, candidates=range(-2, 4)) -> tuple[int, pd.DataFrame]:
    rows = [{'lag_h': k, **stats(p['ref'], p['sensor'])} for k in candidates
            for p in [make_pairs(sensor, ref, k)]]
    table = pd.DataFrame(rows)
    valid = table.dropna(subset=['r2']) if 'r2' in table else table.iloc[0:0]
    if valid.empty:
        raise ValueError('sensor and reference do not overlap in time')
    return int(valid.loc[valid['r2'].idxmax(), 'lag_h']), table


def aggregate(pairs: pd.DataFrame, freq: str, hours_per_bin: int) -> pd.DataFrame:
    """Average end-of-hour pairs into bins labelled by their start; keep bins with enough hours."""
    p = pairs.copy()
    p.index = p.index - pd.Timedelta(hours=1)  # end-of-hour stamp -> start of the hour
    g = p.resample(freq)
    agg = g.mean()
    agg['hours'] = g['ref'].count()
    return agg[agg['hours'] >= MIN_FRACTION * hours_per_bin].drop(columns='hours')


def load_periods(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8'))['periods']


def in_period(df: pd.DataFrame, period: dict) -> pd.DataFrame:
    lo = pd.Timestamp(period['start'], tz='UTC')
    hi = pd.Timestamp(period['end'], tz='UTC')
    return df[(df.index >= lo) & (df.index < hi)]


def analyse(sensor: pd.DataFrame, ref: pd.DataFrame, lag: str | int = 'auto', periods: list[dict] | None = None) -> dict:
    if lag == 'auto':
        lag_h, lag_table = best_lag(sensor, ref)
    else:
        lag_h, lag_table = int(lag), None
    base = make_pairs(sensor, ref, lag_h)
    hourly = step_of(sensor) <= pd.Timedelta(hours=1)
    sets = {'hourly': base, '4-hourly': aggregate(base, '4h', 4), 'daily': aggregate(base, '1D', 24)} if hourly \
        else {f'{int(step_of(sensor) / pd.Timedelta(hours=1))}-hourly (as downloaded)': base}
    rows = []
    for res, p in sets.items():
        rows.append({'period': 'all', 'resolution': res, **stats(p['ref'], p['sensor'])})
        for per in periods or []:
            q = in_period(p, per)
            rows.append({'period': per['name'], 'resolution': res, **stats(q['ref'], q['sensor'])})
    return {'lag_h': lag_h, 'lag_table': lag_table, 'pairs': sets, 'stats': pd.DataFrame(rows),
            'bands': ratio_by_band(base), 'negative_ref': int((ref['value'] < 0).sum())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--sensor', type=Path, required=True, help='CSV from pm25colocation.ohnics (time, pm25, ...)')
    ap.add_argument('--reference', type=Path, required=True, help='CSV from pm25colocation.rivm (time, value, ...)')
    ap.add_argument('--periods', type=Path, default=ROOT / 'config' / 'reference_periods.json',
                    help="JSON with reference-instrument periods, or 'none'")
    ap.add_argument('--lag', default='auto', help="'auto' or whole hours to shift the sensor")
    ap.add_argument('--out', type=Path, default=ROOT / 'results')
    a = ap.parse_args()

    sensor = pd.read_csv(a.sensor, parse_dates=['time'])
    ref = pd.read_csv(a.reference, parse_dates=['time'])
    for df in (sensor, ref):
        df['time'] = pd.to_datetime(df['time'], utc=True)
    periods = [] if str(a.periods).lower() == 'none' else load_periods(a.periods)
    res = analyse(sensor, ref, a.lag if a.lag == 'auto' else int(a.lag), periods)
    a.out.mkdir(parents=True, exist_ok=True)
    res['stats'].to_csv(a.out / 'colocation_stats.csv', index=False)
    print(f'lag {res["lag_h"]:+d} h; wrote {a.out / "colocation_stats.csv"}')


if __name__ == '__main__':
    main()
