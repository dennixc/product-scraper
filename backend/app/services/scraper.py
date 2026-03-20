import copy
import gc
import re
import json
import time
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup, Tag, NavigableString

# Model number pattern: must contain both letters and digits
MODEL_PATTERN = re.compile(r'(?<![/\w])[A-Z]{1,6}[-\s]?[A-Z0-9]*\d[A-Z0-9]*(?:[-\s][A-Z0-9]+)*(?![/\w])')

# Tags allowed in cleaned description HTML
ALLOWED_TAGS = {
    'h2', 'h3', 'h4', 'p', 'ul', 'ol', 'li',
    'strong', 'em', 'b', 'i', 'br',
    'table', 'thead', 'tbody', 'tr', 'td', 'th',
}

# Boilerplate / disclaimer patterns — if element text matches any, skip it
BOILERPLATE_PATTERNS = [
    # 法律 / 免責聲明
    r'FCC', r'認證', r'恕不另行通知', r'如有更改',
    r'商標聲明', r'註冊商標', r'版權',
    r'僅供參考', r'僅做識別之用',
    r'All rights reserved', r'subject to change',
    # 技術 disclaimer
    r'實際傳輸速度', r'實際數據傳輸', r'實際效能',
    r'WiFi 覆蓋範圍', r'無線覆蓋範圍',
    r'WPA.*企業版',
    r'USB 外接硬碟', r'電源供應',
    r'第三方服務', r'第三方供應商',
    # Footer 推廣
    r'免運', r'客服即時通', r'售後服務', r'鑑賞期',
    r'SSL.*加密', r'安心.*付款',
    # 網站導航 / 企業資訊
    r'投資人關係', r'企業社會責任', r'新聞中心',
    r'徵才', r'Careers', r'官方公告',
    r'維修進度', r'找尋服務據點', r'產品註冊',
    r'舊機回收',
]
BOILERPLATE_RE = re.compile('|'.join(BOILERPLATE_PATTERNS), re.IGNORECASE)


def _normalize_text(text: str) -> str:
    """Normalize all whitespace (including \\xa0, \\u200b) to single spaces for dedup."""
    return re.sub(r'\s+', ' ', text).strip()

# Sections to remove before extracting content
REMOVE_SELECTORS = [
    'header', 'footer', 'nav',
    '[class*="cookie"]', '[class*="consent"]',
    '[class*="breadcrumb"]', '[class*="sidebar"]', '[class*="newsletter"]',
    '[class*="subscribe"]', '[class*="social"]', '[class*="share"]',
    '[class*="upsell"]', '[class*="cross-sell"]',
    '[id*="cookie"]', '[id*="consent"]', '[id*="breadcrumb"]',
    '[id*="sidebar"]', '[id*="newsletter"]',
    'script', 'style', 'noscript', 'iframe',
]


_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def detect_spa_heuristic(html: str) -> bool:
    """Original SPA detection heuristic — used as fallback when AI analysis fails."""
    return '__NUXT__' in html or '__NEXT_DATA__' in html


async def fetch_with_httpx(url: str) -> str | None:
    """Lightweight HTTP fetch — no browser needed (~200MB peak)."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception:
        return None


async def fetch_with_playwright(url: str) -> str:
    """Full browser fetch for SPA sites (~450-500MB peak)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--no-first-run',
                '--single-process',
                '--js-flags=--max-old-space-size=256',
            ]
        )
        page = await browser.new_page(user_agent=_USER_AGENT)

        try:
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
            except Exception:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2000)

            # Scroll incrementally to trigger lazy-loaded content
            scroll_start = time.monotonic()
            max_scrolls = 20
            max_seconds = 15
            prev_height = await page.evaluate("document.body.scrollHeight")
            viewport_h = await page.evaluate("window.innerHeight")
            scroll_pos = 0

            for _ in range(max_scrolls):
                if time.monotonic() - scroll_start > max_seconds:
                    break
                scroll_pos += viewport_h
                await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                await page.wait_for_timeout(600)

                new_height = await page.evaluate("document.body.scrollHeight")
                if scroll_pos >= new_height and new_height == prev_height:
                    break
                prev_height = new_height

            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)

            html = await page.content()
        finally:
            await browser.close()

    gc.collect()
    return html


