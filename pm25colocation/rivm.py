"""Download hourly reference data from RIVM's Luchtmeetnet open API.

    python -m pm25colocation.rivm --start 2026-09-03 --end 2026-11-10 [--station NL10821] [--formula PM25]

Luchtmeetnet stamps each hourly value at the END of its hour (timestamp_measured =
timestamp_measured_end). This module keeps that convention: column `time` is the end
of the hour, in UTC. Values from the API are provisional until RIVM validates them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import time as _time
from pathlib import Path

import pandas as pd
import requests

from ._http import get_json

ROOT = Path(__file__).resolve().parent.parent
API = 'https://api.luchtmeetnet.nl/open_api/measurements'
CHUNK_DAYS = 7  # the API serves at most a week per request


def parse(payload: dict) -> pd.DataFrame:
    rows = [{'time': d['timestamp_measured'], 'value': d['value'], 'station': d['station_number'],
             'formula': d['formula']} for d in payload.get('data', [])]
    df = pd.DataFrame(rows, columns=['time', 'value', 'station', 'formula'])
    df['time'] = pd.to_datetime(df['time'], utc=True)
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    return df


def fetch(station: str, formula: str, start: dt.datetime, end: dt.datetime,
          session: requests.Session | None = None, pause: float = 0.5) -> pd.DataFrame:
    s = session or requests.Session()
    parts, t0 = [], start
    while t0 < end:
        t1 = min(t0 + dt.timedelta(days=CHUNK_DAYS), end)
        page = 1
        while True:
            payload = get_json(s, API, {'station_number': station, 'formula': formula,
                                   'start': t0.strftime('%Y-%m-%dT%H:%M:%SZ'), 'end': t1.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                   'page': page, 'order_by': 'timestamp_measured', 'order_direction': 'asc'})
            parts.append(parse(payload))
            if page >= payload.get('pagination', {}).get('last_page', 1):
                break
            page += 1
            _time.sleep(pause)
        t0 = t1
        _time.sleep(pause)
    df = pd.concat(parts, ignore_index=True) if parts else parse({})
    return df.drop_duplicates('time').sort_values('time').reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--station', default='NL10821', help='Luchtmeetnet station (default: Enschede-Winkelshorst)')
    ap.add_argument('--formula', default='PM25')
    ap.add_argument('--start', required=True, help='YYYY-MM-DD (UTC)')
    ap.add_argument('--end', required=True, help='YYYY-MM-DD (UTC, exclusive)')
    ap.add_argument('--out', type=Path, default=None)
    a = ap.parse_args()
    start = dt.datetime.fromisoformat(a.start).replace(tzinfo=dt.timezone.utc)
    end = dt.datetime.fromisoformat(a.end).replace(tzinfo=dt.timezone.utc)
    df = fetch(a.station, a.formula, start, end)
    out = a.out or ROOT / 'data' / 'raw' / f'rivm_{a.station}_{a.formula}.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f'wrote {out}: {len(df)} hourly values, {df["time"].min()} to {df["time"].max()}')


if __name__ == '__main__':
    main()
