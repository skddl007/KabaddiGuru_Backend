# User Authentication System

This module provides a complete user authentication system for the KabaddiGuru application using PostgreSQL database.

## Features

- User registration and login
- JWT token authentication
- Password hashing (SHA-256)
- Chat usage tracking
- Premium user management
- Password reset functionality

## Database Schema

### Users Table
- `id` - Primary key (SERIAL)
- `email` - Unique email address
- `password_hash` - Hashed password
- `full_name` - User's full name
- `chat_count` - Number of chats used
- `max_chats` - Maximum allowed chats
- `is_premium` - Premium user status
- `created_at` - Account creation timestamp
- `last_login` - Last login timestamp
- `reset_token` - Password reset token
- `reset_token_expires` - Reset token expiration

### Chat Sessions Table
- `id` - Primary key (SERIAL)
- `user_id` - Foreign key to users table
- `chat_id` - Unique chat session ID
- `message_count` - Number of messages in session
- `created_at` - Session creation timestamp
- `last_activity` - Last activity timestamp

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configuration

All configuration is centralized in the main `config.env` file located at:
```
kabbadi_analytics/config.env
```

The authentication system automatically loads configuration from this file, including:
- Database connection settings
- JWT configuration

### 3. Configure Database Connection

Run the configuration script to update the main config.env file:

```bash
python configure_database.py
```

This will prompt you for:
- Database host (default: localhost)
- Database port (default: 5432)
- Database name (default: kabaddi_data)
- Database user (default: postgres)
- Database password

### 4. Create Database (if not exists)

If the database doesn't exist, create it:

```sql
CREATE DATABASE kabaddi_data;
```

### 5. Run Database Setup

```bash
python setup_postgresql.py
```

This will:
- Connect to your PostgreSQL database
- Create all required tables
- Test the functionality
- Verify the setup

### 6. Verify Setup

Check that all tables were created:

```bash
python -c "
from database import UserDatabase
db = UserDatabase()
print('✅ Database setup completed successfully!')
"
```

## API Endpoints

### Authentication
- `POST /auth/signup` - User registration
- `POST /auth/signin` - User login
- `GET /auth/me` - Get current user info
- `PUT /auth/me` - Update user profile

### User Management
- `POST /auth/upgrade-premium` - Upgrade to premium
- `GET /auth/chat-limit` - Get chat usage info
- `POST /auth/reset-password` - Request password reset
- `POST /auth/reset-password/confirm` - Confirm password reset

## Usage Example

```python
from database import UserDatabase

# Initialize database
db = UserDatabase()

# Create a new user
user = db.create_user(
    email="user@example.com",
    password="SecurePass123",
    full_name="John Doe"
)

# Authenticate user
auth_user = db.authenticate_user("user@example.com", "SecurePass123")

# Create JWT token
token = db.create_jwt_token(user["id"])
```

## Security Features

- Password hashing using SHA-256
- JWT token authentication
- Session management
- Secure password requirements

## Configuration File

The system uses the main `config.env` file for all configuration:

```env
# Gemini API Configuration
GOOGLE_API_KEY=your_api_key

# Model Configuration
GEMINI_MODEL=gemini-2.5-flash-preview-05-20

# PostgreSQL Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kabaddi_data
DB_USER=postgres
DB_PASSWORD=your_password

# JWT Configuration
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

## Notes

- The system no longer stores `team_name` and `role` fields as requested
- All passwords must meet minimum security requirements
- JWT tokens expire after 24 hours
- Premium users have unlimited chat access
- All configuration is centralized in `config.env` file
