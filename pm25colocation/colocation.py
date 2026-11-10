"""Compare a low-cost sensor with a reference station over a co-location period.

    python -m pm25colocation.colocation --sensor data/raw/samenmeten_OHN_tw-4222_pm25.csv --reference data/raw/rivm_NL10821_PM25.csv
        [--time-col time] [--pm-col pm25] [--sensor-tz UTC] [--periods config/reference_periods.json] [--lag auto|<hours>]

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


def load_periods(path: Path | None, reference: pd.DataFrame | None = None) -> list[dict]:
    """Reference-instrument periods, used only when they belong to the station in the reference file."""
    if not path or str(path).lower() == 'none' or not path.exists():
        return []
    cfg = json.loads(path.read_text(encoding='utf-8'))
    station = cfg.get('station')
    if station and reference is not None and 'station' in reference:
        found = set(reference['station'].dropna().astype(str))
        if found and found != {station}:
            print(f'reference periods in {path.name} are for {station}, not {", ".join(sorted(found))}: not applied')
            return []
    return cfg['periods']


def read_sensor(path: Path, time_col: str = 'time', pm_col: str = 'pm25', tz: str = 'UTC') -> pd.DataFrame:
    """Read any sensor CSV and return columns time (UTC) and pm25. Times without a zone are taken as `tz`."""
    df = pd.read_csv(path)
    missing = [c for c in (time_col, pm_col) if c not in df.columns]
    if missing:
        raise SystemExit(f'{path} has no column {missing}; columns are: {", ".join(df.columns)}')
    t = pd.to_datetime(df[time_col])
    t = t.dt.tz_localize(tz) if t.dt.tz is None else t
    return pd.DataFrame({'time': t.dt.tz_convert('UTC'), 'pm25': pd.to_numeric(df[pm_col], errors='coerce')}) \
        .dropna().drop_duplicates('time').sort_values('time').reset_index(drop=True)


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


# ---------- outputs ----------
def write_summary(res: dict, path: Path, sensor_name: str, ref_name: str) -> None:
    st = res['stats'].copy()
    num = st.select_dtypes('number').columns.drop('n', errors='ignore')
    st[num] = st[num].round(2)
    lines = [f'# Co-location: {sensor_name} vs {ref_name}', '',
             f'Time offset applied to the sensor: {res["lag_h"]:+d} h. '
             f'Negative reference values in the input: {res["negative_ref"]}.', '',
             '## Agreement', '', st.to_markdown(index=False), '',
             '## Sensor/reference ratio by reference concentration (µg/m³)', '',
             res['bands'].round(2).to_markdown(index=False), '']
    if res['lag_table'] is not None:
        lt = res['lag_table'][['lag_h', 'n', 'r2', 'bias']].round(3)
        lines += ['## Time-offset test', '', lt.to_markdown(index=False), '']
    path.write_text('\n'.join(lines), encoding='utf-8')


def plot(res: dict, figdir: Path, sensor_name: str, ref_name: str) -> list[Path]:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    ink, muted, grid = '#17262a', '#56676c', '#e0e6e5'
    c_ref, c_sen = '#2160a6', '#c2410c'
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': muted, 'axes.labelcolor': ink, 'xtick.color': muted,
                         'ytick.color': muted, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.grid': True, 'grid.color': grid, 'grid.linewidth': 0.8})
    figdir.mkdir(parents=True, exist_ok=True)
    out = []

    name, p = next(iter(res['pairs'].items()))
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(p.index, p['ref'], color=c_ref, lw=1.2, label=ref_name)
    ax.plot(p.index, p['sensor'], color=c_sen, lw=1.2, label=sensor_name)
    ax.set_ylabel('PM2.5 (µg/m³)')
    ax.set_title(f'{name.capitalize()} PM2.5, times in UTC', loc='left', color=ink, fontsize=10)
    ax.legend(frameon=False, loc='upper left')
    fig.autofmt_xdate()
    path = figdir / 'colocation_timeseries.png'
    fig.savefig(path, dpi=160, bbox_inches='tight'); plt.close(fig); out.append(path)

    sets = list(res['pairs'].items())
    fig, axes = plt.subplots(1, len(sets), figsize=(3.3 * len(sets), 3.3), squeeze=False)
    for ax, (res_name, q) in zip(axes[0], sets):
        s = stats(q['ref'], q['sensor'])
        hi = float(np.nanmax([q['ref'].max(), q['sensor'].max(), 1])) * 1.05
        ax.plot([0, hi], [0, hi], color=muted, lw=1, ls='--', label='1:1')
        ax.scatter(q['ref'], q['sensor'], s=10, color=c_sen, alpha=0.6, edgecolor='none')
        if 'ols_slope' in s:
            xx = np.array([0, hi])
            ax.plot(xx, s['ols_slope'] * xx + s['ols_intercept'], color=ink, lw=1.2,
                    label=f'y = {s["ols_slope"]:.2f}x {s["ols_intercept"]:+.2f}')
            ax.set_title(f'{res_name} · n = {s["n"]} · R² = {s["r2"]:.2f}', loc='left', color=ink, fontsize=9.5)
        ax.set_xlim(0, hi); ax.set_ylim(0, hi); ax.set_aspect('equal')
        ax.set_xlabel(f'{ref_name} (µg/m³)'); ax.set_ylabel(f'{sensor_name} (µg/m³)')
        ax.legend(frameon=False, loc='upper left', fontsize=8)
    fig.tight_layout()
    path = figdir / 'colocation_scatter.png'
    fig.savefig(path, dpi=160, bbox_inches='tight'); plt.close(fig); out.append(path)

    b = res['bands']
    fig, ax = plt.subplots(figsize=(4.6, 3))
    ax.bar(b['band'], b['median_ratio'], color=c_sen, width=0.6)
    ax.axhline(1, color=muted, lw=1, ls='--')
    for i, (v, n) in enumerate(zip(b['median_ratio'], b['n'])):
        if np.isfinite(v):
            ax.text(i, v + 0.03, f'{v:.2f}\nn={n}', ha='center', va='bottom', fontsize=8, color=ink)
    ax.set_xlabel(f'{ref_name} PM2.5 band (µg/m³)'); ax.set_ylabel('Median sensor / reference')
    ax.set_ylim(0, max(1.5, float(np.nanmax(b['median_ratio'])) + 0.4) if b['median_ratio'].notna().any() else 1.5)
    ax.set_title('Ratio by concentration', loc='left', color=ink, fontsize=10)
    path = figdir / 'colocation_ratio_by_concentration.png'
    fig.savefig(path, dpi=160, bbox_inches='tight'); plt.close(fig); out.append(path)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--sensor', type=Path, required=True, help='sensor CSV (from samenmeten, ohnics, or your own)')
    ap.add_argument('--reference', type=Path, required=True, help='CSV from pm25colocation.rivm (time, value, station)')
    ap.add_argument('--time-col', default='time', help='name of the time column in the sensor CSV')
    ap.add_argument('--pm-col', default='pm25', help='name of the PM2.5 column in the sensor CSV')
    ap.add_argument('--sensor-tz', default='UTC', help='time zone of sensor times that carry none, e.g. Europe/Amsterdam')
    ap.add_argument('--periods', type=Path, default=ROOT / 'config' / 'reference_periods.json',
                    help="JSON with reference-instrument periods, or 'none'")
    ap.add_argument('--lag', default='auto', help="'auto' or whole hours to shift the sensor")
    ap.add_argument('--sensor-name', default='Sensor')
    ap.add_argument('--ref-name', default='RIVM')
    ap.add_argument('--out', type=Path, default=ROOT / 'results')
    ap.add_argument('--figures', type=Path, default=ROOT / 'figures')
    a = ap.parse_args()

    sensor = read_sensor(a.sensor, a.time_col, a.pm_col, a.sensor_tz)
    ref = pd.read_csv(a.reference)
    ref['time'] = pd.to_datetime(ref['time'], utc=True)
    periods = load_periods(a.periods, ref)
    res = analyse(sensor, ref, a.lag if a.lag == 'auto' else int(a.lag), periods)
    a.out.mkdir(parents=True, exist_ok=True)
    res['stats'].to_csv(a.out / 'colocation_stats.csv', index=False)
    write_summary(res, a.out / 'colocation_summary.md', a.sensor_name, a.ref_name)
    figs = plot(res, a.figures, a.sensor_name, a.ref_name)
    print(f'lag {res["lag_h"]:+d} h; wrote {a.out / "colocation_stats.csv"}, {a.out / "colocation_summary.md"}, '
          + ', '.join(str(f) for f in figs))


if __name__ == '__main__':
    main()
