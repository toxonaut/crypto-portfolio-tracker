from app import app, db, Portfolio, PortfolioHistory
import datetime
import os
import logging
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()

# Bitcoin entries to add to the database
bitcoin_entries = [
    ('bitcoin', 'Binance', 0.5, 0),
    ('bitcoin', 'Coinbase', 0.3, 0),
    ('bitcoin', 'BlockFi', 0.2, 4.5),
    ('bitcoin', 'Celsius', 0.1, 5.5)
]

def update_bitcoin_data():
    """
    Update the database with Bitcoin entries.
    """
    try:
        # Get the database URL from environment variable
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            return False
        
        # If the URL starts with postgres://, change it to postgresql:// (SQLAlchemy requirement)
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        logger.info(f"Connecting to database: {database_url.split('@')[1] if '@' in database_url else 'PostgreSQL'}")
        
        # Create a SQLAlchemy engine
        engine = create_engine(database_url)
        
        # Create a session
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Clear existing portfolio data
        logger.info("Clearing existing portfolio data...")
        session.query(Portfolio).delete()
        
        # Add new Bitcoin entries
        logger.info("Adding new Bitcoin entries...")
        total_value = 0
        for coin_id, source, amount, apy in bitcoin_entries:
            portfolio_entry = Portfolio(
                coin_id=coin_id,
                source=source,
                amount=amount,
                apy=apy
            )
            session.add(portfolio_entry)
            # For simplicity, we'll assume 1 BTC = $50,000
            total_value += amount * 50000
        
        # Add a history entry for today
        current_date = datetime.datetime.now()
        history_entry = PortfolioHistory(
            date=current_date,
            total_value=total_value
        )
        session.add(history_entry)
        
        # Commit the changes
        session.commit()
        logger.info("Database updated successfully")
        return True
    except Exception as e:
        logger.error(f"Error updating database: {str(e)}")
        return False

if __name__ == '__main__':
    update_bitcoin_data()