def extract_all(soup: BeautifulSoup, url: str) -> dict:
    """Extract all product data from parsed HTML."""
    product_name = _extract_product_name(soup)
    product_model = _extract_model(soup, product_name, url)
    summary = _extract_summary(soup)
    description = _extract_description(soup)
    # _extract_description_html mutates soup — must be called last
    description_html = _extract_description_html(soup)

    return {
        "product_name": product_name,
        "product_model": product_model,
        "summary": summary,
        "description": description,
        "description_html": description_html,
        "source_url": url,
    }


def _is_content_sufficient(data: dict) -> bool:
    """Check if extracted data has enough content to skip Playwright."""
    if data.get("product_name", "Unknown Product") == "Unknown Product":
        return False
    desc_html = data.get("description_html", "")
    desc = data.get("description", "")
    # Strip HTML tags — 量度實際文字內容，唔係 markup
    plain_from_html = re.sub(r'<[^>]+>', ' ', desc_html)
    plain_from_html = re.sub(r'\s+', ' ', plain_from_html).strip()
    return len(plain_from_html) >= 300 or len(desc) >= 200


async def scrape_product(url: str) -> dict:
    # Phase 1: Try lightweight httpx fetch first (~200MB peak)
    html = await fetch_with_httpx(url)
    if html:
        # SPA frameworks: SSR content often incomplete, needs JS rendering
        is_spa = detect_spa_heuristic(html)
        if not is_spa:
            soup = BeautifulSoup(html, 'lxml')
            data = extract_all(soup, url)
            if _is_content_sufficient(data):
                data["_raw_html"] = html
                del soup
                return data
            del data, soup, html
            gc.collect()
        else:
            del html
            gc.collect()

    # Phase 2: Fallback to Playwright for SPA sites / insufficient content
    html = await fetch_with_playwright(url)
    soup = BeautifulSoup(html, 'lxml')
    data = extract_all(soup, url)
    data["_raw_html"] = html
    del soup, html
    return data


def _extract_product_name(soup: BeautifulSoup) -> str:
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)

    title = soup.find("title")
    if title:
        return title.get_text(strip=True)

    return "Unknown Product"


def _extract_model(soup: BeautifulSoup, product_name: str, url: str) -> str:
    """Extract product model/SKU from multiple sources, prioritizing structured data."""

    # 1. JSON-LD structured data
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                for key in ("sku", "mpn", "model", "productID"):
                    val = item.get(key)
                    if val and isinstance(val, str) and len(val) >= 3:
                        return val.strip()
                offers = item.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if isinstance(offers, dict):
                    val = offers.get("sku")
                    if val and isinstance(val, str) and len(val) >= 3:
                        return val.strip()
        except (json.JSONDecodeError, TypeError, IndexError):
            continue

    # 2. Page elements with SKU/model class or id
    sku_class_patterns = [
        'sku', 'model-number', 'model_number', 'modelNumber',
        'product-model', 'mpn', 'part-number', 'partNumber',
    ]
    for pattern in sku_class_patterns:
        for el in soup.find_all(class_=re.compile(pattern, re.IGNORECASE)):
            text = el.get_text(strip=True)
            text = re.sub(r'^(SKU|Model|Part\s*(No\.?|Number)|MPN)\s*[:：]\s*', '', text, flags=re.IGNORECASE)
            if text and 3 <= len(text) <= 30:
                return text.strip()
        el = soup.find(id=re.compile(pattern, re.IGNORECASE))
        if el:
            text = el.get_text(strip=True)
            text = re.sub(r'^(SKU|Model|Part\s*(No\.?|Number)|MPN)\s*[:：]\s*', '', text, flags=re.IGNORECASE)
            if text and 3 <= len(text) <= 30:
                return text.strip()

    # 3. URL path (e.g., /BPD008btWH.html, /rt-be58u/)
    path = urlparse(url).path
    segments = [s for s in path.rstrip('/').split('/') if s]
    if segments:
        last_seg = segments[-1]
        last_seg = re.sub(r'\.(html?|php|aspx?)$', '', last_seg, flags=re.IGNORECASE)
        if re.search(r'[A-Za-z]', last_seg) and re.search(r'\d', last_seg):
            return last_seg.upper().strip()

    # 4. Product name regex (must contain digit to avoid brand words)
    match = MODEL_PATTERN.search(product_name)
    if match:
        candidate = match.group(0).strip()
        if re.search(r'\d', candidate):
            return candidate

    # 5. Broad meta tag search
    for meta in soup.find_all("meta"):
        content = meta.get("content", "")
        if content:
            match = MODEL_PATTERN.search(content)
            if match and len(match.group(0)) >= 4:
                candidate = match.group(0).strip()
                if re.search(r'\d', candidate):
                    return candidate

    return "product"


