# Olympus

Desktop control plane for orchestrating AI agents with FastAPI + LangGraph backend and Electron + React frontend.

## Project Layout

- `backend/` - Python API, orchestration graph, and agent logic
- `main/` - Electron main process and preload scripts
- `renderer/` - React renderer app
- `shared/` - shared schema/types
- `docker-compose.yml` - PostgreSQL + Redis for local dev

## Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- Docker Desktop (for PostgreSQL/Redis)

## Setup

### Quick setup script

```bash
bash setup.sh
```

### Manual setup

1. Start infra:
   ```bash
   docker-compose up -d
   ```
2. Install desktop dependencies:
   ```bash
   npm install
   cd renderer && npm install
   cd ..
   ```
3. Install backend dependencies:
   ```bash
   cd backend
   python -m venv venv
   # Git Bash on Windows:
   source venv/Scripts/activate
   # Linux/macOS/WSL:
   # source venv/bin/activate
   pip install -r requirements.txt
   ```

## Run

Use two terminals.

1. Backend:
   ```bash
   cd backend
   source venv/Scripts/activate
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. Desktop app:
   ```bash
   npm run dev
   ```

## Notes

- Copy `.env.example` to `.env` and fill required values before running.
- Backend health check: `GET /health`.
