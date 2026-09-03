.PHONY: up down backend frontend test build
up:
	docker compose up --build
down:
	docker compose down
backend:
	cd backend && python -m uvicorn app.main:app --reload --port 8000
frontend:
	cd frontend && npm install && npm run dev
test:
	cd backend && python -m pytest -q
build:
	cd frontend && npm run build
