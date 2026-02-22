import re
import json
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup, Tag

# Patterns to filter out non-product images by URL
EXCLUDE_URL_PATTERNS = [
    r'icon', r'logo', r'banner', r'sprite', r'social',
    r'facebook', r'twitter', r'instagram', r'youtube', r'pinterest',
    r'tracking', r'pixel', r'analytics', r'badge', r'flag',
    r'arrow', r'btn', r'button', r'cart', r'search',
    r'placeholder', r'spacer', r'divider', r'bg[-_]',
    r'avatar', r'favicon', r'1x1', r'blank\.gif',
    r'rating', r'star[-_]', r'review',
    r'payment', r'visa', r'mastercard', r'paypal',
    r'shipping', r'delivery', r'warranty',
    r'\.svg$',
]
EXCLUDE_URL_RE = re.compile('|'.join(EXCLUDE_URL_PATTERNS), re.IGNORECASE)

# Parent sections that should be excluded (images in these are not product images)
EXCLUDE_ANCESTOR_PATTERNS = [
    r'gnav', r'global[-_]?nav', r'mega[-_]?menu',
    r'related', r'recommend', r'also[-_\s]?like', r'you[-_\s]?may',
    r'similar', r'upsell', r'cross[-_\s]?sell', r'recently[-_\s]?viewed',
    r'footer', r'site[-_]?footer', r'global[-_]?footer',
    r'nav[-_]?bar', r'nav[-_]?menu', r'main[-_]?nav', r'site[-_]?nav',
    r'header(?!.*image)', r'site[-_]?header',
    r'sidebar', r'newsletter', r'subscribe', r'signup',
    r'compare', r'accessori', r'compatible',
    r'cookie', r'consent', r'popup', r'modal(?!.*image)',
    r'breadcrumb',
]
EXCLUDE_ANCESTOR_RE = re.compile('|'.join(EXCLUDE_ANCESTOR_PATTERNS), re.IGNORECASE)

# Product image container class/id patterns (prioritized search)
PRODUCT_IMAGE_PATTERNS = [
    r'pdp[-_]?image', r'product[-_]?image', r'product[-_]?gallery',
    r'product[-_]?photo', r'product[-_]?media',
    r'primary[-_]?image', r'main[-_]?image', r'hero[-_]?image',
    r'gallery[-_]?image', r'gallery[-_]?container',
    r'carousel', r'slider', r'slick',
    r'zoom[-_]?container', r'image[-_]?viewer',
]
PRODUCT_IMAGE_RE = re.compile('|'.join(PRODUCT_IMAGE_PATTERNS), re.IGNORECASE)

# Model number pattern: must contain both letters and digits
MODEL_PATTERN = re.compile(r'(?<![/\w])[A-Z]{1,6}[-\s]?[A-Z0-9]*\d[A-Z0-9]*(?:[-\s][A-Z0-9]+)*(?![/\w])')

MAX_IMAGES = 50


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

            # Scroll to trigger lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await page.wait_for_timeout(1000)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

            html = await page.content()
        finally:
            await browser.close()

    soup = BeautifulSoup(html, 'lxml')

    product_name = _extract_product_name(soup)
    product_model = _extract_model(soup, product_name, url)
    summary = _extract_summary(soup)
    description = _extract_description(soup)
    image_urls = _extract_images(soup, url)

    return {
        "product_name": product_name,
        "product_model": product_model,
        "summary": summary,
        "description": description,
        "image_urls": image_urls,
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


def _is_in_excluded_ancestor(tag: Tag) -> bool:
    """Check if a tag is nested inside a non-product section."""
    for parent in tag.parents:
        if not isinstance(parent, Tag):
            continue
        # Skip body/html - they often have state classes like modal-open, is-sticky
        if parent.name in ("body", "html", "[document]"):
            continue
        classes = " ".join(parent.get("class", []))
        el_id = parent.get("id", "") or ""
        combined = f"{classes} {el_id}"
        if combined.strip() and EXCLUDE_ANCESTOR_RE.search(combined):
            return True
    return False


def _collect_img_src(img: Tag) -> str | None:
    """Get the best image source from an img tag."""
    src = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
    if not src or src.startswith("data:"):
        return None
    return src


def _passes_basic_filters(img: Tag, src: str) -> bool:
    """Check if an image passes basic size and URL pattern filters."""
    # Check dimensions from attributes
    width = img.get("width", "")
    height = img.get("height", "")
    try:
        if width and int(width) < 200:
            return False
        if height and int(height) < 200:
            return False
    except (ValueError, TypeError):
        pass

    # Check URL patterns
    if EXCLUDE_URL_RE.search(src):
        return False

    return True


def _extract_images(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Extract product image URLs using a two-pass strategy."""
    seen = set()
    image_urls = []

    def _add_url(src: str) -> bool:
        """Add URL if not seen. Returns True if added."""
        if len(image_urls) >= MAX_IMAGES:
            return False
        abs_url = urljoin(base_url, src)
        parsed = urlparse(abs_url)
        dedup_key = parsed.scheme + "://" + parsed.netloc + parsed.path
        if dedup_key in seen:
            return False
        seen.add(dedup_key)
        image_urls.append(abs_url)
        return True

    # Priority 0: og:image
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        _add_url(og_image["content"])

    # Priority 1: Images inside product-specific containers
    for container in soup.find_all(class_=PRODUCT_IMAGE_RE):
        # Skip if the container itself is inside an excluded section
        if _is_in_excluded_ancestor(container):
            continue
        for img in container.find_all("img"):
            src = _collect_img_src(img)
            if src and _passes_basic_filters(img, src):
                _add_url(src)

    # Priority 2: If we found very few images from containers, scan entire page
    if len(image_urls) < 5:
        for img in soup.find_all("img"):
            if len(image_urls) >= MAX_IMAGES:
                break
            src = _collect_img_src(img)
            if not src:
                continue
            if not _passes_basic_filters(img, src):
                continue
            if _is_in_excluded_ancestor(img):
                continue
            _add_url(src)

    return image_urls
