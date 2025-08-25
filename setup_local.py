#!/usr/bin/env python3
"""
Local Development Setup Script for KabaddiGuru Backend
This script helps set up the local development environment.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def check_postgresql():
    """Check if PostgreSQL is installed and running"""
    try:
        # Try to connect to PostgreSQL
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="Skd6397@@"
        )
        conn.close()
        print("✅ PostgreSQL connection successful")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print("\n📋 To set up PostgreSQL locally:")
        print("1. Install PostgreSQL from https://www.postgresql.org/download/")
        print("2. Create a user 'postgres' with password 'password'")
        print("3. Or update config.env with your PostgreSQL credentials")
        return False

def check_dependencies():
    """Check if required Python packages are installed"""
    required_packages = [
        'fastapi',
        'uvicorn',
        'psycopg2-binary',
        'python-dotenv',
        'pandas',
        'sqlalchemy',
        'langchain',
        'google-generativeai'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package}")
    
    if missing_packages:
        print(f"\n📦 Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
            print("✅ All packages installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install packages")
            return False
    
    return True

def setup_config():
    """Set up configuration files"""
    config_path = Path("config.env")
    
    if config_path.exists():
        print("✅ config.env already exists")
        return True
    
    print("📝 Creating config.env for local development...")
    
    config_content = """# Database Configuration - Local Development
# This file is for local development only
# DO NOT commit this file to version control

# Local PostgreSQL Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kabaddi_data
DB_USER=postgres
DB_PASSWORD=Skd6397@@

# JWT Configuration
JWT_SECRET=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# API Configuration
GOOGLE_API_KEY=your-google-api-key
GEMINI_MODEL=gemini-2.5-flash-preview-05-20

# Frontend Configuration
FRONTEND_ORIGIN=http://localhost:3000

# Debug Configuration
DEBUG=true

# Admin Configuration
ADMIN_EMAILS=["admin@example.com"]
"""
    
    try:
        with open(config_path, 'w') as f:
            f.write(config_content)
        print("✅ config.env created successfully")
        print("⚠️  Please update config.env with your actual credentials")
        return True
    except Exception as e:
        print(f"❌ Failed to create config.env: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 KabaddiGuru Backend - Local Development Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    print("\n📦 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    
    print("\n⚙️  Setting up configuration...")
    if not setup_config():
        sys.exit(1)
    
    print("\n🐘 Checking PostgreSQL...")
    if not check_postgresql():
        print("\n⚠️  PostgreSQL setup required. Please:")
        print("1. Install PostgreSQL")
        print("2. Update config.env with your credentials")
        print("3. Run this script again")
        sys.exit(1)
    
    print("\n✅ Setup completed successfully!")
    print("\n🎯 Next steps:")
    print("1. Update config.env with your actual credentials")
    print("2. Run: uvicorn main:app --reload")
    print("3. Open http://localhost:8000/docs for API documentation")

if __name__ == "__main__":
    main()
