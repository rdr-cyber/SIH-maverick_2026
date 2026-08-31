# MAVERICKS PROJECT Preview Run Doc

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

- Frontend: http://localhost:5173 (or next free port — Vite auto-picks)
- Backend API: http://localhost:8000/api/v1
- API docs: http://localhost:8000/docs

## Current State

- Frontend running on port **5175** (Vite picked this because 5173/5174 were occupied)
- Backend running on port **8000**
- CORS configured for ports 5173-5176
