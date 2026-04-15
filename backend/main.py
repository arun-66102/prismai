"""
Prism AI — FastAPI Application Entry Point

Exposes endpoints for blog, video-script, and image generation.
Serves the frontend SPA at root.
"""

import logging
import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uuid

from config import VALID_PLATFORMS, VALID_STYLES, RATE_LIMITS, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET
import razorpay
import hmac
import hashlib

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

from blog_generation import generate_blog
from video_script import generate_video_script
from image_generation import generate_image, IMAGE_DIR
import database
from database import init_db, log_usage, save_generation
from auth import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    create_refresh_token
)
from middleware import get_current_user, get_rate_limiter
from models import (
    RegisterRequest, OTPRequest, TokenResponse, UserResponse, 
    UserProfileResponse, UsageStats,
    HistoryItem, HistoryListResponse, TranslateRequest
)
import database
import admin
from translation import translate_text

logger = logging.getLogger("prism.api")

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Prism AI",
    description="AI-powered Blog, Video Script & Image Generation API",
    version="2.0.0",
)

@app.on_event("startup")
async def startup_event():
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database during startup: {e}")
        # We don't raise here so the app can still boot and serve /health
        # Endpoints that require DB will fail gracefully when they try to get a connection

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
    product_name: str = Field(..., min_length=1, max_length=1000, description="Product name or detailed description")
    tone: str = Field(..., min_length=1, max_length=50, description="Writing tone")
    word_count: int = Field(..., ge=100, le=5000, description="Approximate word count (100-5000)")


class VideoRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=1000, description="Product name or detailed description")
    tone: str = Field(..., min_length=1, max_length=50, description="Writing tone")
    duration: int = Field(..., ge=1, le=30, description="Video duration in minutes (1-30)")


class ImageRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=1000, description="Product name or detailed description")
    style: VALID_STYLES = Field(..., description="Visual style for the image")
    platform: VALID_PLATFORMS = Field(..., description="Target social media platform")
    seed: int | None = Field(None, description="Optional seed for reproducible generation")
    n: int = Field(1, ge=1, le=4, description="Number of images to generate (1-4)")

class CheckoutRequest(BaseModel):
    tier: str = Field(..., description="Desired tier: pro or business")

class PaymentVerificationRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    tier: str

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
    # Try to ping the database for a more accurate health check
    db_status = "ok"
    try:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
    except Exception as e:
        db_status = f"unreachable: {str(e)}"
        
    return {"status": "ok", "database": db_status}


@app.post("/auth/request-otp")
async def request_otp(request: OTPRequest):
    """Generate and send an OTP for a new user registration."""
    user = await database.get_user_by_email(request.email)
    if user:
        raise HTTPException(status_code=400, detail="Account already exists. Please login instead.")
    
    from email_service import send_otp_email
    from datetime import datetime, timedelta
    
    # Generate and send the OTP
    otp = await send_otp_email(request.email, request.name)
    
    # Save code to DB (expires in 10 minutes)
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    await database.save_otp(request.email, otp, expires_at)
    
    return {"message": "Verification code sent to your email."}

