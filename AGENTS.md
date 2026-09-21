# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

This is a monorepo with two services:
- **`apps/api`** — Python FastAPI backend (satellite constellation management, orbital mechanics)
- **`apps/web`** — Next.js 14 frontend (3D globe dashboard, maneuver planner)

### Running services

| Service | Directory | Command | Port |
|---------|-----------|---------|------|
| API | `apps/api` | `uv run uvicorn node_api.main:app --reload --host 127.0.0.1 --port 8000` | 8000 |
| Web | `apps/web` | `npm run dev` | 3000 |

The API auto-creates an SQLite database at `apps/api/node.sqlite` on first startup. No external database setup is needed.

### Linting and testing

See the root `README.md` for the full commands. Quick reference:
- **Python lint:** `cd apps/api && uv run ruff check src tests`
- **Python types:** `cd apps/api && uv run mypy src`
- **Python tests:** `cd apps/api && uv run pytest`
- **Frontend lint:** `cd apps/web && npm run lint`
- **Frontend build:** `cd apps/web && npm run build`

### Environment files

- `apps/api/.env` — Space-Track credentials (optional; copy from `.env.example`)
- `apps/web/.env.local` — Frontend env vars (copy from `.env.local.example`). The `NEXT_PUBLIC_API_BASE_URL` defaults to `http://127.0.0.1:8000`.

### Gotchas

- The globe visualization requires a `NEXT_PUBLIC_MAPBOX_TOKEN` in `apps/web/.env.local` for full Mapbox rendering. Without it, a fallback or configuration message is shown — this is expected and non-blocking.
- Many API routes beyond `/health`, `/spacecraft/`, and `/satellites/tles` return 501 (Not Implemented) — this is by design as the codebase is a scaffold.
- The web app redirects `/` to `/ops` automatically.
- Node.js 20 LTS is recommended. The project uses `npm` (lockfile: `package-lock.json`).
- Python 3.11+ is required; `uv` is the recommended package manager for the API.
