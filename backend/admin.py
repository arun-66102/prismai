from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from datetime import datetime

from middleware import get_admin_user
import database

router = APIRouter(prefix="/admin", tags=["Admin"])

class UserUpdateRequest(BaseModel):
    tier: str
    role: str
    is_active: bool

class UserAdminResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    tier: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None

class AdminStatsResponse(BaseModel):
    total_users: int
    total_blogs: int
    total_videos: int
    total_images: int

@router.get("/users", response_model=List[UserAdminResponse])
async def list_users(admin_user: dict = Depends(get_admin_user)):
    """List all registered users. Admin only."""
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users ORDER BY created_at DESC")
        return [dict(row) for row in rows]

@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(admin_user: dict = Depends(get_admin_user)):
    """Get platform-wide generation stats. Admin only."""
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        blogs_count = await conn.fetchval("SELECT COUNT(*) FROM usage_logs WHERE endpoint = 'generate-blog'")
        videos_count = await conn.fetchval("SELECT COUNT(*) FROM usage_logs WHERE endpoint = 'generate-video-script'")
        images_count = await conn.fetchval("SELECT COUNT(*) FROM usage_logs WHERE endpoint = 'generate-image'")
            
        return AdminStatsResponse(
            total_users=users_count,
            total_blogs=blogs_count,
            total_videos=videos_count,
            total_images=images_count
        )

@router.put("/users/{user_id}")
async def update_user(user_id: str, request: UserUpdateRequest, admin_user: dict = Depends(get_admin_user)):
    """Update a user's subscription tier, role, and active status. Admin only."""
    if request.tier not in ["free", "pro", "business"]:
        raise HTTPException(status_code=400, detail="Invalid tier")
    if request.role not in ["user", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
        
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET tier = $1, role = $2, is_active = $3 WHERE id = $4", 
            request.tier, request.role, request.is_active, user_id
        )
        
    return {"message": "User updated successfully"}
