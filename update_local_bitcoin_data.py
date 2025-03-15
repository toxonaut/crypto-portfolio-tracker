from app import app, db, Portfolio, PortfolioHistory
import datetime
import sqlite3
import shutil
import os

# Bitcoin entries to add
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

def update_local_database():
    print("Updating local database with Bitcoin entries...")
    
    # Path to the database
    db_path = "portfolio.db"
    
    # Create a backup of the current database
    backup_path = f"{db_path}.backup"
    print(f"Creating backup of database at {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    # Connect to the database directly
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Clear existing portfolio data
    print("Clearing existing portfolio data...")
    cursor.execute("DELETE FROM portfolio")
    
    # Add new Bitcoin entries
    print("Adding new Bitcoin entries...")
    for coin_id, source, amount, apy in bitcoin_entries:
        cursor.execute(
            "INSERT INTO portfolio (coin_id, source, amount, apy) VALUES (?, ?, ?, ?)",
            (coin_id, source, amount, apy)
        )
    
    # Calculate total Bitcoin and value
    total_btc = sum(entry[2] for entry in bitcoin_entries)
    btc_price = 65000  # Assuming a Bitcoin price of around $65,000
    total_value = total_btc * btc_price
    
    print(f"Total Bitcoin: {total_btc}")
    print(f"Total portfolio value: ${total_value:,.2f}")
    
    # Add a history entry for today
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        cursor.execute(
            "INSERT INTO portfolio_history (date, total_value) VALUES (?, ?)",
            (current_date, total_value)
        )
        print("Added history entry for today's value")
    except Exception as e:
        print(f"Error adding history entry: {e}")
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print("Database update completed")
    
    # Create a copy for Railway deployment
    railway_db_path = "initial_data.sqlite.backup"
    print(f"Creating copy for Railway deployment at {railway_db_path}")
    shutil.copy2(db_path, railway_db_path)
    
    print(f"Railway database copy created at {railway_db_path}")
    print("You can now commit and push this file to GitHub to update the Railway deployment")

if __name__ == "__main__":
    update_local_database()
