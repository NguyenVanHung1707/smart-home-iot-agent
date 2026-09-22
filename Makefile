.PHONY: run voice-pi test lint format typecheck check clean deploy-pi deploy-pi-fast deploy-pi-images

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

voice-pi:
	python -m src.voice_cli

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

check: lint format test

deploy-pi:
	@echo "Building frontends locally..."
	npm --prefix frontend run build
	npm --prefix frontend-simulator run build
	@echo "Syncing code and updating Docker containers on Pi..."
	tar --exclude=".git" --exclude="node_modules" --exclude=".venv" --exclude=".pytest_cache" --exclude=".ruff_cache" --exclude="__pycache__" -czf - . | ssh -T pi "bash -c 'mkdir -p /opt/homing-hub/data /opt/homing-hub/runtime && tar -xzf - -C /opt/homing-hub/ && chmod -R 777 /opt/homing-hub/data /opt/homing-hub/runtime 2>/dev/null || true; cd /opt/homing-hub && docker compose up -d --build'"
	@echo "Deploy complete!"

deploy-pi-fast:
	@echo "Building frontends locally..."
	npm --prefix frontend run build
	npm --prefix frontend-simulator run build
	@echo "Syncing code & dist to Pi and restarting services..."
	tar --exclude=".git" --exclude="node_modules" --exclude=".venv" --exclude=".pytest_cache" --exclude=".ruff_cache" --exclude="__pycache__" -czf - . | ssh -T pi "bash -c 'mkdir -p /opt/homing-hub/data /opt/homing-hub/runtime && tar -xzf - -C /opt/homing-hub/ && chmod -R 777 /opt/homing-hub/data /opt/homing-hub/runtime 2>/dev/null || true; cd /opt/homing-hub && docker compose up -d && docker compose restart backend device-simulator frontend'"
	@echo "Fast deploy complete!"

deploy-pi-images:
	@echo "Building frontends locally..."
	npm --prefix frontend run build
	npm --prefix frontend-simulator run build
	@echo "Building ARM64 Docker images on host..."
	docker buildx build --platform linux/arm64 -t pi-p140-backend:latest -t homing-hub-backend:latest --load .
	docker buildx build --platform linux/arm64 -t pi-p140-frontend:latest -t homing-hub-frontend:latest --load ./frontend
	@echo "Streaming images to Pi..."
	docker save homing-hub-backend:latest homing-hub-frontend:latest | ssh -C pi "docker load"
	@echo "Syncing configuration and starting containers on Pi..."
	tar --exclude=".git" --exclude="node_modules" --exclude=".venv" --exclude=".pytest_cache" --exclude=".ruff_cache" --exclude="__pycache__" -czf - . | ssh -T pi "bash -c 'mkdir -p /opt/homing-hub/data /opt/homing-hub/runtime && tar -xzf - -C /opt/homing-hub/ && chmod -R 777 /opt/homing-hub/data /opt/homing-hub/runtime 2>/dev/null || true; cd /opt/homing-hub && docker compose up -d'"
	@echo "Deploy with images complete!"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
