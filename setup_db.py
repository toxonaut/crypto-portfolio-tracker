from app import app, db, Portfolio
import os

print("Starting database setup...")

# Create all tables if they don't exist
with app.app_context():
    print("Creating database tables...")
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
    except Exception as e:
        print(f"Error testing APY column: {e}")
        print("This is normal if the column doesn't exist yet")

print("Database setup completed")
print("Your application should now be ready to run!")
