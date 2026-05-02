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

Open `http://localhost:3000` (redirects to `/ops`). Prefer a normal browser window (Chrome/Firefox/Safari), not a stripped-down embedded preview, so `/_next/static/...` assets load reliably.

### Web: Console “SES / lockdown-install.js”

That line comes from a **browser extension** (often a crypto wallet or “secure JS” shim), not from this app. It is safe to ignore for local dev, or use a **private/incognito** window with extensions disabled if you want a clean console.

### Web: “Extra attributes from the server: data-gr-ext-installed …”

**Grammarly** (and similar extensions) inject attributes into `<body>` before React hydrates. The root layout uses `suppressHydrationWarning` on `<html>` and `<body>` so React does not warn. You can still disable Grammarly on `localhost` if you prefer.

### Web: 500 / `ERR_ABORTED` on `/_next/static/...` (`layout.css`, `main-app.js`, `webpack.js`, …)

Those URLs are **compiled on demand** in `next dev`. A **500** almost always means the **dev compiler failed** for that asset — the real error is in the **terminal where `next dev` is running**, not only in the browser.

**Common causes on macOS**

1. **`EMFILE: too many open files, watch`** (Watchpack) — too many file watchers (multiple Next apps, editors, Dropbox on the repo). Webpack stops compiling reliably → **500** on chunks. Fixes:
   - Stop other `next dev` / Vite processes; run **`npm run dev:clean`** from `apps/web`.
   - In the same terminal: **`ulimit -n 65536`** then **`npm run dev`**.
   - Or avoid native watchers: **`npm run dev:poll`** (uses polling; slightly more CPU).

2. **Wrong port** — if `3000` is busy, Next prints **`http://localhost:3001`**. Opening `3000` while the server is on **`3001`** hits whatever else is on 3000 (often broken HTML / wrong errors).

3. **Stale `.next` / tab** — stop dev, **`npm run dev:clean`**, hard reload (Cmd+Shift+R), or try incognito if extensions block `/_next/…`.

You may still see a harmless webpack log: **`PackFileCacheStrategy` / `Unable to snapshot resolve dependencies`** — unrelated to the 500 above.

### Web: Mapbox blank map or build issues

1. **`apps/web/next.config.js`** — must include `transpilePackages: ["mapbox-gl"]` so webpack transpiles Mapbox (otherwise the map often stays blank).
2. **`apps/web/src/components/globe/Globe.tsx`** — client map setup; check the browser console for `[Globe]` logs if something fails.
3. **`apps/web/.env.local`** — `NEXT_PUBLIC_MAPBOX_TOKEN` (and optional `NEXT_PUBLIC_MAPBOX_STYLE_URL`); restart `npm run dev` after changes.

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
| `NEXT_PUBLIC_MAPBOX_STYLE_URL` | Web | Optional custom style (prefer `mapbox://styles/USER/STYLE_ID` from Studio). Full `https://api.mapbox.com/styles/v1/...` URLs are normalized to `mapbox://`. If Mapbox returns **404**, the username/style id is wrong, the style was deleted, or your **token is not from the Mapbox account that owns** that style. |
| `NEXT_PUBLIC_MAPBOX_GLOBE` | Web | Optional: `1` = force globe, `0` = force flat map. Auto: globe only for core `mapbox://styles/mapbox/…` styles without a custom style URL. |
| `NEXT_PUBLIC_API_BASE_URL` | Web | Python API base URL (defaults to `http://127.0.0.1:8000`) |

## License

Proprietary / TBD — default to your org’s policy when you publish.
