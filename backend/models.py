from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    tier: str
    created_at: datetime

class UsageStats(BaseModel):
    blogs_generated: int
    blogs_total: int
    blogs_limit: int | float | str
    video_scripts_generated: int
    video_scripts_total: int
    video_scripts_limit: int | float | str
    images_generated: int
    images_total: int
    images_limit: int | float | str
    watermark: bool

class UserProfileResponse(BaseModel):
    user: UserResponse
    usage: UsageStats

class HistoryItem(BaseModel):
    id: int
    gen_type: str
    input_params: dict
    output_data: str | None = None
    image_urls: list[str] | None = None
    image_prompt: str | None = None
    created_at: datetime

class HistoryListResponse(BaseModel):
    items: list[HistoryItem]
    total: int
    has_more: bool

class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to translate")
    target_language: str = Field(..., min_length=1, max_length=50, description="Target language")
