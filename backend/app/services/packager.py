import os
import json
import zipfile
from app.models.schemas import ProductResult

async def create_package(result: ProductResult, job_dir: str):
    """Create JSON result file and ZIP archive."""
    # Save JSON
    json_path = os.path.join(job_dir, "product.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)

    # Create ZIP (only product.json)
    zip_path = os.path.join(job_dir, "result.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(json_path, "product.json")
