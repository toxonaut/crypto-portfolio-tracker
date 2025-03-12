from app import db, Portfolio, app

def add_test_data():
    with app.app_context():
        # Check if there's already data in the database
        existing_entries = Portfolio.query.all()
        if existing_entries:
            print(f"Database already has {len(existing_entries)} entries. No test data added.")
            return
        
        # Add a test Bitcoin entry
        test_entry = Portfolio(
            coin_id="bitcoin",
            source="Binance",
            amount=0.5,
            apy=4.5,
            last_price=60000.0
        )
        
        # Add a test Ethereum entry
        test_entry2 = Portfolio(
            coin_id="ethereum",
            source="Coinbase",
            amount=2.0,
            apy=5.2,
            last_price=3000.0
        )
        
        db.session.add(test_entry)
        db.session.add(test_entry2)
        db.session.commit()
        
        print("Added test data to the database")

if __name__ == "__main__":
    add_test_data()