@app.post("/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """Verify OTP and register a new user."""
    user = await database.get_user_by_email(request.email)
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Verify OTP
    is_valid_otp = await database.verify_otp(request.email, request.otp)
    if not is_valid_otp:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code. Please request a new one.")
        
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
         
    # Clean up OTP after successful registration
    await database.delete_otp(request.email)
             
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
    blogs_total = await database.get_total_usage(user_id, "generate-blog")
    video_used = await database.get_today_usage(user_id, "generate-video-script")
    video_total = await database.get_total_usage(user_id, "generate-video-script")
    image_used = await database.get_today_usage(user_id, "generate-image")
    image_total = await database.get_total_usage(user_id, "generate-image")
    
    usage = UsageStats(
        blogs_generated=blogs_used,
        blogs_total=blogs_total,
        blogs_limit=limits.get("generate-blog", 0),
        video_scripts_generated=video_used,
        video_scripts_total=video_total,
        video_scripts_limit=limits.get("generate-video-script", 0),
        images_generated=image_used,
        images_total=image_total,
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
        
        # Save to history
        await _save_with_limit(current_user, "blog",
            {"product_name": request.product_name, "tone": request.tone, "word_count": request.word_count},
            output_data=result.get("generated_blog"))
        
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
        
        # Save to history
        await _save_with_limit(current_user, "video",
            {"product_name": request.product_name, "tone": request.tone, "duration": request.duration},
            output_data=result.get("generated_script"))
        
        return result
    except Exception as e:
        logger.exception("Video script generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/translate")
async def translate_text_endpoint(request: TranslateRequest, current_user: dict = Depends(get_current_user)):
    """Translate text to the target language."""
    try:
        result = await translate_text(
            text=request.text,
            target_language=request.target_language,
        )
        return result
    except Exception as e:
        logger.exception("Translation failed")
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
        
        # Save to history
        img_urls = [img.get("image_url", "") for img in result.get("images", [])]
        await _save_with_limit(current_user, "image",
            {"product_name": request.product_name, "style": request.style, "platform": request.platform, "n": n},
            image_urls=img_urls, image_prompt=result.get("image_prompt"))
        
        return result
    except Exception as e:
        logger.exception("Image generation failed")
        raise HTTPException(status_code=500, detail=str(e))

# ─── History Helper ─────────────────────────────────────────────────────────
async def _save_with_limit(user: dict, gen_type: str, input_params: dict,
                           output_data: str = None, image_urls: list = None,
                           image_prompt: str = None):
    """Save generation to history, auto-pruning oldest entries if tier limit exceeded."""
    try:
        user_id = user["id"]
        tier = user.get("tier", "free")
        limits = RATE_LIMITS.get(tier, RATE_LIMITS["free"])
        history_limit = limits.get("history_limit", 25)
        
        # Save the new entry
        await save_generation(user_id, gen_type, input_params, output_data, image_urls, image_prompt)
        
        # Enforce limit for non-unlimited tiers
        if str(history_limit).lower() not in ("inf", "unlimited"):
            count = await database.get_history_count(user_id)
            if count > int(history_limit):
                # Delete oldest entries that exceed the limit
                pool = await database.get_pool()
                async with pool.acquire() as conn:
                    await conn.execute('''
                        DELETE FROM generation_history
                        WHERE id IN (
                            SELECT id FROM generation_history
                            WHERE user_id = $1
                            ORDER BY created_at ASC
                            LIMIT $2
                        )
                    ''', user_id, count - int(history_limit))
    except Exception as e:
        logger.error(f"Failed to save generation history: {e}")


# ─── History API Routes ─────────────────────────────────────────────────────
from typing import Optional

@app.get("/history", response_model=HistoryListResponse)
async def get_history(
    type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get generation history for the current user."""
    if type and type not in ("blog", "video", "image"):
        raise HTTPException(status_code=400, detail="Invalid type filter. Use blog, video, or image.")
    
    limit = min(limit, 50)
    items = await database.get_user_history(current_user["id"], gen_type=type, limit=limit, offset=offset)
    total = await database.get_history_count(current_user["id"], gen_type=type)
    
    return {
        "items": items,
        "total": total,
        "has_more": (offset + limit) < total
    }


@app.get("/history/{history_id}", response_model=HistoryItem)
async def get_history_detail(
    history_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get a single history entry."""
    item = await database.get_history_item(history_id, current_user["id"])
    if not item:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return item


@app.delete("/history/{history_id}")
async def delete_history(
    history_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a single history entry."""
    deleted = await database.delete_history_item(history_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return {"message": "History entry deleted."}


@app.delete("/history")
async def clear_history(
    current_user: dict = Depends(get_current_user)
):
    """Clear all history for the current user."""
    await database.delete_all_history(current_user["id"])
    return {"message": "All history cleared."}

# ─── Razorpay Integration ─────────────────────────────────────────────────────

@app.post("/create-razorpay-order")
async def create_razorpay_order(request: CheckoutRequest, current_user: dict = Depends(get_current_user)):
    try:
        # Amount is in paise (1 INR = 100 paise)
        # Assuming USD $4 = ~ ₹399 and USD $6 = ~ ₹599
        tier_price = 39900 if request.tier == "pro" else 59900
        
        order_data = {
            "amount": tier_price,
            "currency": "INR",
            "receipt": f"rcpt_{str(current_user.get('id', 'unknown'))[:8]}_{str(uuid.uuid4())[:8]}",
            "notes": {
                "user_id": current_user["id"],
                "tier": request.tier
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        return {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": RAZORPAY_KEY_ID,
            "tier": request.tier
        }
    except Exception as e:
        logger.exception("Razorpay order creation failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify-razorpay-payment")
async def verify_razorpay_payment(req: PaymentVerificationRequest, current_user: dict = Depends(get_current_user)):
    try:
        # Verify the signature from the frontend
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': req.razorpay_order_id,
            'razorpay_payment_id': req.razorpay_payment_id,
            'razorpay_signature': req.razorpay_signature
        })
        
        # Valid signature, secure to upgrade
        success = await database.update_user_tier(current_user["id"], req.tier)
        if success:
            logger.info(f"User {current_user['id']} successfully verified and upgraded to {req.tier}.")
            return {"status": "success"}
        else:
            raise HTTPException(status_code=500, detail="Database update failed")
            
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Signature Verification Failed")
    except Exception as e:
        logger.exception("Payment Verification Error")
        raise HTTPException(status_code=500, detail=str(e))




# ─── Entry Point ──────────────────────────────────────────────────────────────
# Run: python -m uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
