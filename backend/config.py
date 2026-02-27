"""
Prism AI — Shared Configuration & Client Factories

Centralizes environment loading, API client creation (with caching),
and shared constants used across all generation modules.
"""

import os
import logging
from pathlib import Path
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from groq import Groq
from huggingface_hub import InferenceClient

# ─── Environment ──────────────────────────────────────────────────────────────
_backend_dir = Path(__file__).parent
_project_root = _backend_dir.parent
# Try loading .env from backend/ first, then project root
load_dotenv(_backend_dir / ".env")
load_dotenv(_project_root / ".env")

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("prism")

# ─── Constants ────────────────────────────────────────────────────────────────
DEFAULT_LLM_MODEL = "llama-3.3-70b-versatile"
DEFAULT_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"

# JWT Auth Config
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-prism-ai-key-in-dev-only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Database Config
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/prism")

# Rate Limits by Tier
RATE_LIMITS = {
    "free": {
        "generate-blog": 3,
        "generate-video-script": 3,
        "generate-image": 2,
        "image_batch_max": 1,
        "watermark": True
    },
    "pro": {
        "generate-blog": 50,
        "generate-video-script": 50,
        "generate-image": 30,
        "image_batch_max": 4,
        "watermark": False
    },
    "business": {
        "generate-blog": "inf",
        "generate-video-script": "inf",
        "generate-image": "inf",
        "image_batch_max": 4,
        "watermark": False
    }
}

# Platform-specific image dimensions
PLATFORM_SIZES: dict[str, dict[str, int]] = {
    "instagram": {"width": 1080, "height": 1080},
    "linkedin":  {"width": 1200, "height": 627},
    "twitter":   {"width": 1200, "height": 675},
    "facebook":  {"width": 1200, "height": 630},
    "youtube":   {"width": 1280, "height": 720},
}

# Valid platform and style choices (used for Pydantic validation)
VALID_PLATFORMS = Literal[
    "instagram", "linkedin", "twitter", "facebook", "youtube"
]
VALID_STYLES = Literal[
    "minimalist", "vibrant", "corporate", "futuristic",
    "retro", "elegant", "playful", "dark", "neon",
]


# ─── Client Factories (cached singletons) ────────────────────────────────────
@lru_cache(maxsize=1)
def get_groq_client() -> Groq:
    """Return a cached Groq client instance."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError("API_KEY environment variable is not set.")
    return Groq(api_key=api_key)


@lru_cache(maxsize=1)
def get_hf_client() -> InferenceClient:
    """Return a cached Hugging Face InferenceClient instance."""
    api_key = os.getenv("HF_API_KEY")
    if not api_key:
        raise ValueError("HF_API_KEY environment variable is not set.")
    return InferenceClient(token=api_key)
