from app import db

def init_db():
    print("Creating database tables...")
    db.create_all()
    print("Database tables created successfully!")

if __name__ == '__main__':
    init_db()
