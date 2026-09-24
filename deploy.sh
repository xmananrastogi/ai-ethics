#!/usr/bin/env bash

set -e

echo "Starting THOA Screening System Deployment..."

# 1. Update from remote (if using git)
# git pull origin main

# 2. Build frontend React App
echo "Building frontend..."
cd thoa-frontend
npm ci
npm run build
cd ..

# 3. Create necessary directories for Docker volumes (if not exist)
mkdir -p uploads
mkdir -p nginx/ssl
mkdir -p nginx/certbot-www

# 4. Tear down old containers and build new ones
echo "Rebuilding and restarting Docker containers..."
docker compose down
docker compose build
docker compose up -d

# 5. Run Database Migrations
echo "Running database migrations..."
# Assuming Alembic is configured, we'd run:
# docker compose exec backend alembic upgrade head
# Since Alembic might not be set up in this prototype, we'll run a quick script to create all tables:
docker compose exec backend python -c "from thoa_screening.database import Base, get_engine; Base.metadata.create_all(bind=get_engine())"

echo "Deployment completed successfully! The system is now running."
echo "Access the application at http://localhost (or https://your-domain.com)"
