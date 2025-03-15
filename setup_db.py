from app import app, db, Portfolio
import os
import time
import sqlite3

print("Starting database setup...")

# Check if we're running on Railway
is_railway = 'RAILWAY_ENVIRONMENT' in os.environ
if is_railway:
    # On Railway, use a path in the persistent filesystem
    SQLITE_PATH = '/data/railway_portfolio.db'
    print(f"Running on Railway - using database at {SQLITE_PATH}")
else:
    # Locally, use the regular path
    SQLITE_PATH = 'portfolio.db'
    print(f"Running locally - using database at {SQLITE_PATH}")

# Get the database URL
DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{SQLITE_PATH}')
print(f"Database URL: {DATABASE_URL}")
print(f"Environment variables: {[key for key in os.environ.keys() if 'DATABASE' in key]}")

# Try multiple times to create tables (in case the database is still initializing)
max_retries = 5
retry_count = 0
success = False

# Make sure the SQLite database directory exists
if DATABASE_URL.startswith('sqlite:///'):
    db_path = DATABASE_URL.replace('sqlite:///', '')
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        print(f"Creating directory: {db_dir}")
        os.makedirs(db_dir)

# Check if we can connect to the SQLite database
if DATABASE_URL.startswith('sqlite:///'):
    db_path = DATABASE_URL.replace('sqlite:///', '')
    print(f"Checking SQLite database at {db_path}")
    try:
        # Try to connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("Successfully connected to SQLite database")
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio'")
        tables_exist = cursor.fetchone() is not None
        print(f"Portfolio table exists: {tables_exist}")
        
        conn.close()
    except Exception as e:
        print(f"Error connecting to SQLite database: {e}")
        tables_exist = False
else:
    print("Not using SQLite, skipping direct connection test")
    tables_exist = False

while retry_count < max_retries and not success:
    try:
        # Create all tables if they don't exist
        with app.app_context():
            print(f"Attempt {retry_count + 1}: Creating database tables if they don't exist...")
            db.create_all()
            print("Database tables created or verified successfully")

            # Only test with a sample entry if we need to verify the schema
            if not tables_exist:
                print("Testing database schema with sample entry...")
                try:
                    # Try to add a test entry to check if the apy column exists
                    test_entry = Portfolio(
                        coin_id="test_coin",
                        source="test_source",
                        amount=1.0,
                        apy=1.0
                    )
                    db.session.add(test_entry)
                    db.session.commit()
                    print("APY column exists and is working correctly")
                    
                    # Clean up the test entry
                    db.session.delete(test_entry)
                    db.session.commit()
                    print("Test entry removed successfully")
                except Exception as e:
                    print(f"Error testing APY column: {e}")
                    print("This is normal if the column doesn't exist yet")
            else:
                print("Skipping test entry since tables already exist")
                
            # If we get here, everything worked
            success = True
                
    except Exception as e:
        retry_count += 1
        print(f"Error creating database tables: {e}")
        if retry_count < max_retries:
            print(f"Retrying in 5 seconds... (Attempt {retry_count + 1}/{max_retries})")
            time.sleep(5)
        else:
            print("Maximum retries reached. Could not set up database.")

if success:
    print("Database setup completed successfully")
    print("Your application should now be ready to run!")
else:
    print("Database setup failed after multiple attempts")
    print("Please check your database configuration and try again")
