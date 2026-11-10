"""Shared HTTP helper: retry requests that fail now and then.

The Samen Meten API occasionally answers a valid request with 400 or 5xx and then
serves the identical request a moment later, so those codes are retried with a
growing pause. Authentication errors and missing pages (401, 403, 404) are not.
"""
from __future__ import annotations

import time

import requests

RETRY_STATUS = {400, 408, 425, 429, 500, 502, 503, 504}


def get_json(session: requests.Session, url: str, params: dict | None = None, tries: int = 4,
             wait: float = 2.0, timeout: int = 60):
    for attempt in range(1, tries + 1):
        try:
            r = session.get(url, params=params, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == tries:
                raise
        else:
            if r.status_code not in RETRY_STATUS or attempt == tries:
                r.raise_for_status()
                return r.json()
        time.sleep(wait * attempt)
