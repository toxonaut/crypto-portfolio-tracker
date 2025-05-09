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

# Get the base URL from environment variable or use a default
base_url = os.environ.get('BASE_URL', 'https://crypto-tracker.up.railway.app')
session_cookie = os.environ.get('SESSION_COOKIE')
session_cookie_name = os.environ.get('SESSION_COOKIE_NAME', 'session')

# Log the configuration
logger.info(f"Worker starting with BASE_URL={base_url}")
logger.info(f"Session cookie is {'set' if session_cookie else 'NOT SET'}")

# Create a session that will persist cookies
session = requests.Session()

# Set the session cookie if provided
if session_cookie:
    # Extract domain from base_url
    domain = base_url.split('//')[1].split('/')[0]
    session.cookies.set(session_cookie_name, session_cookie, domain=domain)
    logger.info(f"Set session cookie: {session_cookie_name}={session_cookie[:5]}...{session_cookie[-5:] if len(session_cookie) > 10 else session_cookie}")

def add_history_entry():
    """
    Fetch the current portfolio value and add a history entry
    """
    max_retries = 3
    retry_delay = 60  # seconds
    
    for retry in range(max_retries):
        try:
            logger.info(f"Worker: Starting add_history task at {datetime.datetime.now().isoformat()} (Attempt {retry+1}/{max_retries})")
            
            # First get the current portfolio data to calculate the total value
            portfolio_url = f"{base_url.rstrip('/')}/portfolio"
            logger.info(f"Worker: Sending request to {portfolio_url}")
            
            # Use the session to maintain cookies
            portfolio_response = session.get(
                portfolio_url, 
                timeout=30
            )
            
            # Log the response details
            logger.info(f"Response status code: {portfolio_response.status_code}")
            
            # Check if we got redirected to the login page
            if 'login' in portfolio_response.url.lower() or 'sign in with google' in portfolio_response.text.lower():
                logger.error("Got redirected to login page. The session cookie is invalid or expired.")
                logger.error("Please get a new session cookie by logging in manually and set it as the SESSION_COOKIE environment variable.")
                return False
            
            # Check if we got a successful response
            if portfolio_response.status_code != 200:
                logger.error(f"Failed to get portfolio data. Status code: {portfolio_response.status_code}")
                logger.error(f"Response content: {portfolio_response.text[:500]}...")
                raise Exception(f"Failed to get portfolio data. Status code: {portfolio_response.status_code}")
            
            try:
                portfolio_data = portfolio_response.json()
                logger.info(f"Successfully parsed portfolio data as JSON")
            except json.JSONDecodeError:
                # If we can't parse as JSON, it's likely we got HTML
                logger.error("Received HTML response instead of JSON.")
                logger.error(f"First 1000 characters of response: {portfolio_response.text[:1000]}")
                raise Exception("Failed to parse portfolio data as JSON")
            
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
            response = session.post(
                add_history_url, 
                json={
                    "total_value": total_value,
                    "btc_value": btc_value,
                    "actual_btc": actual_bitcoin_amount
                },
                headers={
                    "Content-Type": "application/json"
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
    if not session_cookie:
        logger.error("SESSION_COOKIE environment variable is not set. Cannot authenticate with the web application.")
        logger.error("Please set the SESSION_COOKIE environment variable to a valid session cookie from the web application.")
        return
    
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
