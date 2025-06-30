.PHONY: help install test lint clean build run

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies for all services
	@echo "Installing backend dependencies..."
	@for service in services/*/requirements.txt; do \
		pip install -r $$service; \
	done
	@echo "Installing frontend dependencies..."
	@for service in services/{client-ui,backoffice-ui,video-viewer}; do \
		cd $$service && npm install && cd ../..; \
	done

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	@echo "Running backend tests..."
	@for service in services/*/tests; do \
		python -m pytest $$service; \
	done

test-frontend: ## Run frontend tests
	@echo "Running frontend tests..."
	@for service in services/{client-ui,backoffice-ui,video-viewer}; do \
		cd $$service && npm test && cd ../..; \
	done

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Run backend linters
	@echo "Running backend linters..."
	@for service in services/*/; do \
		flake8 $$service; \
		black $$service --check; \
		isort $$service --check-only; \
	done

lint-frontend: ## Run frontend linters
	@echo "Running frontend linters..."
	@for service in services/{client-ui,backoffice-ui,video-viewer}; do \
		cd $$service && npm run lint && cd ../..; \
	done

clean: ## Clean build artifacts
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "node_modules" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +

build: ## Build all services
	docker-compose build

run: ## Run all services
	docker-compose up

stop: ## Stop all services
	docker-compose down

logs: ## View logs
	docker-compose logs -f

migrate: ## Run database migrations
	@echo "Running database migrations..."
	cd services/api-gateway && alembic upgrade head 