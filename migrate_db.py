import os
import sys
from app import app, db, Portfolio

# First, create all tables if they don't exist
print("Creating database tables if they don't exist...")
with app.app_context():
    db.create_all()
    print("Database tables created or already exist")

# Check if we're using SQLite (local development) or PostgreSQL (Railway)
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///portfolio.db')

# For PostgreSQL (Railway)
if DATABASE_URL.startswith('postgresql://'):
    print("Using PostgreSQL database")
    try:
        # We'll use SQLAlchemy to handle the migration for PostgreSQL
        with app.app_context():
            # Check if the column exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [column['name'] for column in inspector.get_columns('portfolio')]
            
            if 'apy' not in columns:
                print("Adding 'apy' column to PostgreSQL database...")
                # For PostgreSQL, we can use db.engine.execute
                db.engine.execute("ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS apy FLOAT DEFAULT 0.0")
                print("Added 'apy' column to the portfolio table")
            else:
                print("The 'apy' column already exists in the portfolio table")
    except Exception as e:
        print(f"Error during PostgreSQL migration: {e}")
        # Continue execution even if there's an error, as the column might already exist

# For SQLite (local development)
elif DATABASE_URL.startswith('sqlite:///'):
    import sqlite3
    
    # Extract the database file path
    db_path = DATABASE_URL.replace('sqlite:///', '')
    
    try:
        # Connect to the SQLite database
        print(f"Connecting to SQLite database at {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the 'apy' column already exists
        cursor.execute("PRAGMA table_info(portfolio)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'apy' not in column_names:
            # Add the 'apy' column to the portfolio table
            print("Adding 'apy' column to SQLite database...")
            cursor.execute("ALTER TABLE portfolio ADD COLUMN apy FLOAT DEFAULT 0.0")
            conn.commit()
            print("Added 'apy' column to the portfolio table")
        else:
            print("The 'apy' column already exists in the portfolio table")
        
        # Close the connection
        conn.close()
    except Exception as e:
        print(f"Error during SQLite migration: {e}")
        # Continue execution even if there's an error

print("Migration completed")
