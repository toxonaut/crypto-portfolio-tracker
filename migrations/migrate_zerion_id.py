import os
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        # Get database URL from environment
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            return
        
        # Format the URL for SQLAlchemy if needed
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        logger.info(f"Connecting to database: {database_url}")
        
        # Create engine
        engine = create_engine(database_url)
        
        # Execute the migration
        with engine.connect() as connection:
            logger.info("Altering zerion_id column to VARCHAR(255)")
            connection.execute(text("ALTER TABLE portfolio ALTER COLUMN zerion_id TYPE VARCHAR(255)"))
            connection.commit()
            logger.info("Successfully altered zerion_id column to VARCHAR(255)")
        
        logger.info("Migration completed successfully")
    
    except Exception as e:
        logger.error(f"Error during migration: {e}")

if __name__ == "__main__":
    main()
