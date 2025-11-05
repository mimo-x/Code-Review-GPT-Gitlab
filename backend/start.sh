#!/bin/bash

# Exit on error
set -e

echo "Starting Code Review GPT Django Backend..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env file with your configuration before starting the server."
    exit 1
fi

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start development server
echo "Starting Django development server..."
python manage.py runserver 0.0.0.0:8000
