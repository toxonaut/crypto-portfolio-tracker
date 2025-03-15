#!/usr/bin/env python
"""
Script to check if the Railway database has data and create a marker file if it does.
This script should be run before the application starts.
"""
import os
import sqlite3
import logging
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('check_railway_db')

# Define paths
DB_PATH = '/data/railway_portfolio.db'
MARKER_FILE = '/data/db_has_data.marker'

logger.info("Starting Railway database check script")

# Check if we're running on Railway
if 'RAILWAY_ENVIRONMENT' not in os.environ:
    logger.info("Not running on Railway - exiting")
    exit(0)

# Check if the database exists
if not os.path.exists(DB_PATH):
    logger.info(f"Database does not exist at {DB_PATH} - no action needed")
    exit(0)

# Check if the marker file already exists
if os.path.exists(MARKER_FILE):
    logger.info(f"Marker file already exists at {MARKER_FILE} - database is preserved")
    exit(0)

# Connect to the database and check if it has data
try:
    logger.info(f"Checking database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if the portfolio table exists and has data
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio'")
    if cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM portfolio")
        count = cursor.fetchone()[0]
        logger.info(f"Found {count} records in portfolio table")
        
        if count > 0:
            # Create a backup of the database
            backup_path = f"{DB_PATH}.user_data"
            logger.info(f"Creating backup of database with user data at {backup_path}")
            shutil.copy2(DB_PATH, backup_path)
            
            # Create a marker file to indicate the database has data
            with open(MARKER_FILE, 'w') as f:
                f.write(f"Database has {count} records in portfolio table")
            logger.info(f"Created marker file at {MARKER_FILE}")
            
            # Set environment variable to preserve the database
            os.environ['RAILWAY_PRESERVE_DB'] = 'true'
            logger.info("Set RAILWAY_PRESERVE_DB=true")
        else:
            logger.info("Portfolio table exists but has no data")
    else:
        logger.info("Portfolio table does not exist in the database")
    
    conn.close()
except Exception as e:
    logger.error(f"Error checking database: {str(e)}")

logger.info("Railway database check completed")
