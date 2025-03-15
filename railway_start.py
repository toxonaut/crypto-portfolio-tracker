#!/usr/bin/env python
"""
Railway startup script that ensures we don't overwrite the existing database
"""
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('railway_start')

# Check if we're running on Railway
is_railway = 'RAILWAY_ENVIRONMENT' in os.environ

if is_railway:
    logger.info("Running on Railway environment")
    
    # Check if the database exists
    db_path = '/data/railway_portfolio.db'
    if os.path.exists(db_path):
        logger.info(f"Database already exists at {db_path} - preserving existing data")
    else:
        logger.info(f"Database does not exist at {db_path} - it will be created on first run")
        
    # Make sure the /data directory exists
    if not os.path.exists('/data'):
        logger.info("Creating /data directory")
        os.makedirs('/data')
else:
    logger.info("Not running on Railway - this script should only be used in Railway deployments")

# Start the application using gunicorn
logger.info("Starting application with gunicorn")
port = os.environ.get('PORT', 5000)
os.system(f"gunicorn app:app --timeout 120 --workers 1 --bind 0.0.0.0:{port}")
