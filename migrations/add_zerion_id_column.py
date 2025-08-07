import os
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()

def add_zerion_id_column():
    try:
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

        # Create a SQLAlchemy engine
        engine = create_engine(database_url)
        
        # Check if the column already exists
        with engine.connect() as connection:
            result = connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'portfolio' AND column_name = 'zerion_id'"))
            column_exists = result.fetchone() is not None
            
            if column_exists:
                logger.info("zerion_id column already exists in the portfolio table")
                return True
            
            # Add the column if it doesn't exist
            connection.execute(text("ALTER TABLE portfolio ADD COLUMN zerion_id VARCHAR(100)"))
            connection.commit()
            
            logger.info("Successfully added zerion_id column to the portfolio table")
            return True
            
    except Exception as e:
        logger.error(f"Error adding zerion_id column: {e}")
        return False

if __name__ == "__main__":
    success = add_zerion_id_column()
    if success:
        print("Column added successfully or already exists")
    else:
        print("Failed to add column")
