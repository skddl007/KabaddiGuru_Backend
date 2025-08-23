#!/usr/bin/env python3
"""
One-time migration script to load Excel data into PostgreSQL
Run this script once to migrate your Excel data to PostgreSQL database
"""

import sys
import os
from modules.sqlite_loader import force_reload_from_excel, check_tables_exist, get_database_engine

def main():
    print("🔄 Kabaddi Analytics Data Migration Script")
    print("=" * 50)
    
    try:
        # Check if database is accessible
        engine = get_database_engine()
        print("✅ Successfully connected to PostgreSQL database")
        
        # Check current state
        if check_tables_exist(engine):
            print("\n⚠️  Data already exists in PostgreSQL database!")
            response = input("Do you want to reload data from Excel? (y/N): ").strip().lower()
            
            if response not in ['y', 'yes']:
                print("✅ Migration cancelled. Using existing data.")
                return
        
        # Load data from Excel
        print("\n🔄 Loading data from Excel file (SKDB.xlsx)...")
        force_reload_from_excel()
        
        print("\n✅ Migration completed successfully!")
        print("📊 Your Excel data is now available in PostgreSQL")
        print("🚀 You can now run 'python main.py' for fast queries")
        
    except FileNotFoundError:
        print("❌ Excel file 'SKDB.xlsx' not found!")
        print("Please ensure the file exists in the project directory")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure PostgreSQL is running")
        print("2. Check database credentials in sqlite_loader.py")
        print("3. Run setup_database.py first")
        sys.exit(1)

if __name__ == "__main__":
    main()