def _extract_summary(soup: BeautifulSoup) -> str:
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        return og_desc["content"].strip()

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        return meta_desc["content"].strip()

    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) >= 50:
            return text[:500]

    return ""


def _extract_description(soup: BeautifulSoup) -> str:
    """Extract detailed product description from multiple sources."""
    description_parts = []
    seen_texts = set()

    def _add_text(text: str) -> bool:
        norm = _normalize_text(text)
        if norm in seen_texts or len(norm) < 30:
            return False
        seen_texts.add(norm)
        description_parts.append(text)
        return True

    # Source 1: JSON-LD Product.description
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") in ("Product", "IndividualProduct"):
                    desc = item.get("description", "")
                    if desc and len(desc) > 30:
                        _add_text(desc)
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    # Source 2: Class/id pattern matching (existing logic)
    desc_patterns = [
        'product-description', 'product-detail', 'product-info',
        'productDescription', 'productDetail', 'productInfo',
        'prod-desc', 'prod-detail', 'item-description', 'item-detail',
        'description', 'detail', 'spec', 'feature', 'overview',
        'product_description', 'product_detail', 'product_info',
    ]

    for pattern in desc_patterns:
        for el in soup.find_all(class_=re.compile(pattern, re.IGNORECASE)):
            text = el.get_text(separator="\n", strip=True)
            _add_text(text)

        for el in soup.find_all(id=re.compile(pattern, re.IGNORECASE)):
            text = el.get_text(separator="\n", strip=True)
            _add_text(text)

    if description_parts:
        return "\n\n".join(description_parts[:5])

    # Source 3: Paragraphs
    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) >= 50 and _normalize_text(text) not in seen_texts:
            paragraphs.append(text)

    if paragraphs:
        return "\n\n".join(paragraphs[:10])

    # Source 4: Leaf div/section text (fallback for SPA sites)
    main = soup.find('main') or soup.find('article') or soup.find('body') or soup
    leaf_texts = []
    for el in main.find_all(['div', 'section', 'span']):
        if el.find(_BLOCK_TAGS):
            continue
        text = el.get_text(strip=True)
        if len(text) >= 40 and not BOILERPLATE_RE.search(text):
            norm = _normalize_text(text)
            if norm not in seen_texts:
                seen_texts.add(norm)
                leaf_texts.append(text)

    return "\n\n".join(leaf_texts[:10]) if leaf_texts else ""


