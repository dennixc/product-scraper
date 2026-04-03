import logging
import re

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

MAX_HTML_CHARS = 100_000
DEFAULT_MODEL = "z-ai/glm-5"

TRANSLATE_PROMPT_ZH_TO_EN = """You are a professional translator. Translate the following HTML content from Traditional Chinese (繁體中文) to English.

CRITICAL RULES:
1. Preserve ALL HTML tags, attributes, inline styles, and structure exactly as-is.
2. Only translate the visible text content between HTML tags.
3. Do not add, remove, or reorder any HTML elements.
4. Do not translate content inside HTML attributes (class names, style values, href, src, etc.).
5. Maintain the same paragraph structure and formatting.

Output the translated HTML directly. Do not wrap in markdown code blocks. Do not add explanations.

---
{html}"""

TRANSLATE_PROMPT_EN_TO_ZH = """You are a professional translator. Translate the following HTML content from English to Traditional Chinese (繁體中文).

CRITICAL RULES:
1. Preserve ALL HTML tags, attributes, inline styles, and structure exactly as-is.
2. Only translate the visible text content between HTML tags.
3. Do not add, remove, or reorder any HTML elements.
4. Do not translate content inside HTML attributes (class names, style values, href, src, etc.).
5. Maintain the same paragraph structure and formatting.
6. IMPORTANT: Keep the following types of terms in their original English form — do NOT translate them:
   - Brand names (e.g., Google, Apple, Anthropic, ASUS, Samsung, Sony, Microsoft, Amazon, Dell, HP, Lenovo, LG, Panasonic, Canon, Nikon, Dyson, Bose, JBL, Razer, Logitech)
   - Product names (e.g., iPhone, MacBook, Galaxy, PlayStation, Surface, Pixel, AirPods, iPad, HomePod, Chromebook, ThinkPad, ROG, ZenBook)
   - Technical standards and interfaces (e.g., USB-C, USB 3.2, USB4, Wi-Fi, Wi-Fi 6E, Wi-Fi 7, Bluetooth, Bluetooth 5.3, HDMI, HDMI 2.1, NFC, Thunderbolt, DisplayPort, PCIe, DDR5, MagSafe, Lightning, Qi, Miracast)
   - Technical acronyms (e.g., AI, CPU, GPU, RAM, SSD, NVMe, OLED, AMOLED, HDR, HDR10+, ANC, EQ, RGB, LED, LCD, 5G, LTE, GPS, UWB, IoT, API, SDK)
   - Software/OS names (e.g., Windows, macOS, iOS, Android, Linux, Chrome OS, HarmonyOS, iPadOS, watchOS, tvOS)
   - Industry terms commonly kept in English in Traditional Chinese tech writing
   When in doubt, keep the English term.

Output the translated HTML directly. Do not wrap in markdown code blocks. Do not add explanations.

---
{html}"""


def _truncate_html(html: str) -> str:
    if len(html) <= MAX_HTML_CHARS:
        return html
    truncated = html[:MAX_HTML_CHARS]
    last_close = truncated.rfind('>')
    if last_close > MAX_HTML_CHARS * 0.8:
        truncated = truncated[:last_close + 1]
    return truncated


def _strip_code_block(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:html)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


async def translate_html(
    html: str,
    target_language: str,
    api_key: str,
    model: str | None = None,
) -> str:
    """Translate HTML content between Traditional Chinese and English.

    Returns original html on failure (graceful fallback).
    """
    if not html or not html.strip():
        return html

    try:
        if target_language == "en":
            prompt_text = TRANSLATE_PROMPT_ZH_TO_EN.format(html=_truncate_html(html))
        else:
            prompt_text = TRANSLATE_PROMPT_EN_TO_ZH.format(html=_truncate_html(html))

        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=90,
        )
        response = await client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt_text}],
        )
        translated = response.choices[0].message.content
        if translated:
            return _strip_code_block(translated)
        return html
    except Exception:
        logger.exception("Translation failed (target=%s)", target_language)
        return html
