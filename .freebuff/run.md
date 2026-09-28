# TRILOK TRACE Preview Run Doc

## How to Reproduce Uncommitted Artifacts

1. No `.env.local` needed — local mode uses SQLite with zero configuration.
2. Backend needs no pre-build step.

## How to Run the Servers

### Backend (FastAPI on port 8000)

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The backend auto-creates SQLite DB and seeds synthetic data on first startup.

### Frontend (Vite dev server with API proxy)

```bash
cd frontend
npm run dev
```

The Vite config (`vite.config.ts`) includes a proxy: `/api` requests are forwarded to `http://127.0.0.1:8000`.

All frontend API clients use relative URLs (`/api/v1/...`) which go through the Vite proxy.
This avoids CORS issues and works regardless of which port Vite picks.

### Access

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api/v1
- API docs: http://localhost:8000/docs

### Demo Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | ami | ami43210 |
| Senior Analyst | amra | amra4321 |
| Analyst | tumi | tumi1430 |

## Current State (verified 2026-09-01)

- Frontend: port **5173** (Vite) — PID 3520
- Backend: port **8000** (uvicorn) — PID 7728
- API proxy: `/api` → `http://127.0.0.1:8000` via Vite config
- CORS: ports 5173–5176 whitelisted
- Dashboard: real API data verified (13 actors, 17 personas, 56 identifiers, RCS 62.7 MEDIUM)
