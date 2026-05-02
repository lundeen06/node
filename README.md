# node

**node** is a constellation management platform: situational awareness (Mapbox globe) and an AI agent that proposes maneuvers backed by a **typed Python function library** (propagation, screening, solvers, validation, gated actions).

This repository is a **scaffold**: Pydantic models and function signatures are production-shaped, but implementations are stubs (`raise NotImplementedError`). The web app is a polished **demo shell** with mock data.

## Layout

- `apps/api` — FastAPI + `node_api` package (types + `lib/` + `routes/`)
- `apps/web` — Next.js (App Router) + Mapbox GL JS + Tailwind + shadcn-style UI components
- `docs/` — architecture notes and domain glossary

## API (Python)

**Requirements:** Python 3.11+

### Using `uv` (recommended)

```bash
cd apps/api
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run mypy src
uv run uvicorn node_api.main:app --reload --host 127.0.0.1 --port 8000
```

### Using `venv` + `pip`

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn node_api.main:app --reload --host 127.0.0.1 --port 8000
```

- Health: `GET http://127.0.0.1:8000/health`
- Routers return **501** with JSON `{"detail": "..."}` while the surface stabilizes.

## Web (Next.js)

**Requirements:** Node.js 18+ (20 LTS recommended; Node 23 is fine but see troubleshooting below)

```bash
cd apps/web
npm install
cp .env.local.example .env.local
# set NEXT_PUBLIC_MAPBOX_TOKEN (public token is fine for local dev)
# optional: NEXT_PUBLIC_MAPBOX_STYLE_URL for a custom Mapbox Studio style

npm run dev
```

Open `http://localhost:3000` (redirects to `/ops`).

### Web: `pnpm` + Corepack “Cannot find matching keyid”

If `pnpm dev` fails with `Error: Cannot find matching keyid`, your **Corepack** build is too old to verify current pnpm release signatures (common with Homebrew Node + `corepack enable`). Pick one:

1. **Use npm for this repo (simplest)**  
   `npm install` and `npm run dev` — no Corepack involved.

2. **Upgrade Corepack, then use pnpm**  
   `npm install -g corepack@latest && corepack enable`  
   then `corepack prepare pnpm@latest --activate` and retry `pnpm install` / `pnpm dev`.

3. **Bypass Corepack for pnpm**  
   `corepack disable` then `npm install -g pnpm` and use that `pnpm` binary.

## Environment variables

| Variable | App | Purpose |
|----------|-----|---------|
| `NODE_*` | API | See `apps/api/src/node_api/config.py` (`NODE_APP_NAME`, `NODE_CORS_ORIGINS`, …) |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Web | Mapbox GL access token |
| `NEXT_PUBLIC_MAPBOX_STYLE_URL` | Web | Optional custom style URL (`mapbox://…` or `https://api.mapbox.com/styles/v1/…`) |
| `NEXT_PUBLIC_API_BASE_URL` | Web | Python API base URL (defaults to `http://127.0.0.1:8000`) |

## License

Proprietary / TBD — default to your org’s policy when you publish.
