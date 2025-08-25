import pandas as pd
from sqlalchemy import create_engine, text, inspect
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from modules.sheet_loader import load_sheets

# Load environment variables from config.env file
try:
    from dotenv import load_dotenv
    # Load from the main config.env file
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.env')
    load_dotenv(config_path)
except ImportError:
    pass

# PostgreSQL connection parameters from config.env
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Skd6397@@")
DB_NAME = os.getenv("DB_NAME", "kabaddi_data")

# Determine connection string based on environment
import urllib.parse

# Check if we're in deployment mode (Cloud Run)
is_deployment = os.getenv('K_SERVICE') is not None or os.getenv('PORT') is not None

DATABASE_URL = os.getenv("DATABASE_URL")
if is_deployment and DATABASE_URL and DATABASE_URL.strip():
    # Use DATABASE_URL for Cloud SQL connection in deployment
    POSTGRES_CONNECTION_STRING = DATABASE_URL
else:
    # Local development - use individual config (avoid Cloud SQL socket)
    encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
    POSTGRES_CONNECTION_STRING = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def check_and_create_database():
    """
    Check if database exists, create if it doesn't
    """
    # Skip database creation in deployment mode (Cloud SQL)
    is_deployment = os.getenv('K_SERVICE') is not None or os.getenv('PORT') is not None
    if is_deployment:
        print("✅ Skipping database creation in deployment mode (Cloud SQL)")
        return True
    
    try:
        # First, connect to PostgreSQL server without specifying database
        conn = psycopg2.connect(
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
            print(f"🔧 Database '{DB_NAME}' does not exist. Creating...")
            cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"✅ Database '{DB_NAME}' created successfully")
        else:
            print(f"✅ Database '{DB_NAME}' already exists")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error checking/creating database: {e}")
        print("Please ensure:")
        print("1. PostgreSQL is running")
        print(f"2. Username '{DB_USER}' exists") 
        print("3. Password is correct")
        return False

def get_database_engine():
    """
    Get PostgreSQL database engine with optimized connection pooling for better performance
    """
    try:
        engine = create_engine(
            POSTGRES_CONNECTION_STRING,
            pool_pre_ping=True,
            pool_size=10,          # Increased pool size for better concurrency
            max_overflow=20,       # Increased overflow for peak loads
            pool_recycle=1800,     # Recycle connections after 30 minutes
            # pool_timeout=30,       # REMOVED TO PREVENT TIMEOUT ISSUES
            echo=False,            # Set to True for SQL query logging
            # Additional optimizations
            connect_args={
                # "connect_timeout": 10,  # REMOVED TO PREVENT TIMEOUT ISSUES
                "application_name": "kabaddi_analytics"
            }
        )
        return engine
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        print(f"Please ensure PostgreSQL is running and the database '{DB_NAME}' exists")
        raise e

def check_tables_exist(engine):
    """
    Check if required tables exist in PostgreSQL
    """
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        required_tables = ["S_RBR"]  # Based on sheet_loader.py
        
        for table in required_tables:
            if table not in existing_tables:
                return False
                
        # Check if tables have data
        with engine.connect() as conn:
            for table in required_tables:
                result = conn.execute(text(f'SELECT COUNT(*) as count FROM "{table}"'))
                count = result.fetchone()[0]
                if count == 0:
                    print(f"⚠️  Table '{table}' exists but is empty")
                    return False
                print(f"✅ Table '{table}' has {count} rows")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking tables: {e}")
        return False

def load_into_postgresql(tables=None):
    """
    Load data into PostgreSQL database only if tables don't exist or are empty
    Automatically creates database if it doesn't exist
    """
    try:
        # First, ensure database exists
        if not check_and_create_database():
            raise Exception("Failed to create database")
        
        engine = get_database_engine()
        
        # Check if data already exists
        if check_tables_exist(engine):
            print("✅ Data already exists in PostgreSQL, skipping Excel load")
            return engine
        
        print("🔄 Loading data from Excel into PostgreSQL...")
        
        # Load tables from Excel if not provided
        if tables is None:
            tables = load_sheets()
        
        # Load each table into PostgreSQL
        for name, data in tables.items():
            df = pd.DataFrame(data)
            df.to_sql(name, engine, index=False, if_exists='replace')
            print(f"✅ Loaded table '{name}' with {len(df)} rows")
        
        return engine
        
    except Exception as e:
        print(f"❌ Error loading data into PostgreSQL: {e}")
        print("Please ensure PostgreSQL is running and credentials are correct")
        raise e

def force_reload_from_excel():
    """
    Force reload data from Excel file (for updates)
    Automatically creates database if it doesn't exist
    """
    print("🔄 Force reloading data from Excel...")
    
    # Ensure database exists
    if not check_and_create_database():
        raise Exception("Failed to create database")
    
    tables = load_sheets()
    engine = get_database_engine()
    
    for name, data in tables.items():
        df = pd.DataFrame(data)
        df.to_sql(name, engine, index=False, if_exists='replace')
        print(f"✅ Reloaded table '{name}' with {len(df)} rows")
    
    return engine
