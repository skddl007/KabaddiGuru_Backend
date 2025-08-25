import psycopg2
import psycopg2.extras
import jwt
import datetime
import secrets
import hashlib
import os
from typing import Optional, Dict, Any
import json
from dotenv import load_dotenv

# Load environment variables - will be handled by main.py
# This ensures consistent environment loading across the application

class UserDatabase:
    def __init__(self):
        # Support both JWT_SECRET_KEY and legacy JWT_SECRET env var names
        self.secret_key = (
            os.getenv("JWT_SECRET_KEY")
            or os.getenv("JWT_SECRET")
            or "your-secret-key-change-in-production"
        )
        # Prefer centralized DATABASE_URL when present; otherwise fall back to discrete vars
        self.database_url = os.getenv('DATABASE_URL')
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'database': os.getenv('DB_NAME', 'kabaddi_data'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'password'),
            'port': os.getenv('DB_PORT', '5432')
        }
        
        # Load admin emails from config
        admin_emails_str = os.getenv('ADMIN_EMAILS', '[]')
        try:
            self.admin_emails = json.loads(admin_emails_str)
        except json.JSONDecodeError:
            self.admin_emails = []
        
        self.init_database()
    
    def is_admin_email(self, email: str) -> bool:
        """Check if the given email is in the admin list"""
        return email.lower() in [admin_email.lower() for admin_email in self.admin_emails]
    
    def get_connection(self):
        """Get PostgreSQL connection"""
        # Check if we're in deployment mode (Cloud Run)
        is_deployment = os.getenv('K_SERVICE') is not None or os.getenv('PORT') is not None
        
        if is_deployment:
            # Use DATABASE_URL for Cloud SQL connection
            if self.database_url and self.database_url.strip():
                return psycopg2.connect(self.database_url)
            else:
                # Fallback to individual config for Cloud SQL
                return psycopg2.connect(**self.db_config)
        else:
            # Local development - use individual config (avoid Cloud SQL socket)
            return psycopg2.connect(**self.db_config)
    
    def init_database(self):
        """Initialize the database with user table"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Create users table with chat limits
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
            
            conn.commit()
            print("✅ PostgreSQL database tables initialized successfully")
            
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    
    def create_user(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """Create a new user with free trial or admin privileges"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Hash the password
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            # Check if user is admin
            is_admin = self.is_admin_email(email)
            
            if is_admin:
                # Admin users get unlimited access
                cursor.execute('''
                    INSERT INTO users (full_name, email, password_hash, chat_count, max_chats, subscription_type, is_premium)
                    VALUES (%s, %s, %s, 0, 999999, 'admin', TRUE)
                    RETURNING id
                ''', (username, email, password_hash))
                print(f"✅ Created admin user: {email}")
            else:
                # Regular users get free trial (10 chats)
                cursor.execute('''
                    INSERT INTO users (full_name, email, password_hash, chat_count, max_chats, subscription_type)
                    VALUES (%s, %s, %s, 0, 10, 'free_trial')
                    RETURNING id
                ''', (username, email, password_hash))
            
            user_id = cursor.fetchone()[0]
            
            # Generate JWT token
            token = self.generate_jwt_token(user_id, username)
            
            conn.commit()
            
            return {
                "success": True,
                "user_id": user_id,
                "username": username,
                "email": email,
                "token": token,
                "chat_count": 0,
                "max_chats": 999999 if is_admin else 10,
                "subscription_type": "admin" if is_admin else "free_trial",
                "is_premium": is_admin
            }
            
        except psycopg2.IntegrityError:
            return {"success": False, "error": "Username or email already exists"}
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            return {"success": False, "error": str(e)}
        finally:
            cursor.close()
            conn.close()

    def save_chat_turn(self, user_id: int, chat_id: str, question: str, response: str, sql_query: str = "", tokens_used: int = 0) -> bool:
        """Persist a single chat turn to chat_history."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''
                INSERT INTO chat_history (user_id, chat_id, question, response, sql_query, tokens_used)
                VALUES (%s, %s, %s, %s, %s, %s)
                ''',
                (user_id, chat_id, question, response, sql_query or "", tokens_used or 0)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error saving chat turn: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def get_user_chats_overview(self, user_id: int):
        """Return list of chat overviews for a user: chat_id, title (first question), last_message timestamp."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''
                SELECT chat_id,
                       (ARRAY_AGG(question ORDER BY timestamp ASC))[1] AS title,
                       MAX(timestamp) AS last_message
                FROM chat_history
                WHERE user_id = %s
                GROUP BY chat_id
                ORDER BY last_message DESC
                ''',
                (user_id,)
            )
            rows = cursor.fetchall()
            return [
                {
                    "chat_id": r[0],
                    "title": (r[1] or "").strip()[:50],
                    "last_message": r[2].isoformat() if r[2] else None,
                }
                for r in rows
            ]
        except Exception as e:
            print(f"❌ Error fetching user chats overview: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def get_chat_messages(self, user_id: int, chat_id: str):
        """Return complete chat messages for a user and chat_id as alternating user/assistant messages."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''
                SELECT question, response, sql_query, timestamp, tokens_used
                FROM chat_history
                WHERE user_id = %s AND chat_id = %s
                ORDER BY timestamp ASC
                ''',
                (user_id, chat_id)
            )
            rows = cursor.fetchall()
            messages = []
            for q, a, sql, ts, tokens in rows:
                messages.append({
                    "id": f"{int(ts.timestamp()*1000)}-u",
                    "role": "user",
                    "content": q,
                    "timestamp": ts.isoformat(),
                })
                messages.append({
                    "id": f"{int(ts.timestamp()*1000)}-a",
                    "role": "assistant",
                    "content": a,
                    "timestamp": ts.isoformat(),
                    "sql_query": sql or None,
                })
            return messages
        except Exception as e:
            print(f"❌ Error fetching chat messages: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def get_all_chats_overview(self):
        """Admin: return overview for all users' chats with user info."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''
                SELECT u.id AS user_id,
                       u.email,
                       ch.chat_id,
                       (ARRAY_AGG(ch.question ORDER BY ch.timestamp ASC))[1] AS title,
                       MAX(ch.timestamp) AS last_message
                FROM users u
                JOIN chat_history ch ON ch.user_id = u.id
                GROUP BY u.id, u.email, ch.chat_id
                ORDER BY last_message DESC
                '''
            )
            rows = cursor.fetchall()
            return [
                {
                    "user_id": r[0],
                    "email": r[1],
                    "chat_id": r[2],
                    "title": (r[3] or "").strip()[:50],
                    "last_message": r[4].isoformat() if r[4] else None,
                }
                for r in rows
            ]
        except Exception as e:
            print(f"❌ Error fetching all chats overview: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def get_chat_messages_admin(self, user_id: int, chat_id: str):
        """Admin: get messages for a given user and chat_id."""
        return self.get_chat_messages(user_id, chat_id)

    def set_user_password_and_admin(self, email: str, new_password: str) -> bool:
        """Set user's password and upgrade to admin privileges."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            password_hash = hashlib.sha256(new_password.encode()).hexdigest()
            cursor.execute('''
                UPDATE users
                SET password_hash = %s,
                    is_premium = TRUE,
                    subscription_type = 'admin',
                    max_chats = 999999
                WHERE email = %s
            ''', (password_hash, email))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Error setting admin password: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user by full_name and return user data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            cursor.execute('''
                SELECT id, full_name, email, chat_count, max_chats, subscription_type, is_premium
                FROM users 
                WHERE full_name = %s AND password_hash = %s
            ''', (username, password_hash))
            
            user = cursor.fetchone()
            
            if user:
                user_id, full_name, email, chat_count, max_chats, subscription_type, is_premium = user
                
                # Update last login
                cursor.execute('''
                    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s
                ''', (user_id,))
                
                # Generate JWT token
                token = self.generate_jwt_token(user_id, full_name)
                
                conn.commit()
                
                return {
                    "success": True,
                    "user_id": user_id,
                    "username": full_name,
                    "email": email,
                    "token": token,
                    "chat_count": chat_count,
                    "max_chats": max_chats,
                    "subscription_type": subscription_type,
                    "is_premium": bool(is_premium)
                }
            else:
                return {"success": False, "error": "Invalid credentials"}
                
        except Exception as e:
            print(f"❌ Error authenticating user: {e}")
            return {"success": False, "error": str(e)}
        finally:
            cursor.close()
            conn.close()

    def authenticate_user_by_email(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user by email and return user data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            cursor.execute('''
                SELECT id, full_name, email, chat_count, max_chats, subscription_type, is_premium
                FROM users 
                WHERE email = %s AND password_hash = %s
            ''', (email, password_hash))
            
            user = cursor.fetchone()
            
            if user:
                user_id, full_name, email, chat_count, max_chats, subscription_type, is_premium = user
                
                # Check if user is admin and update privileges if needed
                is_admin = self.is_admin_email(email)
                if is_admin and not is_premium:
                    # Upgrade existing admin user to premium
                    cursor.execute('''
                        UPDATE users 
                        SET is_premium = TRUE, subscription_type = 'admin', max_chats = 999999
                        WHERE id = %s
                    ''', (user_id,))
                    is_premium = True
                    max_chats = 999999
                    subscription_type = 'admin'
                    print(f"✅ Upgraded existing user to admin: {email}")
                
                # Update last login
                cursor.execute('''
                    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s
                ''', (user_id,))
                
                # Generate JWT token
                token = self.generate_jwt_token(user_id, full_name)
                
                conn.commit()
                
                return {
                    "success": True,
                    "user_id": user_id,
                    "username": full_name,
                    "email": email,
                    "token": token,
                    "chat_count": chat_count,
                    "max_chats": max_chats,
                    "subscription_type": subscription_type,
                    "is_premium": bool(is_premium)
                }
            else:
                return {"success": False, "error": "Invalid credentials"}
                
        except Exception as e:
            print(f"❌ Error authenticating user by email: {e}")
            return {"success": False, "error": str(e)}
        finally:
            cursor.close()
            conn.close()
    
    def verify_jwt_token(self, token: str) -> Optional[int]:
        """Verify JWT token and return user ID"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload.get("user_id")
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def generate_jwt_token(self, user_id: int, username: str) -> str:
        """Generate JWT token for user"""
        payload = {
            "user_id": user_id,
            "username": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")
    
    def can_user_chat(self, user_id: int) -> Dict[str, Any]:
        """Check if user can make a chat request (free trial limit)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT chat_count, max_chats, subscription_type, is_premium, email
                FROM users WHERE id = %s
            ''', (user_id,))
            
            result = cursor.fetchone()
            
            if not result:
                return {"can_chat": False, "error": "User not found"}
            
            chat_count, max_chats, subscription_type, is_premium, email = result
            
            # Check if user is admin
            is_admin = self.is_admin_email(email)
            
            # Admin users always have unlimited access
            if is_admin or is_premium:
                return {
                    "can_chat": True,
                    "chat_count": chat_count,
                    "max_chats": "unlimited",
                    "subscription_type": subscription_type,
                    "remaining_chats": "unlimited",
                    "is_admin": is_admin
                }
            
            # Free trial users have limited chats
            remaining_chats = max_chats - chat_count
            
            if remaining_chats > 0:
                return {
                    "can_chat": True,
                    "chat_count": chat_count,
                    "max_chats": max_chats,
                    "subscription_type": subscription_type,
                    "remaining_chats": remaining_chats,
                    "is_admin": False
                }
            else:
                return {
                    "can_chat": False,
                    "chat_count": chat_count,
                    "max_chats": max_chats,
                    "subscription_type": subscription_type,
                    "remaining_chats": 0,
                    "is_admin": False,
                    "error": "Free trial limit reached. Please upgrade to premium for unlimited chats."
                }
                
        except Exception as e:
            print(f"❌ Error checking chat limit: {e}")
            return {"can_chat": False, "error": str(e)}
        finally:
            cursor.close()
            conn.close()
    
    def increment_chat_count(self, user_id: int) -> bool:
        """Increment user's chat count"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users SET chat_count = chat_count + 1 WHERE id = %s
            ''', (user_id,))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error incrementing chat count: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT id, full_name, email, chat_count, max_chats, subscription_type, is_premium, created_at, last_login
                FROM users WHERE id = %s
            ''', (user_id,))
            
            result = cursor.fetchone()
            
            if result:
                return {
                    "user_id": result[0],
                    "username": result[1],
                    "email": result[2],
                    "chat_count": result[3],
                    "max_chats": result[4],
                    "subscription_type": result[5],
                    "is_premium": bool(result[6]),
                    "created_at": result[7],
                    "last_login": result[8]
                }
            return None
            
        except Exception as e:
            print(f"❌ Error getting user info: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def upgrade_to_premium(self, user_id: int, subscription_type: str = "premium") -> bool:
        """Upgrade user to premium subscription"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users 
                SET is_premium = TRUE, subscription_type = %s, max_chats = 999999
                WHERE id = %s
            ''', (subscription_type, user_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error upgrading user: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    def reset_free_trial(self, user_id: int) -> bool:
        """Reset user's free trial (admin function)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users 
                SET chat_count = 0, max_chats = 10, subscription_type = 'free_trial', is_premium = FALSE
                WHERE id = %s
            ''', (user_id,))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error resetting free trial: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    def request_password_reset(self, email: str) -> Dict[str, Any]:
        """Create a password reset token for the given email and store expiry."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Generate secure token and expiry (1 hour)
            reset_token = secrets.token_urlsafe(32)
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

            # Update user if exists
            cursor.execute('''
                UPDATE users
                SET reset_token = %s,
                    reset_token_expires = %s
                WHERE email = %s
            ''', (reset_token, expires_at, email))

            conn.commit()

            # Do not reveal if user exists; include token only in DEBUG
            debug_mode = os.getenv("DEBUG", "False").lower() == "true"
            return {"success": True, **({"reset_token": reset_token} if debug_mode and cursor.rowcount > 0 else {})}
        except Exception as e:
            print(f"❌ Error creating password reset token: {e}")
            conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            cursor.close()
            conn.close()

    def reset_password_with_token(self, email: str, reset_token: str, new_password: str) -> Dict[str, Any]:
        """Reset password if token matches and not expired."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Verify token and expiry
            cursor.execute('''
                SELECT reset_token, reset_token_expires
                FROM users WHERE email = %s
            ''', (email,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "Invalid token or email"}
            stored_token, expires_at = row
            if not stored_token or stored_token != reset_token:
                return {"success": False, "error": "Invalid token or email"}
            if not expires_at or expires_at < datetime.datetime.utcnow():
                return {"success": False, "error": "Reset token has expired"}

            # Update password and clear token
            password_hash = hashlib.sha256(new_password.encode()).hexdigest()
            cursor.execute('''
                UPDATE users
                SET password_hash = %s,
                    reset_token = NULL,
                    reset_token_expires = NULL
                WHERE email = %s
            ''', (password_hash, email))
            conn.commit()
            return {"success": cursor.rowcount > 0}
        except Exception as e:
            print(f"❌ Error resetting password: {e}")
            conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            cursor.close()
            conn.close()

# Global instance
user_db = UserDatabase()
