import sqlite3
import os

# Check if we're using SQLite (local development) or PostgreSQL (Railway)
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///portfolio.db')
if DATABASE_URL.startswith('sqlite:///'):
    # Extract the database file path
    db_path = DATABASE_URL.replace('sqlite:///', '')
    
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the 'apy' column already exists
    cursor.execute("PRAGMA table_info(portfolio)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'apy' not in column_names:
        # Add the 'apy' column to the portfolio table
        cursor.execute("ALTER TABLE portfolio ADD COLUMN apy FLOAT DEFAULT 0.0")
        conn.commit()
        print("Added 'apy' column to the portfolio table")
    else:
        print("The 'apy' column already exists in the portfolio table")
    
    # Close the connection
    conn.close()
else:
    print("Using PostgreSQL database. Please run the migration manually or through Railway.")
    print("SQL command: ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS apy FLOAT DEFAULT 0.0;")
