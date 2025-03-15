import os
import shutil
import time
import sqlite3

print("Railway Database Copy Script")
print("===========================")

# Check if we're running on Railway
is_railway = 'RAILWAY_ENVIRONMENT' in os.environ

if is_railway:
    print("Running on Railway - proceeding with database check")
    
    # Source database file (in the project directory)
    source_db = 'initial_data.sqlite.backup'
    
    # Destination in Railway's persistent storage
    dest_dir = '/data'
    dest_db = '/data/railway_portfolio.db'
    
    # Make sure the destination directory exists
    if not os.path.exists(dest_dir):
        print(f"Creating directory: {dest_dir}")
        os.makedirs(dest_dir)
    
    # Check if destination database already exists
    if os.path.exists(dest_db):
        print(f"Destination database already exists: {dest_db}")
        print(f"Size: {os.path.getsize(dest_db)} bytes")
        
        # Check if the database has user data
        try:
            conn = sqlite3.connect(dest_db)
            cursor = conn.cursor()
            
            # Check if the portfolio table exists and has data
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM portfolio")
                count = cursor.fetchone()[0]
                print(f"Found {count} records in portfolio table")
                
                if count > 0:
                    print("Database contains user data - preserving existing data")
                    # Set environment variable to preserve the database
                    os.environ['RAILWAY_PRESERVE_DB'] = 'true'
                    
                    # Create a marker file to indicate the database has data
                    marker_file = '/data/db_has_data.marker'
                    with open(marker_file, 'w') as f:
                        f.write(f"Database has {count} records in portfolio table")
                    print(f"Created marker file at {marker_file}")
                else:
                    print("Portfolio table exists but has no data")
            else:
                print("Portfolio table does not exist in the database")
                print("Replacing with initial database")
                # Backup the existing file just in case
                backup_path = f"{dest_db}.backup.{int(time.time())}"
                shutil.copy(dest_db, backup_path)
                print(f"Backed up existing database to {backup_path}")
                # Copy the initial database
                shutil.copy(source_db, dest_db)
                print(f"Copied initial database to {dest_db}")
            
            conn.close()
        except Exception as e:
            print(f"Error checking database: {str(e)}")
            print("Database may be corrupted - replacing with initial database")
            # Backup the existing file just in case
            backup_path = f"{dest_db}.corrupted.{int(time.time())}"
            shutil.copy(dest_db, backup_path)
            print(f"Backed up corrupted database to {backup_path}")
            # Copy the initial database
            shutil.copy(source_db, dest_db)
            print(f"Copied initial database to {dest_db}")
    else:
        # Check if source database exists
        if os.path.exists(source_db):
            print(f"Found source database: {source_db} ({os.path.getsize(source_db)} bytes)")
            
            # Copy the database file
            try:
                shutil.copy(source_db, dest_db)
                print(f"Successfully copied database to {dest_db}")
                
                # Verify the copy
                if os.path.exists(dest_db):
                    print(f"Verified database exists at {dest_db}")
                    print(f"Database size: {os.path.getsize(dest_db)} bytes")
                    
                    # List all files in the destination directory
                    print(f"Contents of {dest_dir}:")
                    for file in os.listdir(dest_dir):
                        file_path = os.path.join(dest_dir, file)
                        file_size = os.path.getsize(file_path)
                        print(f"  - {file} ({file_size} bytes)")
                else:
                    print(f"ERROR: Database copy failed, {dest_db} does not exist")
            except Exception as e:
                print(f"Error copying database: {e}")
        else:
            print(f"ERROR: Source database {source_db} not found")
    
    # List the contents of the data directory
    print(f"\nFinal contents of {dest_dir}:")
    if os.path.exists(dest_dir):
        for file in os.listdir(dest_dir):
            file_path = os.path.join(dest_dir, file)
            file_size = os.path.getsize(file_path)
            print(f"  - {file} ({file_size} bytes)")
    else:
        print(f"  Directory {dest_dir} does not exist")
else:
    print("Not running on Railway, skipping database copy")

print("Script completed")
