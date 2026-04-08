"""
Prism AI — Translation Module

Translates generated text using the Groq LLM.
"""

import asyncio
import logging

from config import DEFAULT_LLM_MODEL, get_groq_client

logger = logging.getLogger("prism.translate")


async def translate_text(
    text: str,
    target_language: str,
    model: str = DEFAULT_LLM_MODEL,
) -> dict:
    """
    Translate text to the target language using Groq API.
    """

    prompt = f"""You are a professional translator. 
Please translate the following text into {target_language}.

CRITICAL INSTRUCTIONS:
1. Maintain the original format, tone, and structure.
2. DO NOT translate proper nouns, brand names (e.g., "Huda Beauty"), or specific product categories that are commonly used in English (e.g., "Foundation", "Concealer"). Keep them in English or transliterate them appropriately. Do NOT provide literal word-for-word translations like translating "Foundation" to a building base (e.g., "Adithalam" in Tamil).
3. Context matters: The text may contain cosmetics and beauty terminology. Ensure translations make sense in the context of makeup/beauty.

Only output the translated text and nothing else.

--- TEXT ---
{text}
--- END TEXT ---
"""

    logger.info("Translating text to '%s'", target_language)

    client = get_groq_client()
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert translator."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=4000,
    )

    translated_text = response.choices[0].message.content
    logger.info("Translation completed for '%s'", target_language)

    return {
        "status": "success",
        "target_language": target_language,
        "translated_text": translated_text,
    }
