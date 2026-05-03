# node API

Python package `node_api`: Pydantic domain models, layered function library (stubs), and FastAPI routes.

See the monorepo [README](../../README.md) for full setup.

## Credentials (Space-Track)

1. Copy `.env.example` in this directory to `.env`.
2. Set `NODE_SPACETRACK_IDENTITY`, `NODE_SPACETRACK_PASSWORD`, and `NODE_SPACETRACK_USER_AGENT` with your [Space-Track](https://www.space-track.org) account.

Settings load `apps/api/.env` automatically (even when you run uvicorn from another working directory).

## Space-Track over HTTP

With credentials configured and the API running:

```bash
curl "http://127.0.0.1:8000/satellites/tles?norad_ids=25544"
```

Or:

```bash
uv run python scripts/print_satellites_tles.py 25544
```

**What you get:** each item has `tle` (parsed lines + epoch) and `gp`, the raw Space-Track **gp** row (`OBJECT_NAME`, `EPOCH`, `MEAN_MOTION`, `INCLINATION`, element-set metadata, etc.). Use the TLE lines with `propagate_sgp4`; use `gp` for labels, sorting, or screening.

**Filtering:** `norad_ids` only selects catalog numbers. For other Space-Track filters (time windows, operators like `>now-7`, combined predicates), use the Python helper `query_gp("PREDICATE/...")` in `node_api.lib.ingress.space_track` — see [Space-Track REST API](https://www.space-track.org/documentation#/api-restApi) (predicate chain between `gp/` and `/format/json`). Keep queries small and respect rate limits.

## Spacecraft catalog (SQLite + Space-Track)

The API creates **`apps/api/node.sqlite`** on startup (override with **`NODE_DATABASE_URL`** if you use another SQLAlchemy URL).

1. **Register** — fetch latest GP for a NORAD id and persist full snapshot + TLE + derived classical elements:

```bash
curl -X POST http://127.0.0.1:8000/spacecraft/register ^
  -H "Content-Type: application/json" ^
  -d "{\"sat_id\":\"iss\",\"name\":\"ISS\",\"norad_catalog_id\":25544,\"purpose\":\"crew\"}"
```

(PowerShell: use `curl.exe` or single-line JSON.)

2. **List** — `GET http://127.0.0.1:8000/spacecraft/`

3. **Detail** — `GET http://127.0.0.1:8000/spacecraft/{sat_id}` — returns `gp` (raw Space-Track fields), `tle_line*`, `oe_vector` (`[a,e,i,Ω,ω,M]` in m / rad).

4. **Refresh all** — `POST http://127.0.0.1:8000/spacecraft/sync`

5. **Trajectory** — `GET http://127.0.0.1:8000/spacecraft/{sat_id}/trajectory?duration_minutes=90&step_seconds=60&include_llh=true` — propagates stored mean elements with `physics.propulsion.util_dyn.propagate_oe` (+ J2) and `oe_to_pv`.

In-library TLE arcs use the same scheme via **`propagate_sgp4`** (SGP4 at epoch → elements → `propagate_oe`).

### Constellation-bounded import (Starlink, Kuiper, Planet, Galileo, GPS)

Space-Track does not expose a “constellation id” field — we bound results with **`OBJECT_NAME`** prefix predicates (`FIELD/name~~` means “starts with `name`”). Presets are heuristic; adjust `node_api.lib.ingress.constellation_presets` if names change.

- **List presets:** `GET http://127.0.0.1:8000/spacecraft/constellation-presets`
- **Import up to N rows:** `POST http://127.0.0.1:8000/spacecraft/import-constellation` with JSON e.g.
  `{"preset":"starlink","limit":400,"purpose":"Starlink","sat_id_prefix":"sl"}`

Use a conservative **`limit`** and respect Space-Track rate limits; full Starlink is thousands of objects.
