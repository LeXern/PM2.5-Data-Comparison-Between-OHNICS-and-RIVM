import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pm25colocation import ohnics, rivm, samenmeten

FIX = Path(__file__).resolve().parent / 'fixtures'

# ---------- data sources ----------
def test_rivm_parser_keeps_end_of_hour_stamps():
    df = rivm.parse(json.loads((FIX / 'rivm_sample.json').read_text()))
    assert list(df['value']) == [31.65, 31.69, 35.62, 39.93]
    assert df['time'].iloc[0] == pd.Timestamp('2026-11-08T00:00:00Z')


def test_ohnics_parser_renames_fields():
    df = ohnics.parse(json.loads((FIX / 'ohnics_sample.json').read_text()))
    assert list(df.columns) == ['time', 'pm25', 'pm1', 'temp_c', 'rh']
    assert df['pm25'].iloc[0] == 31.01 and str(df['time'].dt.tz) == 'UTC'


def test_ohnics_id_never_has_a_default(tmp_path, monkeypatch):
    monkeypatch.delenv('OHNICS_SENSOR_ID', raising=False)
    with pytest.raises(SystemExit):
        ohnics.sensor_id(tmp_path)
    (tmp_path / '.env').write_text('OHNICS_SENSOR_ID=abc-1\n')
    assert ohnics.sensor_id(tmp_path) == 'abc-1'


def test_samenmeten_finds_raw_and_calibrated_series():
    thing = json.loads((FIX / 'samenmeten_thing.json').read_text())['value'][0]
    assert samenmeten.datastream_id(thing, 'pm25') == 56006
    assert samenmeten.datastream_id(thing, 'pm25_kal') == 56007
    with pytest.raises(SystemExit):
        samenmeten.datastream_id(thing, 'no2')
    text = samenmeten.describe(thing)
    assert 'NL10821' in text and 'OHN_tw-4222' in text


def test_samenmeten_parser():
    df = samenmeten.parse(json.loads((FIX / 'samenmeten_observations.json').read_text()))
    assert list(df.columns) == ['time', 'pm25'] and list(df['pm25']) == [2.57, 2.82]
    assert df['time'].iloc[1] == pd.Timestamp('2026-09-20T01:00:00Z')
