import os
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()

def resolve_database_url() -> str | None:
    """
    Resolve Postgres connection from environment variables:
      1) DATABASE_URL
      2) POSTGRES_URL
      3) Compose from PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
    Normalizes postgres:// to postgresql://.
    """
    url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
    if not url:
        pg_host = os.environ.get('PGHOST')
        pg_port = os.environ.get('PGPORT', '5432')
        pg_user = os.environ.get('PGUSER')
        pg_pass = os.environ.get('PGPASSWORD')
        pg_db = os.environ.get('PGDATABASE')
        if pg_host and pg_user and pg_db:
            cred = pg_user if not pg_pass else f"{pg_user}:{pg_pass}"
            url = f"postgresql://{cred}@{pg_host}:{pg_port}/{pg_db}"
    if url and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url

def add_zerion_id_column():
    try:
        database_url = resolve_database_url()
        if not database_url:
            logger.error("DATABASE_URL/POSTGRES_URL or PG* vars are required for migrations")
            return False
        logger.info("Using database for migration: postgresql://<redacted>")

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
