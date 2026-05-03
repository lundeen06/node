#!/usr/bin/env python3
"""Print JSON from GET /satellites/tles (Space-Track-backed).

Requires the API running locally and Space-Track credentials in apps/api/.env .

Usage (from repo root or apps/api):

    uv run uvicorn node_api.main:app --host 127.0.0.1 --port 8000

In another shell (from apps/api):

    uv run python scripts/print_satellites_tles.py 25544
    uv run python scripts/print_satellites_tles.py 25544 48274

Environment:

    NODE_API_BASE — default http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def main() -> None:
    base = os.environ.get("NODE_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    ids = sys.argv[1:]
    if not ids:
        ids = ["25544"]
    q = ",".join(ids)
    url = f"{base}/satellites/tles?norad_ids={urllib.parse.quote(q, safe=',')}"
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        raise SystemExit(exc.code) from exc
    data = json.loads(body)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
