"""
Prism AI — Image Generation Module

Uses a two-step pipeline:
  1. Groq LLM crafts an optimized image prompt
  2. Hugging Face Inference API (FLUX.1-schnell) generates the image

Supports configurable model, seed, per-platform dimensions, and watermarking.
"""

import asyncio
import logging
import uuid
from pathlib import Path

from PIL import Image, ImageEnhance

from config import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_LLM_MODEL,
    PLATFORM_SIZES,
    get_groq_client,
    get_hf_client,
)

logger = logging.getLogger("prism.image")

import os
# Directory to save generated images (use /tmp on Vercel)
if os.getenv("VERCEL"):
    IMAGE_DIR = Path("/tmp/generated_images")
else:
    IMAGE_DIR = Path(__file__).parent / "generated_images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# Watermark logo path
WATERMARK_PATH = Path(__file__).parent.parent / "frontend" / "watermark.png"


# ─── Watermark Helper ────────────────────────────────────────────────────────
def _apply_watermark(
    image: Image.Image,
    opacity: float = 0.4,
    scale: float = 0.08,
    padding: int = 12,
) -> Image.Image:
    """
    Overlay logo.png as a semi-transparent watermark on the bottom-right corner.

    Args:
        image:   The generated PIL Image to watermark.
        opacity: Watermark transparency (0.0 = invisible, 1.0 = fully opaque).
        scale:   Watermark size relative to the image width (0.15 = 15%).
        padding: Pixel padding from the bottom-right edge.

    Returns:
        A new PIL Image with the watermark composited.
    """
    if not WATERMARK_PATH.exists():
        logger.warning("Watermark logo not found at %s — skipping.", WATERMARK_PATH)
        return image

    # Load and resize watermark
    watermark = Image.open(WATERMARK_PATH).convert("RGBA")
    wm_width = int(image.width * scale)
    wm_ratio = wm_width / watermark.width
    wm_height = int(watermark.height * wm_ratio)
    watermark = watermark.resize((wm_width, wm_height), Image.LANCZOS)

    # Adjust opacity
    alpha = watermark.split()[3]  # extract alpha channel
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
    watermark.putalpha(alpha)

    # Position: bottom-right with padding
    base = image.convert("RGBA")
    x = base.width - wm_width - padding
    y = base.height - wm_height - padding

    # Composite and convert back to RGB for PNG saving
    base.paste(watermark, (x, y), watermark)
    return base.convert("RGB")


# ─── Prompt Engineering ──────────────────────────────────────────────────────
async def _generate_image_prompt(
    product_name: str,
    style: str,
    platform: str,
) -> str:
    """
    Use Groq LLM to create an optimized image-generation prompt
    from the product name, style, and target platform.
    """
    meta_prompt = f"""You are an expert social media visual designer.

Generate a detailed, vivid image generation prompt for an AI diffusion model.
The image should be a stunning social media graphic for the following:

Product Name: {product_name}
Visual Style: {style}
Target Platform: {platform}

Requirements:
- Describe colors, composition, lighting, and mood in detail
- Make it visually striking and scroll-stopping for {platform}
- Do NOT ask the model to render any text or typography — diffusion models handle text poorly
- Focus on abstract shapes, product imagery, and visual storytelling instead
- Keep the prompt under 200 words

Output the image prompt directly, nothing else."""

    client = get_groq_client()

    # Groq SDK is synchronous — run in a thread to avoid blocking the event loop
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=DEFAULT_LLM_MODEL,
        messages=[
            {"role": "system", "content": "You are a visual design prompt engineer."},
            {"role": "user", "content": meta_prompt},
        ],
        temperature=0.8,
        max_tokens=300,
    )

    return response.choices[0].message.content.strip()


# ─── Image Generation ────────────────────────────────────────────────────────
async def generate_image(
    product_name: str,
    style: str,
    platform: str,
    seed: int | None = None,
    n: int = 1,
    watermark: bool = True,
) -> dict:
    """
    Generate social media image(s) for a product using Hugging Face Inference API.

    Workflow:
      1. Groq LLM crafts an optimized image prompt
      2. Hugging Face FLUX model generates the image(s)
      3. Images are saved locally

    Args:
        product_name: Name of the product
        style:        Visual style (e.g., minimalist, vibrant, corporate)
        platform:     Target social media platform
        seed:         Optional seed for reproducible generation
        n:            Number of images to generate (1-4)
        watermark:    Whether to apply a watermark to the image

    Returns:
        dict with status, metadata, image URLs, and the generated prompt
    """
    platform_lower = platform.lower()
    dimensions = PLATFORM_SIZES.get(platform_lower, {"width": 1024, "height": 1024})

    # Step 1 — Generate an optimized image prompt via Groq
    logger.info("Generating image prompt for '%s' (%s / %s)", product_name, style, platform)
    image_prompt = await _generate_image_prompt(product_name, style, platform)
    logger.info("Prompt generated (%d chars)", len(image_prompt))

    # Step 2 — Generate image(s) via Hugging Face Inference API
    client = get_hf_client()
    count = min(n, 4)

    logger.info(
        "Calling Hugging Face (%s, %dx%d, n=%d)",
        DEFAULT_IMAGE_MODEL,
        dimensions["width"],
        dimensions["height"],
        count,
    )

    # HF text_to_image returns a PIL Image — generate `n` images sequentially
    saved_images: list[dict] = []
    for idx in range(count):
        # Build kwargs for text_to_image
        generate_kwargs: dict = {
            "width": dimensions["width"],
            "height": dimensions["height"],
        }
        if seed is not None:
            # Use seed + idx so each image in a batch is different but reproducible
            generate_kwargs["seed"] = seed + idx

        image = await asyncio.to_thread(
            client.text_to_image,
            prompt=image_prompt,
            model=DEFAULT_IMAGE_MODEL,
            **generate_kwargs,
        )

        # Apply watermark
        if watermark:
            image = _apply_watermark(image)

        # Save the PIL Image to disk
        slug = product_name.replace(" ", "_").lower()
        filename = f"{slug}_{platform_lower}_{uuid.uuid4().hex[:8]}.png"
        filepath = IMAGE_DIR / filename

        await asyncio.to_thread(image.save, str(filepath))
        saved_images.append({
            "index": idx,
            "filename": filename,
            "image_url": f"/images/{filename}",
        })
        logger.info("Saved image: %s", filename)

    return {
        "status": "success",
        "product_name": product_name,
        "style": style,
        "platform": platform,
        "dimensions": dimensions,
        "image_prompt": image_prompt,
        "images": saved_images,
        # Convenience: first image URL at top level for backward-compatibility
        "image_url": saved_images[0]["image_url"] if saved_images else None,
    }
