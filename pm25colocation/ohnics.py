"""Download readings from an Ohnics sensor.

    python -m pm25colocation.ohnics [--days 30]

The sensor ID is read from the environment variable OHNICS_SENSOR_ID or from a
`.env` file in the repository root. It is deliberately not stored in the
repository: the sensor stands at a private home, and its ID leads to its location.

The `days` value sets both range and resolution on Ohnics' side (for example
1 = 10-minute values for the last day, 7 = hourly for a week, 30 = 4-hourly,
360 = daily). This is an undocumented endpoint that may change, so keep the
CSV files you download as the record of what was analysed.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
API = 'https://d.ohnics.online/m/{sensor}/{days}'
FIELDS = {'P2': 'pm25', 'P1': 'pm1', 'T': 'temp_c', 'H': 'rh'}


def sensor_id(root: Path = ROOT) -> str:
    sid = os.environ.get('OHNICS_SENSOR_ID')
    env = root / '.env'
    if not sid and env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            key, _, value = line.partition('=')
            if key.strip() == 'OHNICS_SENSOR_ID':
                sid = value.strip().strip('"\'')
    if not sid:
        raise SystemExit('Set OHNICS_SENSOR_ID in your environment or in .env (see .env.example).')
    return sid


def parse(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=['time', *FIELDS.values()])
    df = df.rename(columns=FIELDS)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    cols = ['time'] + [c for c in FIELDS.values() if c in df.columns]
    for c in cols[1:]:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df[cols].drop_duplicates('time').sort_values('time').reset_index(drop=True)


def fetch(sensor: str, days: int) -> pd.DataFrame:
    r = requests.get(API.format(sensor=sensor, days=days), timeout=60)
    r.raise_for_status()
    return parse(r.json())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--days', type=int, default=30)
    ap.add_argument('--out', type=Path, default=None)
    a = ap.parse_args()
    df = fetch(sensor_id(), a.days)
    out = a.out or ROOT / 'data' / 'raw' / f'ohnics_{a.days}d.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    step = df['time'].diff().median() if len(df) > 1 else None
    print(f'wrote {out}: {len(df)} records, step {step}, {df["time"].min()} to {df["time"].max()}')


if __name__ == '__main__':
    main()
