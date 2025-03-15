from app import app, db, Portfolio, PortfolioHistory
import os
import time
import sys

def init_db():
    print("Starting Railway PostgreSQL database initialization...")
    
    # Check if we're using PostgreSQL
    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url or not ('postgresql' in database_url or 'postgres' in database_url):
        print(f"WARNING: Not using PostgreSQL! Database URL: {database_url}")
        print("This script should only be run on Railway with PostgreSQL configured.")
        return False
    
    print(f"Using database: {database_url}")
    
    # Try to create tables with multiple retries
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with app.app_context():
                print(f"Attempt {attempt + 1}/{max_retries}: Creating database tables...")
                db.create_all()
                
                # Verify tables were created by adding and removing a test record
                test_entry = Portfolio(
                    coin_id="test_coin",
                    source="test_source",
                    amount=1.0,
                    apy=1.0
                )
                db.session.add(test_entry)
                db.session.commit()
                print("Test entry created successfully!")
                
                # Verify we can query the database
                test_query = Portfolio.query.filter_by(coin_id="test_coin").first()
                if test_query:
                    print("Test query successful!")
                else:
                    print("Test query failed - entry not found!")
                    raise Exception("Database verification failed")
                
                # Clean up test entry
                db.session.delete(test_entry)
                db.session.commit()
                print("Test entry removed successfully!")
                
                print("All database tables created and verified successfully!")
                return True
                
        except Exception as e:
            print(f"Error during attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 5
                print(f"Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
            else:
                print(f"Failed after {max_retries} attempts.")
                return False
    
    return False

if __name__ == '__main__':
    success = init_db()
    if success:
        print("Database initialization completed successfully!")
        sys.exit(0)
    else:
        print("Database initialization failed!")
        sys.exit(1)
