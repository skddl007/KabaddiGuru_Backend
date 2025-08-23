#!/usr/bin/env python3
"""
Complete Database Setup Script for Kabaddi Analytics
- Checks if PostgreSQL database exists
- Creates database if it doesn't exist
- Loads Excel data (SKDB.xlsx) into PostgreSQL tables
- Verifies the setup
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text, inspect

# Database connection parameters: prefer DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "kabaddi_data")
POSTGRES_CONNECTION_STRING = (
    DATABASE_URL if (DATABASE_URL and DATABASE_URL.strip()) else f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Excel file path
EXCEL_PATH = "SKDB.xlsx"

def check_postgresql_running():
    """Check if PostgreSQL server is running"""
    try:
        conn = psycopg2.connect(DATABASE_URL) if (DATABASE_URL and DATABASE_URL.strip()) else psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.close()
        print("✅ PostgreSQL server is running")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL server is not running or credentials are wrong: {e}")
        print("\nPlease ensure:")
        print("1. PostgreSQL is installed and running")
        print("2. Username 'postgres' exists")
        print("3. Password is correct")
        return False

def check_database_exists():
    """Check if the kabaddi_data database exists"""
    try:
        conn = psycopg2.connect(DATABASE_URL) if (DATABASE_URL and DATABASE_URL.strip()) else psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_NAME,))
        exists = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if exists:
            print(f"✅ Database '{DB_NAME}' already exists")
            return True
        else:
            print(f"⚠️  Database '{DB_NAME}' does not exist")
            return False
            
    except Exception as e:
        print(f"❌ Error checking database existence: {e}")
        return False

def create_database():
    """Create the database if it doesn't exist"""
    try:
        conn = psycopg2.connect(DATABASE_URL) if (DATABASE_URL and DATABASE_URL.strip()) else psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
        print(f"✅ Database '{DB_NAME}' created successfully")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False

def check_excel_file():
    """Check if Excel file exists"""
    if os.path.exists(EXCEL_PATH):
        print(f"✅ Excel file found: {EXCEL_PATH}")
        return True
    else:
        print(f"❌ Excel file not found: {EXCEL_PATH}")
        print("Please ensure SKDB.xlsx is in the current directory")
        return False

def load_excel_sheets():
    """Load all sheets from Excel file"""
    try:
        xl = pd.ExcelFile(EXCEL_PATH)
        print(f"📊 Excel sheets available: {xl.sheet_names}")
        
        tables = {}
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name)
            tables[sheet_name] = df
            print(f"✅ Loaded sheet '{sheet_name}' with {len(df)} rows and {len(df.columns)} columns")
        
        return tables
        
    except Exception as e:
        print(f"❌ Error loading Excel file: {e}")
        return None

def create_database_engine():
    """Create SQLAlchemy engine for PostgreSQL"""
    try:
        # Try different connection string formats for Windows
        connection_strings = [
            POSTGRES_CONNECTION_STRING,
            f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        ]
        
        for conn_str in connection_strings:
            try:
                print(f"🔄 Trying connection: {conn_str.replace(DB_PASSWORD, '***')}")
                engine = create_engine(
                    conn_str,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10
                )
                
                # Test connection
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT version()"))
                    version = result.fetchone()[0]
                    print(f"✅ Connected to PostgreSQL via SQLAlchemy: {version[:50]}...")
                
                return engine
                
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                continue
        
        print("❌ All connection attempts failed")
        return None
        
    except Exception as e:
        print(f"❌ Error creating database engine: {e}")
        return None

def load_data_to_postgresql(tables, engine):
    """Load Excel data into PostgreSQL tables"""
    try:
        print("\n🔄 Loading data into PostgreSQL...")
        
        for sheet_name, df in tables.items():
            # Clean sheet name for table name (remove special characters)
            table_name = sheet_name.replace(' ', '_').replace('-', '_').replace('.', '_')
            
            # Load data into PostgreSQL
            df.to_sql(table_name, engine, index=False, if_exists='replace')
            print(f"✅ Created table '{table_name}' with {len(df)} rows")
            
            # Show column info
            print(f"   Columns: {list(df.columns)[:5]}{'...' if len(df.columns) > 5 else ''}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading data to PostgreSQL: {e}")
        return False

def verify_tables(engine):
    """Verify that tables were created and have data"""
    try:
        print("\n🔍 Verifying tables...")
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if not tables:
            print("❌ No tables found in database")
            return False
        
        print(f"✅ Found {len(tables)} tables: {tables}")
        
        with engine.connect() as conn:
            for table in tables:
                # Use double quotes for case-sensitive table names in PostgreSQL
                result = conn.execute(text(f'SELECT COUNT(*) as count FROM "{table}"'))
                count = result.fetchone()[0]
                print(f"   Table '{table}': {count} rows")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verifying tables: {e}")
        return False

def main():
    print("🚀 Kabaddi Analytics - Complete Database Setup")
    print("=" * 60)
    
    # Step 1: Check PostgreSQL server
    if not check_postgresql_running():
        sys.exit(1)
    
    # Step 2: Check if database exists
    db_exists = check_database_exists()
    
    # Step 3: Create database if needed
    if not db_exists:
        print("\n🔧 Creating database...")
        if not create_database():
            sys.exit(1)
    
    # Step 4: Check Excel file
    if not check_excel_file():
        sys.exit(1)
    
    # Step 5: Load Excel data
    print("\n📊 Loading Excel data...")
    tables = load_excel_sheets()
    if not tables:
        sys.exit(1)
    
    # Step 6: Create database engine
    print("\n🔗 Creating database connection...")
    engine = create_database_engine()
    if not engine:
        sys.exit(1)
    
    # Step 7: Load data to PostgreSQL
    if not load_data_to_postgresql(tables, engine):
        sys.exit(1)
    
    # Step 8: Verify setup
    if not verify_tables(engine):
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("🎉 DATABASE SETUP COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("✅ PostgreSQL database 'kabaddi_data' is ready")
    print("✅ All Excel data has been loaded into tables")
    print("✅ You can now run: python main.py")
    print("\n🚀 Your Kabaddi Analytics system is ready to use!")

if __name__ == "__main__":
    main()
