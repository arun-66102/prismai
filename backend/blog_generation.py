"""
Prism AI — Blog Generation Module

Generates SEO-optimized blog articles using the Groq LLM.
"""

import asyncio
import logging

from config import DEFAULT_LLM_MODEL, get_groq_client

logger = logging.getLogger("prism.blog")


async def generate_blog(
    product_name: str,
    tone: str,
    word_count: int,
    model: str = DEFAULT_LLM_MODEL,
) -> dict:
    """
    Generate an SEO-optimized blog article for a product using Groq API.

    Args:
        product_name: Name of the product to write about
        tone:         Writing tone (e.g., Professional, Casual, Informative)
        word_count:   Approximate word count
        model:        LLM model identifier

    Returns:
        dict with status, metadata, and generated blog content
    """

    prompt = f"""You are a professional SEO blog writer.

Write a high-quality, engaging, and SEO-optimized blog article about the following product:

Product Name: {product_name}
Tone: {tone}
Word Count: Approximately {word_count} words

Follow this structure STRICTLY:

Title:
<SEO optimized title about the product>

Meta Description:
<150-160 characters meta description>

Introduction:
<Engaging hook-based introduction about the product>

Main Content:
<Use H2 and H3 headings properly>
<Cover product features, benefits, and use cases>
<Make content informative and structured>

Conclusion:
<Strong summary>

Call To Action:
<Encourage reader action clearly>"""

    logger.info("Generating blog for '%s' (tone=%s, ~%d words)", product_name, tone, word_count)

    client = get_groq_client()
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=model,
        messages=[
            {"role": "system", "content": "You are a professional content strategist."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2000,
    )

    generated_text = response.choices[0].message.content
    logger.info("Blog generated successfully for '%s'", product_name)

    return {
        "status": "success",
        "product_name": product_name,
        "tone": tone,
        "word_count": word_count,
        "generated_blog": generated_text,
    }
