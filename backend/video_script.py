"""
Prism AI — Video Script Generation Module

Generates structured video scripts using the Groq LLM.
"""

import asyncio
import logging

from config import DEFAULT_LLM_MODEL, get_groq_client

logger = logging.getLogger("prism.video")


async def generate_video_script(
    product_name: str,
    tone: str,
    duration_mins: int,
    model: str = DEFAULT_LLM_MODEL,
) -> dict:
    """
    Generate a video script for a product using Groq API.

    Args:
        product_name: Name of the product
        tone:         Writing tone (e.g., Professional, Casual, Energetic)
        duration_mins: Video duration in minutes
        model:        LLM model identifier

    Returns:
        dict with status, metadata, and generated script
    """

    prompt = f"""You are a professional video script writer and content strategist.

Create a highly engaging and structured video script for the following product:

Product Name: {product_name}
Tone: {tone}
Video Duration: {duration_mins} minutes

Follow this structure STRICTLY:

Hook (First 5-10 seconds):
<Powerful attention-grabbing opening about the product>

Introduction:
<Brief intro to the product and what the video will cover>

Main Content:
<Cover product features, benefits, and use cases>
<Use storytelling or real-world examples>
<Keep pacing appropriate for {duration_mins} minute video>

Engagement Prompt:
<Ask viewers to comment, like, and share>

Call To Action:
<Clear CTA — try the product, visit the website, etc.>

Outro:
<Strong memorable closing line>

Important: Make sure the script feels natural when spoken aloud and fits within a {duration_mins}-minute video."""

    logger.info("Generating video script for '%s' (tone=%s, %d min)", product_name, tone, duration_mins)

    client = get_groq_client()
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=model,
        messages=[
            {"role": "system", "content": "You are a professional video script creator."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2000,
    )

    generated_script = response.choices[0].message.content
    logger.info("Video script generated successfully for '%s'", product_name)

    return {
        "status": "success",
        "product_name": product_name,
        "tone": tone,
        "duration_mins": duration_mins,
        "generated_script": generated_script,
    }