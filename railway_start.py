#!/usr/bin/env python
import os
import sys
import logging
import subprocess
from app import db, app

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_database():
    """
    Create all database tables if they don't exist.
    """
    try:
        # When running on Railway, always use the internal connection string
        database_url = "postgresql://postgres:RyWIsfflSCUOVGjjfrBvSVLGfqeGGYet@postgres.railway.internal:5432/railway"
        
        logger.info(f"Setting up database using internal Railway connection: postgres.railway.internal:5432/railway")
        
        with app.app_context():
            # Create all tables
            db.create_all()
            
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        return False

def start_application():
    """
    Start the application using gunicorn.
    """
    try:
        port = os.environ.get('PORT', '5000')
        logger.info(f"Starting application on port {port}")
        
        # Set Railway environment variable
        os.environ['RAILWAY_ENVIRONMENT'] = 'production'
        
        # Start gunicorn
        cmd = f"gunicorn app:app --timeout 120 --workers 1 --bind 0.0.0.0:{port}"
        logger.info(f"Running command: {cmd}")
        
        # Execute the command
        subprocess.run(cmd, shell=True, check=True)
        
    except Exception as e:
        logger.error(f"Error starting application: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    # Print environment information for debugging
    logger.info("Starting Crypto Portfolio Tracker on Railway")
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Environment variables:")
    logger.info(f"PORT: {os.environ.get('PORT')}")
    logger.info(f"DATABASE_URL exists: {'Yes' if os.environ.get('DATABASE_URL') else 'No'}")
    
    # Setup database
    if not setup_database():
        logger.error("Failed to set up database, exiting")
        sys.exit(1)
    
    # Start application
    start_application()
