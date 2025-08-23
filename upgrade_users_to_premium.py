#!/usr/bin/env python3
"""
Script to upgrade specific users to premium for unlimited chat access
Usage: python upgrade_users_to_premium.py
"""

import os
import sys
from dotenv import load_dotenv

# Add the parent directory to the path to import User_sign modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from User_sign.database import UserDatabase

def upgrade_users_to_premium():
    """Upgrade specific users to premium for unlimited chat access"""
    
    # Load environment variables
    config_path = os.path.join(os.path.dirname(__file__), 'config.env')
    load_dotenv(config_path)
    
    # Initialize database connection
    user_db = UserDatabase()
    
    # List of user emails to upgrade to premium
    # Replace these with actual user emails
    users_to_upgrade = [
        "user1@example.com",
        "user2@example.com"
    ]
    
    print("🔧 Upgrading users to premium for unlimited chat access...")
    
    for email in users_to_upgrade:
        try:
            # First, find the user by email
            conn = user_db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, full_name, email FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()
            
            if user:
                user_id, full_name, user_email = user
                
                # Upgrade to premium
                success = user_db.upgrade_to_premium(user_id, "premium")
                
                if success:
                    print(f"✅ Successfully upgraded {full_name} ({user_email}) to premium")
                else:
                    print(f"❌ Failed to upgrade {full_name} ({user_email}) to premium")
            else:
                print(f"⚠️  User with email {email} not found in database")
                
        except Exception as e:
            print(f"❌ Error upgrading user {email}: {e}")
        finally:
            if 'conn' in locals():
                cursor.close()
                conn.close()
    
    print("🎉 User upgrade process completed!")

if __name__ == "__main__":
    upgrade_users_to_premium()

