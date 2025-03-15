#!/usr/bin/env python
"""
Railway startup script that ensures we don't overwrite the existing database
"""
import os
import sys
import logging
import shutil
import glob
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('railway_start')

# First, run the check_railway_db.py script to check if the database has data
logger.info("Running check_railway_db.py script")
subprocess.run(["python", "check_railway_db.py"], check=True)

# Print environment variables for debugging
logger.info("Environment variables:")
for key, value in os.environ.items():
    logger.info(f"  {key}={value}")

# Check if we're running on Railway
is_railway = 'RAILWAY_ENVIRONMENT' in os.environ

if is_railway:
    logger.info("Running on Railway environment")
    
    # List all files in the current directory for debugging
    logger.info("Files in current directory:")
    for file in glob.glob("*"):
        file_size = os.path.getsize(file) if os.path.isfile(file) else "directory"
        logger.info(f"  {file} - {file_size}")
    
    # List all files in the instance directory if it exists
    if os.path.exists("instance"):
        logger.info("Files in instance directory:")
        for file in glob.glob("instance/*"):
            file_size = os.path.getsize(file) if os.path.isfile(file) else "directory"
            logger.info(f"  {file} - {file_size}")
    
    # Check if the database exists
    db_path = '/data/railway_portfolio.db'
    if os.path.exists(db_path):
        logger.info(f"Database already exists at {db_path} - preserving existing data")
        logger.info(f"Database size: {os.path.getsize(db_path)} bytes")
        
        # Create a backup of the database before starting the application
        backup_path = f"{db_path}.backup"
        logger.info(f"Creating backup of database at {backup_path}")
        shutil.copy2(db_path, backup_path)
        logger.info(f"Backup created successfully")
    else:
        logger.info(f"Database does not exist at {db_path} - it will be created on first run")
        
    # Make sure the /data directory exists
    if not os.path.exists('/data'):
        logger.info("Creating /data directory")
        os.makedirs('/data')
    
    # List all files in the /data directory for debugging
    logger.info("Files in /data directory:")
    for file in glob.glob("/data/*"):
        file_size = os.path.getsize(file) if os.path.isfile(file) else "directory"
        logger.info(f"  {file} - {file_size}")
        
    # Set an environment variable to prevent database initialization
    os.environ['RAILWAY_PRESERVE_DB'] = 'true'
    logger.info("Set RAILWAY_PRESERVE_DB=true to prevent database initialization")
    
    # Check for any existing SQLite database files in the deployment
    logger.info("Searching for SQLite database files:")
    result = subprocess.run(["find", "/", "-name", "*.db", "-type", "f"], 
                           capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line:
            try:
                file_size = os.path.getsize(line)
                logger.info(f"  {line} - {file_size} bytes")
            except:
                logger.info(f"  {line} - could not get size")
else:
    logger.info("Not running on Railway - this script should only be used in Railway deployments")

# Start the application using gunicorn
logger.info("Starting application with gunicorn")
port = os.environ.get('PORT', 5000)
os.system(f"gunicorn app:app --timeout 120 --workers 1 --bind 0.0.0.0:{port}")
