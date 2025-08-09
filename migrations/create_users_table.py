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

def resolve_database_url() -> str | None:
    """
    Resolve Postgres connection string from environment:
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

database_url = resolve_database_url()
if not database_url:
    logger.error("DATABASE_URL/POSTGRES_URL or PG* vars are required for migrations")
    raise SystemExit(1)

logger.info("Using database for migration: postgresql://<redacted>")

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
