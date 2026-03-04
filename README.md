# Nelson

Multi-LLM consensus system. Submit a question, have multiple AI models debate it through iterative critique rounds until they converge on an answer, then pick your preferred response.

## How it works

1. **Ask** — Submit an enquiry and select which models to consult
2. **Respond** — Each model answers independently
3. **Critique** — Each model reviews all other responses, identifies disagreements, and revises its answer
4. **Iterate** — Repeat until all models agree (or a round cap is hit)
5. **Choose** — Review all final responses side by side and pick the one you trust

## Tech stack

- **Frontend**: Next.js, Tailwind CSS, shadcn/ui, TanStack Query
- **Backend**: FastAPI, PydanticAI, SQLAlchemy (async), Alembic
- **Database**: PostgreSQL
- **Observability**: Pydantic Logfire
- **Infra**: Docker Compose (local), DigitalOcean App Platform (prod)

## Getting started

```bash
cp .env.example .env
# Fill in your environment variables
make up
```

Backend: http://localhost:8000
Frontend: http://localhost:3000

## Development

```bash
make up          # Start all services
make down        # Stop all services
make logs        # Tail logs
make migrate     # Run database migrations
make test        # Run all tests
make lint        # Run linters
```

## License

MIT
