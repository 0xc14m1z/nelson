# Nelson

Multi-LLM consensus system. Submit a question, have multiple AI models debate it through iterative critique rounds until they converge on an answer, then pick your preferred response.

## How it works

1. **Ask** — Submit an enquiry and select which models to consult
2. **Respond** — Each model answers independently
3. **Critique** — Each model reviews all other responses, identifies disagreements, and revises its answer
4. **Iterate** — Repeat until all models agree (or a round cap is hit)
5. **Choose** — Review all final responses side by side and pick the one you trust

## Tech stack

- **Frontend**: Next.js, Mantine, TanStack Query
- **Backend**: FastAPI, PydanticAI, SQLAlchemy (async), Alembic
- **Database**: PostgreSQL
- **Observability**: Pydantic Logfire
- **Infra**: Docker Compose (local), DigitalOcean App Platform (prod)

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (for running all services)
- [uv](https://docs.astral.sh/uv/) (Python package manager, for local backend dev)
- [Bun](https://bun.sh/) (JavaScript runtime, for local frontend dev)

## Getting started

```bash
cp .env.example .env
make up
```

This starts three containers via Docker Compose:
- **Postgres 16** on port 5432
- **FastAPI backend** on port 8000
- **Next.js frontend** on port 3000

Run database migrations (creates tables and seeds provider/model data):

```bash
make migrate
```

Verify everything is working:

```bash
# Backend health check
curl http://localhost:8000/health
# → {"status":"ok"}

# Frontend
open http://localhost:3000
```

## Development

```bash
make up          # Start all services (builds images first)
make down        # Stop all services
make logs        # Tail logs from all services
make migrate     # Run Alembic migrations (uses uv)
make test        # Run backend + frontend tests
make backend-test  # Backend tests only (uses uv + pytest)
make frontend-test # Frontend tests only (uses bun)
make lint        # Run ruff (backend) + eslint (frontend)
```

### Running backend tests locally (without Docker)

Requires a running Postgres instance (e.g. via `docker compose up db`):

```bash
cd backend
uv sync --dev
uv run pytest -v
```

## License

MIT
