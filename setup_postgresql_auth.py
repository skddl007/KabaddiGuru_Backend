#!/usr/bin/env python3
"""
Setup script for PostgreSQL authentication database
"""

import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def setup_postgresql_auth():
    """Setup PostgreSQL database for authentication"""
    
    # Database configuration
    database_url = os.getenv('DATABASE_URL')
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'password'),
        'port': os.getenv('DB_PORT', '5432')
    }
    
    db_name = os.getenv('DB_NAME', 'kabaddi_data')
    
    print("🏗️ Setting up PostgreSQL authentication database...")
    
    try:
        # Connect to PostgreSQL server (not to a specific database)
        conn = psycopg2.connect(database_url) if (database_url and database_url.strip()) else psycopg2.connect(**db_config)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone()
        
        if not exists:
            print(f"📦 Creating database '{db_name}'...")
            cursor.execute(f'CREATE DATABASE {db_name}')
            print(f"✅ Database '{db_name}' created successfully")
        else:
            print(f"✅ Database '{db_name}' already exists")
        
        cursor.close()
        conn.close()
        
        # Now connect to the specific database and create tables
        db_config['database'] = db_name
        conn = psycopg2.connect(database_url) if (database_url and database_url.strip()) else psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Create users table
        print("👥 Creating users table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                full_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                chat_count INTEGER DEFAULT 0,
                max_chats INTEGER DEFAULT 10,
                is_premium BOOLEAN DEFAULT FALSE,
                subscription_type VARCHAR(50) DEFAULT 'free_trial'
            )
        ''')
        
        # Create chat history table
        print("💬 Creating chat history table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                chat_id VARCHAR(255),
                question TEXT,
                response TEXT,
                sql_query TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tokens_used INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create indexes for better performance
        print("📊 Creating indexes...")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_full_name ON users(full_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_history_chat_id ON chat_history(chat_id)')
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ PostgreSQL authentication database setup completed successfully!")
        print(f"📋 Database: {db_name}")
        print(f"🌐 Host: {db_config['host']}:{db_config['port']}")
        print(f"👤 User: {db_config['user']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up PostgreSQL database: {e}")
        return False

def test_connection():
    """Test database connection"""
    print("\n🧪 Testing database connection...")
    
    try:
        from User_sign.database import UserDatabase
        user_db = UserDatabase()
        
        # Test connection by trying to get a connection
        conn = user_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        cursor.close()
        conn.close()
        
        print(f"✅ Database connection successful!")
        print(f"📋 PostgreSQL version: {version[0]}")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🏏 KABADDI ANALYTICS - POSTGRESQL AUTH SETUP")
    print("=" * 50)
    
    # Setup database
    if setup_postgresql_auth():
        # Test connection
        test_connection()
        print("\n🎉 Setup completed successfully!")
    else:
        print("\n❌ Setup failed!")

if __name__ == "__main__":
    main()
