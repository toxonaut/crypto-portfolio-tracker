from app import db, Portfolio, app

def add_bitcoin_data():
    with app.app_context():
        # Clear existing Bitcoin entries
        bitcoin_entries = Portfolio.query.filter_by(coin_id="bitcoin").all()
        for entry in bitcoin_entries:
            db.session.delete(entry)
        db.session.commit()
        
        # Bitcoin entries with locations and amounts
        bitcoin_entries = [
            {"source": "SolvBTC Arbitrum Avalon", "amount": 1},
            {"source": "Swell Earn BTC Vault", "amount": 1},
            {"source": "Ledger", "amount": 50},
            {"source": "Frankencoin coll", "amount": 0.2},
            {"source": "cbBTC ZeroLend", "amount": 3.0677},
            {"source": "SONIC SolvBTC Silo", "amount": 1.0049},
            {"source": "WBTC Free", "amount": 4},
            {"source": "Solana Raydium", "amount": 3.2829},
            {"source": "Nexo", "amount": 34.7484},
            {"source": "Swell swBTC", "amount": 1.049},
            {"source": "swapX Sonic", "amount": 1.011},
            {"source": "LBTC in Lombard vault", "amount": 1.9981},
            {"source": "LBTC Hourglass Pool", "amount": 0.995},
            {"source": "cbBTC Base Aave", "amount": 2},
            {"source": "Gate.io Earn", "amount": 5.0054},
            {"source": "cbBTC Euler finance", "amount": 0.861},
            {"source": "WBTC Across", "amount": 3.0043},
            {"source": "WBTC Strike", "amount": 3.0044},
            {"source": "BTC Kraken", "amount": 5.2453},
            {"source": "cbBTC Avalon Base", "amount": 0.0868},
            {"source": "Zerolend WBTC & LBTC", "amount": 4.1307},
            {"source": "cbBTC zero base", "amount": 0.8}
        ]
        
        # Add all Bitcoin entries
        for entry_data in bitcoin_entries:
            new_entry = Portfolio(
                coin_id="bitcoin",
                source=entry_data["source"],
                amount=entry_data["amount"],
                apy=0.0,  # Default APY to 0
                last_price=60000.0  # Approximate BTC price
            )
            db.session.add(new_entry)
        
        db.session.commit()
        print(f"Added {len(bitcoin_entries)} Bitcoin entries to the database")

if __name__ == "__main__":
    add_bitcoin_data()
