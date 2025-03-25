import os
import sys
import time
import datetime
import logging
import requests
import json
import traceback
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
    base_url = "https://web-production-03de.up.railway.app/"
else:
    # We're running locally
    logger.info("Running locally - using localhost connection")
    base_url = "http://localhost:5000"

def add_history_entry():
    """
    Send a request to the add_history endpoint to create a new history entry
    """
    try:
        logger.info(f"Worker: Starting add_history task at {datetime.datetime.now().isoformat()}")
        
        # First get the current portfolio data to calculate the total value
        logger.info(f"Worker: Sending request to {base_url}/portfolio")
        
        # Add a timeout to the request to prevent hanging
        portfolio_response = requests.get(f"{base_url}/portfolio", timeout=30)
        
        if not portfolio_response.ok:
            logger.error(f"Failed to get portfolio data: {portfolio_response.status_code} - {portfolio_response.text}")
            return False
            
        portfolio_data = portfolio_response.json()
        
        if not portfolio_data.get('success'):
            logger.error(f"Portfolio data response indicates failure: {portfolio_data}")
            return False
            
        total_value = portfolio_data.get('total_value', 0)
        logger.info(f"Current portfolio total value: {total_value}")
        
        # Validate total_value
        if total_value <= 0:
            logger.error(f"Invalid total_value: {total_value}. Skipping history entry.")
            return False
            
        # Extract Bitcoin price and actual Bitcoin amount
        bitcoin_price = 0
        actual_bitcoin_amount = 0
        
        if 'bitcoin' in portfolio_data.get('data', {}):
            bitcoin_data = portfolio_data['data']['bitcoin']
            bitcoin_price = bitcoin_data.get('price', 0)
            actual_bitcoin_amount = bitcoin_data.get('total_amount', 0)
        
        # Calculate total value in BTC
        btc_value = 0
        if bitcoin_price > 0:
            btc_value = total_value / bitcoin_price
        else:
            logger.warning(f"Bitcoin price is invalid: {bitcoin_price}. BTC value will be set to 0.")
            
        logger.info(f"Bitcoin price: {bitcoin_price}, BTC value: {btc_value}, Actual BTC: {actual_bitcoin_amount}")
        
        # Ensure we have valid data before proceeding
        if bitcoin_price <= 0:
            logger.error("Cannot add history entry with invalid Bitcoin price")
            return False
        
        # Now send the add_history request
        logger.info(f"Worker: Sending request to {base_url}/add_history with total_value={total_value}")
        response = requests.post(
            f"{base_url}/add_history", 
            json={
                "total_value": total_value,
                "btc_value": btc_value,
                "actual_btc": actual_bitcoin_amount
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        logger.info(f"Add history response status: {response.status_code}")
        logger.info(f"Add history response text: {response.text}")
        
        if response.ok:
            logger.info(f"Successfully added history entry with value {total_value}")
            return True
        else:
            logger.error(f"Failed to add history entry: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error in add_history_entry: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def main():
    """
    Main worker function that runs in an infinite loop
    """
    logger.info("Starting portfolio history worker")
    
    # Wait a bit on startup to ensure the web app is running
    initial_delay = int(os.environ.get('INITIAL_DELAY_SECONDS', 30))
    logger.info(f"Waiting {initial_delay} seconds before starting...")
    time.sleep(initial_delay)
    
    # Try to add a history entry immediately on startup
    logger.info("Adding initial history entry...")
    add_history_entry()
    
    interval_seconds = int(os.environ.get('HISTORY_INTERVAL_SECONDS', 3600))  # Default to 1 hour
    logger.info(f"Worker configured with interval of {interval_seconds} seconds")
    
    while True:
        try:
            next_run = datetime.datetime.now() + datetime.timedelta(seconds=interval_seconds)
            logger.info(f"Next scheduled run at: {next_run.isoformat()}")
            
            # Sleep until the next interval
            time.sleep(interval_seconds)
            
            logger.info(f"Running scheduled task at {datetime.datetime.now().isoformat()}")
            
            # Add a history entry
            success = add_history_entry()
            
            if success:
                logger.info(f"Task completed successfully.")
            else:
                logger.warning(f"Task failed. Will retry at next interval.")
                
        except Exception as e:
            logger.error(f"Error in main worker loop: {str(e)}")
            logger.error(traceback.format_exc())
            # Sleep for a shorter time if there was an error
            time.sleep(60)

if __name__ == "__main__":
    main()
