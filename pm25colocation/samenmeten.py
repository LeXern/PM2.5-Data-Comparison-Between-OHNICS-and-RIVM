"""Download hourly sensor data from RIVM's Samen Meten portal (open, no login).

    python -m pm25colocation.samenmeten --info OHN_tw-4222
    python -m pm25colocation.samenmeten --sensor OHN_tw-4222 --start 2026-09-19 --end 2026-10-01 [--calibrated]

Samen Meten (https://samenmeten.rivm.nl/dataportaal/) collects citizen and research
sensors across the Netherlands, including every Ohnics unit (named OHN_<id>). It serves
hourly values for any date range through an OGC SensorThings API. For PM2.5 each
sensor has two series: `pm25` (the sensor's own values) and `pm25_kal` (RIVM's
calibrated version). RIVM also records which reference station is nearest to each
sensor; `--info` prints it, so you know which station to compare with.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import time as _time
from pathlib import Path

import pandas as pd
import requests

from ._http import get_json

ROOT = Path(__file__).resolve().parent.parent
API = 'https://api-samenmeten.rivm.nl/v1.0'
PAGE = 1000


def find_thing(name: str, session: requests.Session | None = None) -> dict:
    s = session or requests.Session()
    payload = get_json(s, f'{API}/Things', {'$filter': f"name eq '{name}'", '$expand': 'Datastreams,Locations'})
    things = payload.get('value', [])
    if not things:
        raise SystemExit(f'No sensor called {name!r} on Samen Meten. Check the name on samenmeten.rivm.nl/dataportaal.')
    return things[0]


def datastream_id(thing: dict, quantity: str) -> int:
    """quantity is 'pm25' (sensor values) or 'pm25_kal' (RIVM-calibrated)."""
    for ds in thing.get('Datastreams', []):
        if re.search(rf'-{re.escape(quantity)}$', ds['name']):
            return ds['@iot.id']
    names = ', '.join(ds['name'] for ds in thing.get('Datastreams', []))
    raise SystemExit(f'{thing["name"]} has no {quantity} series. Available: {names}')


def parse(payload: dict) -> pd.DataFrame:
    rows = [{'time': o['phenomenonTime'], 'pm25': o['result']} for o in payload.get('value', [])]
    df = pd.DataFrame(rows, columns=['time', 'pm25'])
    df['time'] = pd.to_datetime(df['time'], utc=True)
    df['pm25'] = pd.to_numeric(df['pm25'], errors='coerce')
    return df


def fetch(ds_id: int, start: dt.datetime, end: dt.datetime, session: requests.Session | None = None,
          pause: float = 0.3) -> pd.DataFrame:
    s = session or requests.Session()
    url = f'{API}/Datastreams({ds_id})/Observations'
    params = {'$filter': f"phenomenonTime ge {start:%Y-%m-%dT%H:%M:%SZ} and phenomenonTime lt {end:%Y-%m-%dT%H:%M:%SZ}",
              '$orderby': 'phenomenonTime asc', '$top': PAGE, '$select': 'phenomenonTime,result'}
    parts = []
    while url:
        payload = get_json(s, url, params)
        parts.append(parse(payload))
        url, params = payload.get('@iot.nextLink'), None  # the next link carries its own query
        if url:
            _time.sleep(pause)
    df = pd.concat(parts, ignore_index=True) if parts else parse({})
    return df.drop_duplicates('time').sort_values('time').reset_index(drop=True)


def describe(thing: dict) -> str:
    p = thing.get('properties') or {}
    lines = [f'Sensor: {thing["name"]} (owner: {p.get("owner", "?")}, project: {p.get("project", "?")})',
             f'Nearest PM2.5 reference station: {p.get("pm25closecode", "?")} '
             f'(regional: {p.get("pm25regiocode", "?")}, urban: {p.get("pm25stadcode", "?")})',
             'Series: ' + ', '.join(ds['name'] for ds in thing.get('Datastreams', []))]
    locs = thing.get('Locations') or []
    if locs:
        lon, lat = locs[0]['location']['coordinates'][:2]
        lines.append(f'Location: {lat:.4f} N, {lon:.4f} E')
    return '\n'.join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--sensor', '--info', dest='sensor', required=True, help='Samen Meten name, e.g. OHN_tw-4222')
    ap.add_argument('--start', help='YYYY-MM-DD (UTC)')
    ap.add_argument('--end', help='YYYY-MM-DD (UTC, exclusive)')
    ap.add_argument('--calibrated', action='store_true', help="use RIVM's calibrated series (pm25_kal)")
    ap.add_argument('--out', type=Path, default=None)
    a = ap.parse_args()

    thing = find_thing(a.sensor)
    if not (a.start and a.end):
        print(describe(thing))
        return
    quantity = 'pm25_kal' if a.calibrated else 'pm25'
    start = dt.datetime.fromisoformat(a.start).replace(tzinfo=dt.timezone.utc)
    end = dt.datetime.fromisoformat(a.end).replace(tzinfo=dt.timezone.utc)
    df = fetch(datastream_id(thing, quantity), start, end)
    out = a.out or ROOT / 'data' / 'raw' / f'samenmeten_{a.sensor}_{quantity}.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    station = (thing.get('properties') or {}).get('pm25closecode')
    print(f'wrote {out}: {len(df)} hourly values, {df["time"].min()} to {df["time"].max()}'
          + (f'\nnearest PM2.5 reference station: {station}' if station else ''))


if __name__ == '__main__':
    main()
