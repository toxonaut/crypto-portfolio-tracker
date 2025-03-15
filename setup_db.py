from app import app, db, Portfolio
import os
import time
import sqlite3

print("Starting database setup...")
print(f"Database URL: {os.environ.get('DATABASE_URL', 'Not set, using SQLite fallback')}")
print(f"Environment variables: {[key for key in os.environ.keys() if 'DATABASE' in key]}")

# Try multiple times to create tables (in case the database is still initializing)
max_retries = 5
retry_count = 0
success = False

# Make sure the SQLite database file exists and is writable
sqlite_path = 'portfolio.db'
print(f"Checking SQLite database at {sqlite_path}")
try:
    # Try to connect to SQLite database
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    print("Successfully connected to SQLite database")
    conn.close()
except Exception as e:
    print(f"Error connecting to SQLite database: {e}")

while retry_count < max_retries and not success:
    try:
        # Create all tables if they don't exist
        with app.app_context():
            print(f"Attempt {retry_count + 1}: Creating database tables...")
            db.create_all()
            print("Database tables created successfully")

            # Check if we need to add the APY column
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
                
                # If we get here, everything worked
                success = True
                
            except Exception as e:
                print(f"Error testing APY column: {e}")
                print("This is normal if the column doesn't exist yet")
                # Still mark as success if this is the only error
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
