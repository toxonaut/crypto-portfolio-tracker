import os
import sys
import time
import datetime
import logging
import requests
import json
import traceback
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

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

# Get database connection string
database_url = os.environ.get('DATABASE_URL')

# If running on Railway, use the internal connection string
if 'RAILWAY_ENVIRONMENT' in os.environ:
    logger.info("Running on Railway - using internal PostgreSQL connection")
    # Use the internal connection string for better performance and security
    database_url = "postgresql://postgres:RyWIsfflSCUOVGjjfrBvSVLGfqeGGYet@postgres.railway.internal:5432/railway"
    logger.info(f"Using internal Railway database connection")
else:
    logger.info("Running locally - using external PostgreSQL connection")
    # Local environment should have DATABASE_URL in .env file
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
    else:
        logger.info(f"Using external Railway database connection")

# If the URL starts with postgres://, change it to postgresql:// (SQLAlchemy requirement)
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

# Create database engine
db_engine = None
if database_url:
    try:
        db_engine = create_engine(database_url)
        logger.info("Database engine created successfully")
    except Exception as e:
        logger.error(f"Error creating database engine: {e}")
        db_engine = None

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

def update_worker_status_db(is_authenticated, error_message=None):
    """
    Update the worker status directly in the database
    """
    if not db_engine:
        logger.error("Cannot update worker status: database engine not available")
        return False
        
    try:
        logger.info(f"Updating worker status in database: authenticated={is_authenticated}, error={error_message}")
        
        with db_engine.connect() as connection:
            # Check if worker_status table exists
            result = connection.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'worker_status')"))
            table_exists = result.scalar()
            
            if not table_exists:
                logger.info("Creating worker_status table")
                connection.execute(text("""
                CREATE TABLE worker_status (
                    id SERIAL PRIMARY KEY,
                    last_check TIMESTAMP NOT NULL,
                    is_authenticated BOOLEAN DEFAULT FALSE,
                    last_error VARCHAR(500)
                )
                """))
                connection.commit()
                logger.info("Successfully created worker_status table")
            
            # Check if there's an existing record
            result = connection.execute(text("SELECT COUNT(*) FROM worker_status"))
            count = result.scalar()
            
            if count == 0:
                # Insert new record
                connection.execute(text("""
                INSERT INTO worker_status (last_check, is_authenticated, last_error)
                VALUES (:last_check, :is_authenticated, :last_error)
                """), {
                    "last_check": datetime.datetime.now(),
                    "is_authenticated": is_authenticated,
                    "last_error": error_message
                })
            else:
                # Update existing record
                connection.execute(text("""
                UPDATE worker_status
                SET last_check = :last_check,
                    is_authenticated = :is_authenticated,
                    last_error = :last_error
                WHERE id = (SELECT id FROM worker_status LIMIT 1)
                """), {
                    "last_check": datetime.datetime.now(),
                    "is_authenticated": is_authenticated,
                    "last_error": error_message
                })
            
            connection.commit()
            logger.info("Successfully updated worker status in database")
            return True
    except SQLAlchemyError as e:
        logger.error(f"Database error updating worker status: {e}")
        return False
    except Exception as e:
        logger.error(f"Error updating worker status in database: {e}")
        return False

def update_worker_status(is_authenticated, error_message=None):
    """
    Update the worker status - try API first, fall back to direct DB update
    """
    try:
        # First try the API endpoint
        status_url = f"{base_url.rstrip('/')}/api/update_worker_status"
        logger.info(f"Updating worker status via API: authenticated={is_authenticated}, error={error_message}")
        
        response = session.post(
            status_url,
            json={
                "is_authenticated": is_authenticated,
                "last_error": error_message
            },
            headers={
                "Content-Type": "application/json"
            },
            timeout=30
        )
        
        if response.ok:
            logger.info("Successfully updated worker status via API")
            return True
        else:
            logger.error(f"Failed to update worker status via API: {response.status_code} - {response.text}")
            # Fall back to direct database update
            logger.info("Falling back to direct database update")
            return update_worker_status_db(is_authenticated, error_message)
    except Exception as e:
        logger.error(f"Error updating worker status via API: {e}")
        # Fall back to direct database update
        logger.info("Falling back to direct database update")
        return update_worker_status_db(is_authenticated, error_message)

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
                error_message = "Got redirected to login page. The session cookie is invalid or expired."
                logger.error(error_message)
                logger.error("Please get a new session cookie by logging in manually and set it as the SESSION_COOKIE environment variable.")
                
                # Update worker status in the database
                update_worker_status_db(False, error_message)
                
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
                # Update worker status to indicate successful authentication
                update_worker_status(True)
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
