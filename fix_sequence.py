import os
import psycopg2
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('db_fix')

# Load environment variables
load_dotenv()

def fix_portfolio_history_sequence():
    """
    Fix the sequence for the portfolio_history table's id column
    to ensure it starts from the maximum id value + 1
    """
    try:
        # Get database connection details from environment variables
        db_url = os.getenv('DATABASE_URL')
        
        if not db_url:
            logger.error("DATABASE_URL environment variable not found")
            return False
        
        logger.info(f"Connecting to database: {db_url}")
        
        # Connect to the database
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Find the maximum ID in the portfolio_history table
        cursor.execute("SELECT MAX(id) FROM portfolio_history")
        max_id = cursor.fetchone()[0]
        
        if max_id is None:
            logger.info("No entries found in portfolio_history table")
            return True
        
        logger.info(f"Maximum ID in portfolio_history table: {max_id}")
        
        # Reset the sequence to start from max_id + 1
        cursor.execute(f"SELECT setval('portfolio_history_id_seq', {max_id}, true)")
        
        # Commit the changes
        conn.commit()
        
        logger.info(f"Successfully reset sequence to {max_id + 1}")
        return True
        
    except Exception as e:
        logger.error(f"Error fixing sequence: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    if fix_portfolio_history_sequence():
        logger.info("Sequence fix completed successfully")
    else:
        logger.error("Failed to fix sequence")
