#!/usr/bin/env python3
"""
Database setup script for Kabaddi Analytics
Creates the PostgreSQL database and tables
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

# Database connection parameters (from env, prefer DATABASE_URL for Cloud Run)
import os
DATABASE_URL = os.getenv("DATABASE_URL")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "kabaddi_data")

def create_database():
    """Create the database if it doesn't exist"""
    try:
        # Connect to PostgreSQL server (without specifying database)
        conn = psycopg2.connect(DATABASE_URL) if (DATABASE_URL and DATABASE_URL.strip()) else psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_NAME,))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"✅ Database '{DB_NAME}' created successfully")
        else:
            print(f"✅ Database '{DB_NAME}' already exists")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        print("Please ensure PostgreSQL is running and the credentials are correct")
        sys.exit(1)

def test_connection():
    """Test connection to the database"""
    try:
        conn = psycopg2.connect(DATABASE_URL) if (DATABASE_URL and DATABASE_URL.strip()) else psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Connected to PostgreSQL: {version[0]}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Setting up PostgreSQL database for Kabaddi Analytics...")
    create_database()
    
    if test_connection():
        print("✅ Database setup completed successfully!")
        print("You can now run: python main.py")
    else:
        print("❌ Database setup failed!")
        sys.exit(1)
