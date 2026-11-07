import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pm25colocation import rivm

FIX = Path(__file__).resolve().parent / 'fixtures'

# ---------- data sources ----------
def test_rivm_parser_keeps_end_of_hour_stamps():
    df = rivm.parse(json.loads((FIX / 'rivm_sample.json').read_text()))
    assert list(df['value']) == [31.65, 31.69, 35.62, 39.93]
    assert df['time'].iloc[0] == pd.Timestamp('2026-11-08T00:00:00Z')
