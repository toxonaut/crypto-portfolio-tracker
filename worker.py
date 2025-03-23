import os
import sys
import time
import datetime
import logging
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("portfolio_worker")

# Determine if we're running on Railway
if 'RAILWAY_ENVIRONMENT' in os.environ:
    # We're on Railway, use internal connection
    logger.info("Running on Railway - using internal service connection")
    base_url = "http://crypto-portfolio-tracker.up.railway.app"
else:
    # We're running locally
    logger.info("Running locally - using localhost connection")
    base_url = "http://localhost:5000"

def add_history_entry():
    """
    Send a request to the add_history endpoint to create a new history entry
    """
    try:
        logger.info(f"Worker: Sending request to {base_url}/portfolio")
        
        # First get the current portfolio data to calculate the total value
        portfolio_response = requests.get(f"{base_url}/portfolio")
        
        if not portfolio_response.ok:
            logger.error(f"Failed to get portfolio data: {portfolio_response.status_code} - {portfolio_response.text}")
            return False
            
        portfolio_data = portfolio_response.json()
        
        if not portfolio_data.get('success'):
            logger.error(f"Portfolio data response indicates failure: {portfolio_data}")
            return False
            
        total_value = portfolio_data.get('total_value', 0)
        logger.info(f"Current portfolio total value: {total_value}")
        
        # Now send the add_history request
        logger.info(f"Worker: Sending request to {base_url}/add_history with total_value={total_value}")
        response = requests.post(
            f"{base_url}/add_history", 
            json={"total_value": total_value},
            headers={"Content-Type": "application/json"}
        )
        
        if response.ok:
            logger.info(f"Successfully added history entry with value {total_value}")
            return True
        else:
            logger.error(f"Failed to add history entry: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error in add_history_entry: {str(e)}", exc_info=True)
        return False

def main():
    """
    Main worker function that runs in an infinite loop
    """
    logger.info("Starting portfolio history worker")
    
    # Wait a bit on startup to ensure the web app is running
    time.sleep(10)
    
    interval_seconds = int(os.environ.get('HISTORY_INTERVAL_SECONDS', 3600))  # Default to 1 hour
    
    while True:
        try:
            logger.info(f"Running scheduled task (interval: {interval_seconds} seconds)")
            
            # Add a history entry
            success = add_history_entry()
            
            if success:
                logger.info(f"Task completed successfully. Sleeping for {interval_seconds} seconds.")
            else:
                logger.warning(f"Task failed. Will retry in {interval_seconds} seconds.")
                
            # Sleep until the next interval
            time.sleep(interval_seconds)
            
        except Exception as e:
            logger.error(f"Error in main worker loop: {str(e)}", exc_info=True)
            # Sleep for a shorter time if there was an error
            time.sleep(60)

if __name__ == "__main__":
    main()
