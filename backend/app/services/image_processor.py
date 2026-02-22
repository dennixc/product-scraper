import os
import httpx
from io import BytesIO
from PIL import Image
from app.models.schemas import ProductResult

async def process_images(raw_data: dict, job_dir: str, model: str) -> ProductResult:
    """Download, classify, process, and save all product images."""
    images_dir = os.path.join(job_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    image_urls = raw_data.get("image_urls", [])
    main_images = []
    gallery_images = []
    counter = 1

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for url in image_urls:
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    continue

                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    continue

                img = Image.open(BytesIO(response.content))

                # Skip very small images
                if img.width < 200 or img.height < 200:
                    continue

                # Convert to RGB (in case of RGBA/P mode)
                if img.mode != "RGB":
                    img = img.convert("RGB")

                filename = f"{_sanitize_model(model)}_{counter:02d}.jpg"

                if is_white_background(img):
                    # Main image: crop to square, resize to 800x800
                    processed = crop_to_square(img)
                    processed = processed.resize((800, 800), Image.LANCZOS)
                    processed.save(os.path.join(images_dir, filename), "JPEG", quality=90)
                    main_images.append(filename)
                else:
                    # Gallery image: resize width to 1280, maintain aspect ratio
                    processed = resize_to_width(img, 1280)
                    processed.save(os.path.join(images_dir, filename), "JPEG", quality=90)
                    gallery_images.append(filename)

                counter += 1
            except Exception:
                continue

    return ProductResult(
        product_name=raw_data.get("product_name", "Unknown"),
        product_model=model,
        main_images=main_images,
        gallery_images=gallery_images,
        summary=raw_data.get("summary", ""),
        description=raw_data.get("description", ""),
        source_url=raw_data.get("source_url", ""),
    )

def is_white_background(image: Image.Image) -> bool:
    """Sample edge pixels to determine if image has white/gray background."""
    pixels = []
    w, h = image.size

    if w < 3 or h < 3:
        return False

    # Sample 20 pixels from each edge
    for i in range(20):
        x = int(w * i / 19)
        y = int(h * i / 19)
        # Clamp coordinates
        x = min(x, w - 1)
        y = min(y, h - 1)
        pixels.extend([
            image.getpixel((x, 0)),          # top edge
            image.getpixel((x, h - 1)),      # bottom edge
            image.getpixel((0, y)),           # left edge
            image.getpixel((w - 1, y)),       # right edge
        ])

    white_count = sum(
        1 for p in pixels
        if all(c > 200 for c in p[:3]) and (max(p[:3]) - min(p[:3])) < 30
    )
    return white_count / len(pixels) > 0.75

def crop_to_square(img: Image.Image) -> Image.Image:
    """Center-crop image to a square."""
    w, h = img.size
    size = min(w, h)
    left = (w - size) // 2
    top = (h - size) // 2
    return img.crop((left, top, left + size, top + size))

def resize_to_width(img: Image.Image, target_width: int) -> Image.Image:
    """Resize image to target width, maintaining aspect ratio."""
    w, h = img.size
    if w <= target_width:
        return img
    ratio = target_width / w
    new_height = int(h * ratio)
    return img.resize((target_width, new_height), Image.LANCZOS)

def _sanitize_model(model: str) -> str:
    """Sanitize model name for use in filenames."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in model)
