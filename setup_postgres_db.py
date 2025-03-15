from app import app, db
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()

def setup_database():
    """
    Create all database tables if they don't exist.
    """
    try:
        # Get the database URL from environment variable
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            return False
            
        logger.info(f"Setting up database: {database_url.split('@')[1] if '@' in database_url else 'PostgreSQL'}")
        
        with app.app_context():
            # Create all tables
            db.create_all()
            
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        return False

if __name__ == '__main__':
    setup_database()
