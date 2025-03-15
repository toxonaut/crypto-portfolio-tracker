from app import app, db, Portfolio, PortfolioHistory
import datetime
import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the database URL from environment variable
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@containers-us-west-141.railway.app:7617/railway')

# If the URL starts with postgres://, change it to postgresql:// (SQLAlchemy requirement)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Bitcoin entries to add
bitcoin_entries = [
    ("bitcoin", "SolvBTC Arbitrum Avalon", 1, 0),
    ("bitcoin", "Swell Earn BTC Vault", 1, 0),
    ("bitcoin", "Ledger", 50, 0),
    ("bitcoin", "Frankencoin coll", 0.2, 0),
    ("bitcoin", "cbBTC ZeroLend", 3.0677, 0),
    ("bitcoin", "SONIC SolvBTC Silo", 1.0049, 0),
    ("bitcoin", "Aave WBTC", 1.5, 0),
    ("bitcoin", "WBTC Free", 1.5, 0),
    ("bitcoin", "Solana Raydium", 3.2845, 0),
    ("bitcoin", "Nexo", 34.7484, 0),
    ("bitcoin", "Swell swBTC", 1.049, 0),
    ("bitcoin", "swapX Sonic", 1.011, 0),
    ("bitcoin", "LBTC in Lombard vault", 2.9965, 0),
    ("bitcoin", "cbBTC Base Aave", 2, 0),
    ("bitcoin", "Gate.io Earn", 5.0054, 0),
    ("bitcoin", "cbBTC Euler finance", 0.861, 0),
    ("bitcoin", "WBTC Across", 3.0043, 0),
    ("bitcoin", "WBTC Strike", 3.0044, 0),
    ("bitcoin", "BTC Kraken", 5.2453, 0),
    ("bitcoin", "cbBTC Avalon Base", 0.0868, 0),
    ("bitcoin", "Zerolend WBTC & LBTC", 4.1316, 0),
    ("bitcoin", "cbBTC zero base", 0.8, 0),
    ("bitcoin", "eBTC Zerolend", 1, 0)
]

def update_railway_database():
    """Update the Railway PostgreSQL database with Bitcoin entries"""
    logger.info("Updating Railway PostgreSQL database with Bitcoin entries...")
    logger.info(f"Using database URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'PostgreSQL'}")
    
    try:
        # Create a SQLAlchemy engine and session
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Clear existing portfolio data
        logger.info("Clearing existing portfolio data...")
        session.query(Portfolio).delete()
        
        # Add new Bitcoin entries
        logger.info("Adding new Bitcoin entries...")
        for coin_id, source, amount, apy in bitcoin_entries:
            portfolio_entry = Portfolio(
                coin_id=coin_id,
                source=source,
                amount=amount,
                apy=apy
            )
            session.add(portfolio_entry)
        
        # Calculate total Bitcoin and value
        total_btc = sum(entry[2] for entry in bitcoin_entries)
        btc_price = 65000  # Assuming a Bitcoin price of around $65,000
        total_value = total_btc * btc_price
        
        logger.info(f"Total Bitcoin: {total_btc}")
        logger.info(f"Total portfolio value: ${total_value:,.2f}")
        
        # Add a history entry for today
        current_date = datetime.datetime.now()
        history_entry = PortfolioHistory(
            date=current_date,
            total_value=total_value
        )
        session.add(history_entry)
        
        # Commit changes and close session
        session.commit()
        session.close()
        
        logger.info("Database update completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error updating database: {str(e)}")
        return False

if __name__ == "__main__":
    update_railway_database()
