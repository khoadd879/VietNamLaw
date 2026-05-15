.PHONY: install install-backend install-frontend dev-backend dev-frontend clean

install: install-backend install-frontend

install-backend:
	pip install -r backend/requirements.txt

install-frontend:
	cd frontend && npm install

dev-backend:
	cd backend && uvicorn main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

clean:
	rm -rf frontend/node_modules
	rm -rf backend/__pycache__
	rm -rf backend/.venv
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name ".env" -type f -delete 2>/dev/null || true