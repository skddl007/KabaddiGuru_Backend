import os
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .database import user_db

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

# Pydantic models for request/response
class UserRegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str

class UserLoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    chat_count: int
    max_chats: int
    subscription_type: str
    is_premium: bool
    token: str

class ChatLimitResponse(BaseModel):
    can_chat: bool
    chat_count: int
    max_chats: int
    subscription_type: str
    remaining_chats: int
    error: Optional[str] = None

class ChatOverview(BaseModel):
    chat_id: str
    title: str
    last_message: Optional[str] = None

class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    sql_query: Optional[str] = None

class UpgradeRequest(BaseModel):
    subscription_type: str = "premium"

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirmRequest(BaseModel):
    email: str
    reset_token: str
    new_password: str

# Authentication dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """Get current user from JWT token"""
    token = credentials.credentials
    user_id = user_db.verify_jwt_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id

@router.post("/register", response_model=UserResponse)
async def register_user(request: UserRegisterRequest):
    """Register a new user with free trial"""
    result = user_db.create_user(
        username=request.full_name,
        email=request.email,
        password=request.password
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return UserResponse(
        user_id=result["user_id"],
        username=result["username"],
        email=result["email"],
        chat_count=result["chat_count"],
        max_chats=result["max_chats"],
        subscription_type=result["subscription_type"],
        is_premium=False,
        token=result["token"]
    )

@router.post("/signup", response_model=UserResponse)
async def signup_user(request: UserRegisterRequest):
    """Signup endpoint (alias for register)"""
    return await register_user(request)

@router.post("/login", response_model=UserResponse)
async def login_user(request: UserLoginRequest):
    """Login user and return user data with token"""
    result = user_db.authenticate_user_by_email(
        email=request.email,
        password=request.password
    )
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])
    return UserResponse(
        user_id=result["user_id"],
        username=result["username"],
        email=result["email"],
        chat_count=result["chat_count"],
        max_chats=result["max_chats"],
        subscription_type=result["subscription_type"],
        is_premium=result["is_premium"],
        token=result["token"]
    )

class AdminSetupRequest(BaseModel):
    email: str
    new_password: str

@router.post("/admin/setup")
async def admin_setup(request: AdminSetupRequest, x_admin_setup_token: Optional[str] = Header(None)):
    """Secure admin setup endpoint to set password and privileges for an admin email.
    Requires ADMIN_SETUP_TOKEN env header unless DEBUG=true.
    """
    setup_token = os.getenv("ADMIN_SETUP_TOKEN")
    debug_mode = os.getenv("DEBUG", "False").lower() == "true"
    if not debug_mode:
        if not setup_token or x_admin_setup_token != setup_token:
            raise HTTPException(status_code=403, detail="Forbidden")
    success = user_db.set_user_password_and_admin(request.email, request.new_password)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update admin user")
    return {"success": True}

@router.post("/signin", response_model=UserResponse)
async def signin_user(request: UserLoginRequest):
    """Signin endpoint (alias for login)"""
    return await login_user(request)

@router.post("/password/forgot")
async def password_forgot(request: PasswordResetRequest):
    """Initiate password reset and return success. In DEBUG, return token for testing."""
    result = user_db.request_password_reset(request.email)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to create reset token"))
    # In production, you would email the token. For now, return message and token if present.
    response: Dict[str, Any] = {"success": True, "message": "If the email exists, a reset link has been sent."}
    if "reset_token" in result:
        response["reset_token"] = result["reset_token"]
    return response

@router.post("/password/reset")
async def password_reset(request: PasswordResetConfirmRequest):
    """Reset password with token."""
    result = user_db.reset_password_with_token(request.email, request.reset_token, request.new_password)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Invalid or expired token"))
    return {"success": True}

@router.get("/chat-limit", response_model=ChatLimitResponse)
async def get_chat_limit(user_id: int = Depends(get_current_user)):
    """Get user's chat limit and remaining chats"""
    try:
        result = user_db.can_user_chat(user_id)
        return ChatLimitResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/profile")
async def get_user_profile(user_id: int = Depends(get_current_user)):
    """Get user profile information"""
    try:
        user_info = user_db.get_user_info(user_id)
        if not user_info:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upgrade")
async def upgrade_to_premium(
    request: UpgradeRequest,
    user_id: int = Depends(get_current_user)
):
    """Upgrade user to premium subscription"""
    try:
        success = user_db.upgrade_to_premium(user_id, request.subscription_type)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to upgrade user")
        
        return {"success": True, "message": "Successfully upgraded to premium"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset-trial")
async def reset_free_trial(user_id: int = Depends(get_current_user)):
    """Reset user's free trial (admin function)"""
    try:
        success = user_db.reset_free_trial(user_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to reset free trial")
        
        return {"success": True, "message": "Free trial reset successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/verify")
async def verify_token(user_id: int = Depends(get_current_user)):
    """Verify JWT token and return user info"""
    try:
        user_info = user_db.get_user_info(user_id)
        if not user_info:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {"valid": True, "user": user_info}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chats")
async def list_user_chats(user_id: int = Depends(get_current_user)):
    """Get current user's chat overviews."""
    try:
        chats = user_db.get_user_chats_overview(user_id)
        return {"chats": chats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chats/{chat_id}")
async def get_user_chat_messages(chat_id: str, user_id: int = Depends(get_current_user)):
    """Get current user's messages for a chat_id."""
    try:
        messages = user_db.get_chat_messages(user_id, chat_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/chats")
async def list_all_chats(user_id: int = Depends(get_current_user)):
    """Admin: list all chat overviews across users."""
    try:
        user_info = user_db.get_user_info(user_id)
        if not user_info or user_info.get("subscription_type") != "admin":
            raise HTTPException(status_code=403, detail="Forbidden")
        chats = user_db.get_all_chats_overview()
        return {"chats": chats}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/chat-messages")
async def get_admin_chat_messages(target_user_id: int, chat_id: str, user_id: int = Depends(get_current_user)):
    """Admin: get messages for a user's chat_id."""
    try:
        user_info = user_db.get_user_info(user_id)
        if not user_info or user_info.get("subscription_type") != "admin":
            raise HTTPException(status_code=403, detail="Forbidden")
        messages = user_db.get_chat_messages_admin(target_user_id, chat_id)
        return {"messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
