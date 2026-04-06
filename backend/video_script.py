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

    prompt = f"""You are an expert video script writer.

Create a highly engaging and structured video script based on the following product description provided by the user:

--- USER INPUT ---
{product_name}
--- END USER INPUT ---

The user input above may be a simple product name (e.g. "iPhone 16 Pro") or a detailed description with specific features, target audience, use cases, and other context. Use ALL the details provided to create a highly tailored and specific script. If only a product name is given, use your knowledge to create a compelling script about it.

CRITICAL INSTRUCTION ON TONE: Your writing MUST fully embrace the requested tone: {tone}. If the tone is humorous, it should be genuinely funny, witty, and conversationally entertaining. If the tone is professional, keep it formal. Under no circumstances should you default to a standard corporate tone unless explicitly requested.

Video Duration: {duration_mins} minutes

Follow this structure STRICTLY:

Hook (First 5-10 seconds):
<Powerful attention-grabbing opening about the product>

Introduction:
<Brief intro to the product and what the video will cover>

Main Content:
<Cover product features, benefits, and use cases>
<Incorporate any specific details the user provided>
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
            {"role": "system", "content": f"You are an expert script writer who specializes in creating highly engaging video content in a strictly {tone} tone."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.85,
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