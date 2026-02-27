"""
Prism AI — FastAPI Application Entry Point

Exposes endpoints for blog, video-script, and image generation.
Serves the frontend SPA at root.
"""

import logging
import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uuid

from config import VALID_PLATFORMS, VALID_STYLES, RATE_LIMITS
from blog_generation import generate_blog
from video_script import generate_video_script
from image_generation import generate_image, IMAGE_DIR
import database
from database import init_db, log_usage
from auth import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    create_refresh_token
)
from middleware import get_current_user, get_rate_limiter
from models import RegisterRequest, TokenResponse, UserResponse, UserProfileResponse, UsageStats
import database
import admin

logger = logging.getLogger("prism.api")

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Prism AI",
    description="AI-powered Blog, Video Script & Image Generation API",
    version="2.0.0",
)

@app.on_event("startup")
async def startup_event():
    await init_db()

# CORS — allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)

# Serve generated images as static files
app.mount("/images", StaticFiles(directory=str(IMAGE_DIR)), name="images")

# Resolve frontend directory: check env var first, then relative path
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", Path(__file__).parent.parent / "frontend"))

# Only mount static files if the frontend directory exists
if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    logger.info("Frontend directory found at %s — serving static files.", FRONTEND_DIR)
else:
    logger.warning("Frontend directory not found at %s — static file serving disabled.", FRONTEND_DIR)


# ─── Request Models (with validation) ────────────────────────────────────────
class BlogRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=100, description="Name of the product")
    tone: str = Field(..., min_length=1, max_length=50, description="Writing tone")
    word_count: int = Field(..., ge=100, le=5000, description="Approximate word count (100-5000)")


class VideoRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=100, description="Name of the product")
    tone: str = Field(..., min_length=1, max_length=50, description="Writing tone")
    duration: int = Field(..., ge=1, le=30, description="Video duration in minutes (1-30)")


class ImageRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=100, description="Name of the product")
    style: VALID_STYLES = Field(..., description="Visual style for the image")
    platform: VALID_PLATFORMS = Field(..., description="Target social media platform")
    seed: int | None = Field(None, description="Optional seed for reproducible generation")
    n: int = Field(1, ge=1, le=4, description="Number of images to generate (1-4)")


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/")
async def home():
    """Serve the frontend SPA (or a fallback message if frontend is not deployed)."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file))
    return JSONResponse(
        {"message": "Prism AI API is running. Frontend not found at this path."},
        status_code=200,
    )


@app.get("/health")
async def health():
    """Simple health-check endpoint."""
    return {"status": "ok"}


@app.post("/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """Register a new user."""
    user = await database.get_user_by_email(request.email)
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(request.password)
    
    user_count = await database.get_user_count()
    role = "admin" if user_count == 0 else "user"
             
    pool = await database.get_pool()
    async with pool.acquire() as conn:
         await conn.execute(
             "INSERT INTO users (id, email, name, password_hash, role) VALUES ($1, $2, $3, $4, $5)",
             user_id, request.email, request.name, hashed_password, role
         )
             
    access_token = create_access_token(data={"sub": user_id, "tier": "free"})
    refresh_token = create_refresh_token(data={"sub": user_id})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@app.post("/auth/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login to get JWT tokens."""
    user = await database.get_user_by_email(form_data.username) # OAuth2 uses 'username' field for email
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET last_login = $1 WHERE id = $2", datetime.utcnow(), user["id"])
        
    access_token = create_access_token(data={"sub": user["id"], "tier": user["tier"]})
    refresh_token = create_refresh_token(data={"sub": user["id"]})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserProfileResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user profile and usage stats."""
    print(f"DEBUG IN SECURE ROUTE: User id is {current_user['id']}")
    user_id = current_user["id"]
    tier = current_user["tier"]
    limits = RATE_LIMITS.get(tier, RATE_LIMITS["free"])
    
    blogs_used = await database.get_today_usage(user_id, "generate-blog")
    video_used = await database.get_today_usage(user_id, "generate-video-script")
    image_used = await database.get_today_usage(user_id, "generate-image")
    
    usage = UsageStats(
        blogs_generated=blogs_used,
        blogs_limit=limits.get("generate-blog", 0),
        video_scripts_generated=video_used,
        video_scripts_limit=limits.get("generate-video-script", 0),
        images_generated=image_used,
        images_limit=limits.get("generate-image", 0),
        watermark=limits.get("watermark", True)
    )
    
    return {"user": current_user, "usage": usage}

@app.post("/generate-blog", dependencies=[Depends(get_rate_limiter("generate-blog"))])
async def create_blog(request: BlogRequest, current_user: dict = Depends(get_current_user)):
    """Generate an SEO-optimized blog article."""
    try:
        result = await generate_blog(
            product_name=request.product_name,
            tone=request.tone,
            word_count=request.word_count,
        )
        await log_usage(current_user["id"], "generate-blog")
        limits = RATE_LIMITS.get(current_user["tier"], RATE_LIMITS["free"])
        return result
    except Exception as e:
        logger.exception("Blog generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-video-script", dependencies=[Depends(get_rate_limiter("generate-video-script"))])
async def create_video_script(request: VideoRequest, current_user: dict = Depends(get_current_user)):
    """Generate an engaging video script."""
    try:
        result = await generate_video_script(
            product_name=request.product_name,
            tone=request.tone,
            duration_mins=request.duration,
        )
        await log_usage(current_user["id"], "generate-video-script")
        return result
    except Exception as e:
        logger.exception("Video script generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-image", dependencies=[Depends(get_rate_limiter("generate-image"))])
async def create_image(request: ImageRequest, current_user: dict = Depends(get_current_user)):
    """Generate a social media image for a product."""
    limits = RATE_LIMITS.get(current_user["tier"], RATE_LIMITS["free"])
    n = min(request.n, limits.get("image_batch_max", 1))
    watermark = limits.get("watermark", True)
    try:
        result = await generate_image(
            product_name=request.product_name,
            style=request.style,
            platform=request.platform,
            seed=request.seed,
            n=n,
            watermark=watermark,
        )
        await log_usage(current_user["id"], "generate-image")
        return result
    except Exception as e:
        logger.exception("Image generation failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Entry Point ──────────────────────────────────────────────────────────────
# Run: python -m uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)