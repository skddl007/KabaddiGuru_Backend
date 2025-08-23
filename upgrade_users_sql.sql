-- SQL Commands to upgrade specific users to premium for unlimited chat access
-- Run these commands in your Cloud SQL PostgreSQL database

-- Method 1: Upgrade by email (replace with actual user emails)
UPDATE users 
SET is_premium = TRUE, 
    subscription_type = 'premium', 
    max_chats = 999999
WHERE email IN ('user1@example.com', 'user2@example.com');

-- Method 2: Upgrade by user ID (replace with actual user IDs)
-- UPDATE users 
-- SET is_premium = TRUE, 
--     subscription_type = 'premium', 
--     max_chats = 999999
-- WHERE id IN (1, 2);

-- Verify the changes
SELECT id, full_name, email, is_premium, subscription_type, max_chats, chat_count
FROM users 
WHERE email IN ('user1@example.com', 'user2@example.com');

-- Check all premium users
SELECT id, full_name, email, is_premium, subscription_type, max_chats, chat_count
FROM users 
WHERE is_premium = TRUE;

