.PHONY: up down logs migrate test lint backend-test frontend-test

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	cd backend && uv run alembic upgrade head

test: backend-test frontend-test

backend-test:
	cd backend && uv run pytest -v

frontend-test:
	cd frontend && bun run test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && bun run lint
