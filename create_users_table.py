import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()

# Get the database URL from environment variable
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
        logger.warning("DATABASE_URL environment variable not set locally, using default SQLite")
        database_url = 'sqlite:///portfolio.db'
    else:
        logger.info(f"Using external Railway database connection")

# If the URL starts with postgres://, change it to postgresql:// (SQLAlchemy requirement)
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

logger.info(f"Using database: {database_url.split('@')[1] if database_url and '@' in database_url else 'Unknown'}")

def create_users_table():
    """Create the users table for authentication."""
    try:
        # Create an engine
        engine = create_engine(database_url)
        
        # Create a metadata instance
        metadata = MetaData()
        
        # Define the users table
        users = Table(
            'users', 
            metadata,
            Column('id', Integer, primary_key=True),
            Column('email', String(100), unique=True),
            Column('name', String(100))
        )
        
        # Create the table
        metadata.create_all(engine)
        logger.info("Users table created successfully")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Error creating users table: {str(e)}")
        return False

if __name__ == '__main__':
    create_users_table()
