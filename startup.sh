#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Print environment information for debugging
echo "Starting Crypto Portfolio Tracker on Railway"
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Environment variables:"
echo "PORT: $PORT"
echo "RAILWAY_ENVIRONMENT: $RAILWAY_ENVIRONMENT"
echo "DATABASE_URL exists: $(if [ -n "$DATABASE_URL" ]; then echo "Yes"; else echo "No"; fi)"

# Run database setup script
echo "Running database setup script..."
python setup_postgres_db.py

# Start the application using gunicorn
echo "Starting application with gunicorn..."
exec gunicorn app:app --timeout 120 --workers 1 --bind 0.0.0.0:$PORT
