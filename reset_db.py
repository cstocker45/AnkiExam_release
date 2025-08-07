from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable must be set for PostgreSQL.")

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def reset_database():
    print("Starting database reset...")
    
    # Create a connection
    with engine.connect() as connection:
        # Disable foreign key checks temporarily (if needed)
        connection.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS pending_registrations CASCADE"))
        connection.commit()
        print("Tables dropped successfully!")
    
    print("Database reset complete! Restart the application to recreate tables.")

if __name__ == "__main__":
    confirmation = input("WARNING: This will delete all data. Are you sure? (yes/no): ")
    if confirmation.lower() == 'yes':
        reset_database()
    else:
        print("Database reset cancelled.")
