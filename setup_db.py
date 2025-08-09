from app import app, db, Portfolio, PortfolioHistory, INITIALIZE_DB
import os
import sys
import time
import sqlite3
import datetime
import shutil

def setup_db():
    """
    Sets up the database tables if they don't exist.
    """
    print(f"Connecting to database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    # Check if we're running on Railway and if we should preserve the database
    is_railway = 'RAILWAY_ENVIRONMENT' in os.environ
    preserve_db = os.environ.get('RAILWAY_PRESERVE_DB') == 'true'
    
    if is_railway and preserve_db:
        print("Running on Railway with RAILWAY_PRESERVE_DB=true - skipping database initialization")
        return
    
    # Check if we should initialize the database
    if not INITIALIZE_DB:
        print("INITIALIZE_DB is False - skipping database initialization")
        return
    
    # Check if the database already has data before initializing
    if is_railway:
        try:
            # Connect to the database directly to check if it has data
            conn = sqlite3.connect(SQLITE_PATH)
            cursor = conn.cursor()
            
            # Check if the portfolio table exists and has data
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM portfolio")
                count = cursor.fetchone()[0]
                print(f"Found {count} records in portfolio table")
                
                if count > 0:
                    print("Database contains user data - skipping initialization")
                    # Set environment variable to preserve the database
                    os.environ['RAILWAY_PRESERVE_DB'] = 'true'
                    print("Set RAILWAY_PRESERVE_DB=true")
                    conn.close()
                    return
            
            conn.close()
        except Exception as e:
            print(f"Error checking database: {str(e)}")

print("setup_db.py deprecated: Postgres-only. No action required. Exiting.")
sys.exit(0)

# Check if we're running on Railway
is_railway = 'RAILWAY_ENVIRONMENT' in os.environ
if is_railway:
    # On Railway, use a path in the persistent filesystem
    SQLITE_PATH = '/data/railway_portfolio.db'
    print(f"Running on Railway - using database at {SQLITE_PATH}")
    
    # Make sure the /data directory exists
    if not os.path.exists('/data'):
        os.makedirs('/data')
        print("Created /data directory")
        
    # On Railway, we don't want to initialize the database if it already exists
    if os.path.exists(SQLITE_PATH):
        print(f"Database already exists at {SQLITE_PATH} - skipping initialization")
        # Exit the script early to prevent any database operations
        import sys
        sys.exit(0)
    else:
        print(f"Database does not exist at {SQLITE_PATH} - will create minimal structure only")
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
tables_exist = False
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

# If we're on Railway and the database doesn't exist yet, create a local one first and then copy it
if is_railway and not os.path.exists(SQLITE_PATH):
    print("Creating initial database for Railway...")
    
    # Create a local temporary database
    temp_db_path = 'temp_portfolio.db'
    
    # Connect to the temporary database
    temp_conn = sqlite3.connect(temp_db_path)
    temp_cursor = temp_conn.cursor()
    
    # Create tables
    temp_cursor.execute('''
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin_id TEXT NOT NULL,
        source TEXT NOT NULL,
        amount REAL NOT NULL,
        apy REAL DEFAULT 0.0
    )
    ''')
    
    temp_cursor.execute('''
    CREATE TABLE IF NOT EXISTS portfolio_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TIMESTAMP NOT NULL,
        total_value REAL NOT NULL
    )
    ''')
    
    # Add test data
    bitcoin_entries = [
        ("bitcoin", "SolvBTC Arbitrum Avalon", 1, 0),
        ("bitcoin", "Swell Earn BTC Vault", 1, 0),
        ("bitcoin", "Ledger", 50, 0),
        ("bitcoin", "Frankencoin coll", 0.2, 0),
        ("bitcoin", "cbBTC ZeroLend", 3.0677, 0),
        ("bitcoin", "SONIC SolvBTC Silo", 1.0049, 0),
        ("bitcoin", "Aave WBTC", 1.5, 0),
        ("bitcoin", "WBTC Free", 1.5, 0),
        ("bitcoin", "Solana Raydium", 3.2845, 0),
        ("bitcoin", "Nexo", 34.7484, 0),
        ("bitcoin", "Swell swBTC", 1.049, 0),
        ("bitcoin", "swapX Sonic", 1.011, 0),
        ("bitcoin", "LBTC in Lombard vault", 2.9965, 0),
        ("bitcoin", "cbBTC Base Aave", 2, 0),
        ("bitcoin", "Gate.io Earn", 5.0054, 0),
        ("bitcoin", "cbBTC Euler finance", 0.861, 0),
        ("bitcoin", "WBTC Across", 3.0043, 0),
        ("bitcoin", "WBTC Strike", 3.0044, 0),
        ("bitcoin", "BTC Kraken", 5.2453, 0),
        ("bitcoin", "cbBTC Avalon Base", 0.0868, 0),
        ("bitcoin", "Zerolend WBTC & LBTC", 4.1316, 0),
        ("bitcoin", "cbBTC zero base", 0.8, 0),
        ("bitcoin", "eBTC Zerolend", 1, 0)
    ]
    
    for coin in bitcoin_entries:
        temp_cursor.execute(
            "INSERT INTO portfolio (coin_id, source, amount, apy) VALUES (?, ?, ?, ?)",
            coin
        )
    
    # Add history data
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    history_data = [
        (now, 5000.0),
        (now, 5100.0)
    ]
    
    for entry in history_data:
        temp_cursor.execute(
            "INSERT INTO portfolio_history (date, total_value) VALUES (?, ?)",
            entry
        )
    
    # Commit and close
    temp_conn.commit()
    temp_conn.close()
    
    # Copy the temporary database to the Railway path
    try:
        shutil.copy(temp_db_path, SQLITE_PATH)
        print(f"Successfully copied database to {SQLITE_PATH}")
        
        # Verify the copy
        if os.path.exists(SQLITE_PATH):
            print(f"Verified database exists at {SQLITE_PATH}")
            print(f"Database size: {os.path.getsize(SQLITE_PATH)} bytes")
        else:
            print(f"ERROR: Database copy failed, {SQLITE_PATH} does not exist")
    except Exception as e:
        print(f"Error copying database to Railway path: {e}")

setup_db()

while retry_count < max_retries and not success:
    try:
        # Create all tables if they don't exist
        with app.app_context():
            print(f"Attempt {retry_count + 1}: Creating database tables if they don't exist...")
            if INITIALIZE_DB and not is_railway:
                db.create_all()
                print("Database tables created or verified successfully")
            else:
                print("Database initialization skipped - using existing database")

            # Only test with a sample entry if we need to verify the schema
            if not tables_exist and INITIALIZE_DB and not is_railway:
                print("Testing database schema with sample entry...")
                try:
                    # Check if there's any data in the portfolio table
                    portfolio_count = Portfolio.query.count()
                    print(f"Found {portfolio_count} existing portfolio entries")
                    
                    # Only add test data if the portfolio is empty
                    if portfolio_count == 0:
                        print("Adding test data to the database...")
                        
                        # Add test data - popular cryptocurrencies
                        test_data = [
                            ('bitcoin', 'Coinbase', 0.5, 0.0),
                            ('ethereum', 'Binance', 2.5, 4.5),
                            ('solana', 'Kraken', 15.0, 6.2),
                            ('cardano', 'Ledger', 500.0, 3.0),
                            ('polkadot', 'Metamask', 50.0, 8.0),
                            ('avalanche-2', 'Coinbase', 10.0, 9.5)
                        ]
                        
                        for coin_id, source, amount, apy in test_data:
                            new_entry = Portfolio(
                                coin_id=coin_id,
                                source=source,
                                amount=amount,
                                apy=apy
                            )
                            db.session.add(new_entry)
                        
                        # Add some history data
                        history_data = [
                            (datetime.datetime.now(), 5000.0),
                            (datetime.datetime.now(), 5100.0)
                        ]
                        
                        for date, total_value in history_data:
                            new_history = PortfolioHistory(
                                date=date,
                                total_value=total_value
                            )
                            db.session.add(new_history)
                        
                        db.session.commit()
                        print(f"Added {len(test_data)} test coins to the portfolio")
                        print(f"Added {len(history_data)} history entries")
                    else:
                        print("Database already has data, skipping test data insertion")
                    
                except Exception as e:
                    print(f"Error testing or adding data: {e}")
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

# Final verification
if success:
    print("Database setup completed successfully")
    
    # Verify the database has data
    with app.app_context():
        portfolio_count = Portfolio.query.count()
        history_count = PortfolioHistory.query.count()
        print(f"Final verification: Database contains {portfolio_count} portfolio entries and {history_count} history entries")
    
    print("Your application should now be ready to run!")
else:
    print("Database setup failed after multiple attempts")
    print("Please check your database configuration and try again")
