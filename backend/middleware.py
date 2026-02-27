from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any

from auth import decode_token
from database import get_user_by_id, get_today_usage
from config import RATE_LIMITS

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(request: Request) -> Dict[str, Any]:
    try:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            print("DEBUG: Missing or invalid Authorization header")
            raise credentials_exception
            
        token = auth_header.split(" ")[1]
        print(f"DEBUG: Token starts with: {token[:10]}...")
        payload = decode_token(token)
        if payload is None:
            print("DEBUG: decode_token returned None")
            raise credentials_exception
            
        user_id: str = payload.get("sub")
        if user_id is None:
            print("DEBUG: payload missing 'sub'")
            raise credentials_exception
            
        print(f"DEBUG: Fetching user {user_id}")
        user = await get_user_by_id(user_id)
        if user is None:
            print("DEBUG: get_user_by_id returned None")
            raise credentials_exception
            
        if not user["is_active"]:
            print("DEBUG: User is not active")
            raise credentials_exception
            
        print(f"DEBUG: User is authenticated {user['email']}")
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "tier": user["tier"],
            "is_active": user["is_active"],
            "created_at": user["created_at"]
        }
    except Exception as e:
        print(f"DEBUG EXCEPTION in get_current_user: {e}")
        import traceback
        traceback.print_exc()
        raise e

async def get_admin_user(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user

def get_rate_limiter(endpoint: str):
    async def rate_limiter(user: Dict[str, Any] = Depends(get_current_user)):
        tier = user.get("tier", "free")
        limits = RATE_LIMITS.get(tier, RATE_LIMITS["free"])
        limit = limits.get(endpoint)
        
        if limit is None or limit == "unlimited":
            return user
            
        usage = await get_today_usage(user["id"], endpoint)
        if usage >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Daily limit of {limit} {endpoint} reached for {tier} tier. Upgrade to Pro!"
            )
            
        return user
    return rate_limiter
