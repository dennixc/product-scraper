import re
import json
from urllib.parse import urlparse
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
    r'IEEE 802\.11', r'WPA.*企業版',
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
    '[class*="cookie"]', '[class*="consent"]', '[class*="banner"]',
    '[class*="breadcrumb"]', '[class*="sidebar"]', '[class*="newsletter"]',
    '[class*="subscribe"]', '[class*="social"]', '[class*="share"]',
    '[class*="related"]', '[class*="recommend"]', '[class*="similar"]',
    '[class*="upsell"]', '[class*="cross-sell"]',
    '[id*="cookie"]', '[id*="consent"]', '[id*="breadcrumb"]',
    '[id*="sidebar"]', '[id*="newsletter"]',
    'script', 'style', 'noscript', 'iframe',
]


async def scrape_product(url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)

            # Scroll to trigger lazy loading of dynamic content
            for i in range(4):
                await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {(i+1)/4})")
                await page.wait_for_timeout(1000)

            html = await page.content()
        finally:
            await browser.close()

    soup = BeautifulSoup(html, 'lxml')

    product_name = _extract_product_name(soup)
    product_model = _extract_model(soup, product_name, url)
    summary = _extract_summary(soup)
    description = _extract_description(soup)
    description_html = _extract_description_html(soup)

    return {
        "product_name": product_name,
        "product_model": product_model,
        "summary": summary,
        "description": description,
        "description_html": description_html,
        "source_url": url,
    }


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
    """Extract detailed product description from common product detail sections."""
    description_parts = []

    desc_patterns = [
        'product-description', 'product-detail', 'product-info',
        'productDescription', 'productDetail', 'productInfo',
        'prod-desc', 'prod-detail', 'item-description', 'item-detail',
        'description', 'detail', 'spec', 'feature', 'overview',
        'product_description', 'product_detail', 'product_info',
    ]

    for pattern in desc_patterns:
        elements = soup.find_all(class_=re.compile(pattern, re.IGNORECASE))
        for el in elements:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 30 and text not in description_parts:
                description_parts.append(text)

        elements = soup.find_all(id=re.compile(pattern, re.IGNORECASE))
        for el in elements:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 30 and text not in description_parts:
                description_parts.append(text)

    if description_parts:
        return "\n\n".join(description_parts[:5])

    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) >= 50:
            paragraphs.append(text)

    return "\n\n".join(paragraphs[:10]) if paragraphs else ""


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


def _extract_description_html(soup: BeautifulSoup) -> str:
    """Extract clean HTML description suitable for Shopline product description."""
    # Work on a copy so we don't mutate the original
    from copy import copy
    work_soup = BeautifulSoup(str(soup), 'lxml')

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

    for el in main.find_all(['h2', 'h3', 'h4', 'p', 'ul', 'ol', 'table']):
        # Skip empty elements
        text = el.get_text(strip=True)
        if not text or len(text) < 5:
            continue

        # Normalize for dedup comparison
        norm = _normalize_text(text)
        if norm in seen_texts:
            continue
        seen_texts.add(norm)

        # Sentence-level dedup: split into sentences (>15 chars),
        # skip element if >50% of its sentences already appeared
        sentences = [s.strip() for s in re.split(r'[。！？\n]', norm) if len(s.strip()) > 15]
        if sentences:
            overlap = sum(1 for s in sentences if s in seen_texts)
            if overlap > len(sentences) * 0.5:
                continue
            for s in sentences:
                seen_texts.add(s)

        # Skip boilerplate / disclaimer content
        if BOILERPLATE_RE.search(text):
            continue

        # Skip short-text link lists (likely navigation)
        if el.name in ('ul', 'ol'):
            items = el.find_all('li')
            if items and all(len(li.get_text(strip=True)) < 30 for li in items):
                continue

        # Clean the element
        clean = BeautifulSoup(str(el), 'lxml')
        target = clean.find(el.name)
        if not target:
            continue

        # Strip all attributes from all tags
        for tag in target.find_all(True):
            if tag.name in ALLOWED_TAGS:
                tag.attrs = {}
            else:
                # Replace non-allowed tag with its contents
                tag.unwrap()

        # Get cleaned HTML string
        html_str = str(target)
        if html_str:
            content_parts.append(html_str)

    return "\n".join(content_parts)