def _clean_tag(tag: Tag) -> Tag | None:
    """Recursively clean a tag, keeping only allowed tags and stripping attributes."""
    if tag.name not in ALLOWED_TAGS:
        # For non-allowed tags, promote children
        return None

    # Strip all attributes
    tag.attrs = {}

    # Process children
    for child in list(tag.children):
        if isinstance(child, NavigableString):
            continue
        if isinstance(child, Tag):
            if child.name in ALLOWED_TAGS:
                _clean_tag(child)
            else:
                # Replace non-allowed tag with its children
                for grandchild in list(child.children):
                    child.insert_before(grandchild)
                child.decompose()

    return tag


# Block-level tags used to identify "leaf" containers in Phase 2
_BLOCK_TAGS = {'div', 'section', 'article', 'aside', 'main', 'header', 'footer', 'nav',
               'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'table', 'blockquote',
               'figure', 'figcaption', 'details', 'summary', 'form', 'fieldset', 'pre'}


def _maybe_add_element(
    el: Tag,
    seen_texts: set[str],
    content_parts: list[str],
    min_length: int = 5,
) -> bool:
    """Try to add an element's cleaned HTML to content_parts.

    Returns True if the element was added, False if skipped.
    Handles dedup, boilerplate filtering, nav-list filtering, and HTML cleaning.
    """
    text = el.get_text(strip=True)
    if not text or len(text) < min_length:
        return False

    # Normalize for dedup
    norm = _normalize_text(text)
    if norm in seen_texts:
        return False

    # Sentence-level dedup: skip if >50% of sentences already seen
    # Split on Chinese sentence markers, English sentence boundaries, and newlines
    sentences = [s.strip() for s in re.split(r'[。！？!?\n]|(?<=\w)\.\s', norm) if len(s.strip()) > 15]
    if sentences:
        overlap = sum(1 for s in sentences if s in seen_texts)
        if overlap > len(sentences) * 0.5:
            seen_texts.add(norm)
            return False
        for s in sentences:
            seen_texts.add(s)

    seen_texts.add(norm)

    # Skip boilerplate / disclaimer content
    if BOILERPLATE_RE.search(text):
        return False

    # Skip ul/ol that are structural containers (contain headings, not a simple list)
    if el.name in ('ul', 'ol'):
        if el.find(['h2', 'h3', 'h4']):
            return False
        # Skip short-text link lists (likely navigation)
        items = el.find_all('li')
        if items and all(len(li.get_text(strip=True)) < 30 for li in items):
            return False

    # Clean the element — keep only allowed tags, strip attributes
    el_copy = copy.deepcopy(el)
    el_copy.attrs = {}  # Strip root element attributes
    for tag in el_copy.find_all(True):
        if tag.name in ALLOWED_TAGS:
            tag.attrs = {}
        else:
            tag.unwrap()

    html_str = str(el_copy)
    if html_str:
        content_parts.append(html_str)
        return True
    return False


def _extract_description_html(soup: BeautifulSoup) -> str:
    """Extract clean HTML description suitable for Shopline product description.

    NOTE: This function mutates soup. It MUST be called last in scrape_product().
    """
    work_soup = soup

    # Remove non-content elements
    for selector in REMOVE_SELECTORS:
        for el in work_soup.select(selector):
            el.decompose()

    # Find main content area
    main = work_soup.find('main')
    if not main:
        # Try article
        main = work_soup.find('article')
    if not main:
        # Try largest content div
        main = work_soup.find('body') or work_soup

    # Collect content elements
    content_parts = []
    seen_texts = set()

    # Phase 1: Standard semantic elements (h2-h4, p, ul, ol, table)
    for el in main.find_all(['h2', 'h3', 'h4', 'p', 'ul', 'ol', 'table']):
        _maybe_add_element(el, seen_texts, content_parts)

    # Phase 2: Leaf containers — div/section/span with text but no block-level children
    # This captures SPA content rendered inside Vue/React components
    for el in main.find_all(['div', 'section', 'span']):
        # Skip if it contains block-level children (not a "leaf")
        if el.find(_BLOCK_TAGS):
            continue
        _maybe_add_element(el, seen_texts, content_parts, min_length=40)

    return "\n".join(content_parts)


