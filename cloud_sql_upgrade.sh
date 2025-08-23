#!/bin/bash

# Script to connect to Cloud SQL and upgrade users to premium
# Make sure you have gcloud CLI installed and authenticated

echo "🔧 Connecting to Cloud SQL and upgrading users to premium..."

# Set your project ID
PROJECT_ID="kabaddiguru"
INSTANCE_NAME="kabaddi-sql"
DATABASE_NAME="kabaddi_data"
DB_USER="user"

# Connect to Cloud SQL and run upgrade commands
gcloud sql connect $INSTANCE_NAME \
    --user=$DB_USER \
    --database=$DATABASE_NAME \
    --project=$PROJECT_ID \
    --quiet \
    << 'EOF'

-- Upgrade specific users to premium (replace with actual emails)
UPDATE users 
SET is_premium = TRUE, 
    subscription_type = 'premium', 
    max_chats = 999999
WHERE email IN ('user1@example.com', 'user2@example.com');

-- Verify the changes
SELECT id, full_name, email, is_premium, subscription_type, max_chats, chat_count
FROM users 
WHERE email IN ('user1@example.com', 'user2@example.com');

-- Show all premium users
SELECT id, full_name, email, is_premium, subscription_type, max_chats, chat_count
FROM users 
WHERE is_premium = TRUE;

EOF

echo "✅ User upgrade completed!"

