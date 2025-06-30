#!/bin/bash

# Backend services array
BACKEND_SERVICES=(
    "image-enhance"
    "gis-extract"
    "video-generator"
    "video-qa-service"
    "prompt-optimizer"
    "video-assembler"
    "storage-service"
    "api-gateway"
    "multimodal-orchestrator"
    "job-scheduler"
)

# Frontend services array
FRONTEND_SERVICES=(
    "client-ui"
    "backoffice-ui"
    "video-viewer"
)

# Create backend service structure
for service in "${BACKEND_SERVICES[@]}"; do
    mkdir -p "services/$service"/{app/{api,core,models},tests}
    touch "services/$service/app/__init__.py"
    touch "services/$service/app/api/__init__.py"
    touch "services/$service/app/core/__init__.py"
    touch "services/$service/app/models/__init__.py"
    touch "services/$service/requirements.txt"
    touch "services/$service/Dockerfile"
    touch "services/$service/README.md"
done

# Create frontend service structure
for service in "${FRONTEND_SERVICES[@]}"; do
    mkdir -p "services/$service"/{src/{components,pages,utils,styles},public}
    touch "services/$service/package.json"
    touch "services/$service/tsconfig.json"
    touch "services/$service/vite.config.ts"
    touch "services/$service/.env"
    touch "services/$service/README.md"
    touch "services/$service/Dockerfile"
done

# Create shared module structure
mkdir -p services/shared/common/{utils,models,config}
touch services/shared/common/{utils,models,config}/__init__.py
touch services/shared/common/requirements.txt

echo "Service structure created successfully!" 