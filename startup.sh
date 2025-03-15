#!/bin/bash

# Run database setup script
python setup_postgres_db.py

# Start the application using gunicorn
exec gunicorn app:app --timeout 120 --workers 1 --bind 0.0.0.0:$PORT
