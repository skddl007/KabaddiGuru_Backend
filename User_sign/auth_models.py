from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserSigninRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    chat_count: int
    max_chats: int
    is_premium: bool
    created_at: datetime
    last_login: Optional[datetime] = None

class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserResponse] = None
    token: Optional[str] = None

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    reset_token: str
    new_password: str

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
