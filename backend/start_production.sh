#!/bin/bash

# Exit on error
set -e

echo "Starting Code Review GPT in Production Mode..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    exit 1
fi

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn server
echo "Starting Gunicorn server..."
gunicorn core.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class gevent \
    --timeout 300 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level info
