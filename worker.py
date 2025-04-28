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
    base_url = "https://crypto-tracker.up.railway.app"
else:
    # We're running locally
    logger.info("Running locally - using localhost connection")
    base_url = "http://localhost:5000"

def add_history_entry():
    """
    Send a request to the add_history endpoint to create a new history entry
    """
    max_retries = 3
    retry_delay = 60  # seconds
    
    for retry in range(max_retries):
        try:
            logger.info(f"Worker: Starting add_history task at {datetime.datetime.now().isoformat()} (Attempt {retry+1}/{max_retries})")
            
            # First get the current portfolio data to calculate the total value
            # Use the standard endpoint with the worker key header
            portfolio_url = f"{base_url.rstrip('/')}/portfolio"
            logger.info(f"Worker: Sending request to {portfolio_url}")
            
            # Add a timeout to the request to prevent hanging
            portfolio_response = requests.get(
                portfolio_url, 
                timeout=30,
                headers={
                    "X-Worker-Key": os.environ.get("WORKER_KEY", "default_worker_key")
                }
            )
            
            # Log the raw response for debugging
            logger.info(f"Response status code: {portfolio_response.status_code}")
            logger.info(f"Response headers: {portfolio_response.headers}")
            logger.info(f"Response content (first 500 chars): {portfolio_response.text[:500]}")
            
            if not portfolio_response.ok:
                logger.error(f"Failed to get portfolio data: {portfolio_response.status_code} - {portfolio_response.text}")
                
                # Check if we need to authenticate
                if portfolio_response.status_code == 401 or portfolio_response.status_code == 302 or 'login' in portfolio_response.text.lower():
                    logger.error("Authentication required. The worker needs to be authenticated to access the portfolio data.")
                    logger.error("Please add a session cookie or implement an authentication mechanism for the worker.")
                    
                    if retry < max_retries - 1:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                    
                return False
                
            try:
                portfolio_data = portfolio_response.json()
            except Exception as e:
                logger.error(f"Error parsing JSON response: {e}")
                logger.error(f"Response content: {portfolio_response.text}")
                
                # Check if the response contains HTML instead of JSON (likely a login page)
                if '<html' in portfolio_response.text.lower():
                    logger.error("Received HTML response instead of JSON. This likely means authentication is required.")
                    logger.error("Please add a session cookie or implement an authentication mechanism for the worker.")
                
                if retry < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                
                return False
            
            if not portfolio_data.get('success'):
                logger.error(f"Portfolio data response indicates failure: {portfolio_data}")
                
                if retry < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                
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
            add_history_url = f"{base_url.rstrip('/')}/add_history"
            logger.info(f"Worker: Sending request to {add_history_url} with total_value={total_value}")
            response = requests.post(
                add_history_url, 
                json={
                    "total_value": total_value,
                    "btc_value": btc_value,
                    "actual_btc": actual_bitcoin_amount
                },
                headers={
                    "Content-Type": "application/json",
                    "X-Worker-Key": os.environ.get("WORKER_KEY", "default_worker_key")
                },
                timeout=30
            )
            
            logger.info(f"Add history response status: {response.status_code}")
            logger.info(f"Add history response text: {response.text}")
            
            if response.ok:
                logger.info(f"Successfully added history entry with value {total_value}")
                return True
            else:
                logger.error(f"Failed to add history entry: {response.status_code} - {response.text}")
                
                if retry < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                
                return False
                
        except Exception as e:
            logger.error(f"Error in add_history_entry: {e}")
            logger.error(traceback.format_exc())
            
            if retry < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                continue
            
            return False
    
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
