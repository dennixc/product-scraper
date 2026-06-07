from fastapi import APIRouter, HTTPException, Query, Response

from app.models.schemas import Env, StoredBrandProfile
from app.services import brand_store

router = APIRouter(prefix="/api")


@router.get("/brands", response_model=list[StoredBrandProfile])
async def list_brands_endpoint(env: Env = Query("prod")):
    try:
        return await brand_store.list_brands(env=env)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"讀取品牌失敗：{e}")


@router.post("/brands", response_model=StoredBrandProfile)
async def upsert_brand_endpoint(profile: StoredBrandProfile, env: Env = Query("prod")):
    try:
        saved = await brand_store.upsert_brand(profile.model_dump(), env=env)
        return saved
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"儲存品牌失敗：{e}")


@router.delete("/brands/{brand_id}", status_code=204)
async def delete_brand_endpoint(brand_id: str, env: Env = Query("prod")):
    try:
        deleted = await brand_store.delete_brand(brand_id, env=env)
        if not deleted:
            detail = "品牌不存在" if env == "prod" else "品牌不存在於測試環境（正式品牌請切換到正式模式刪除）"
            raise HTTPException(status_code=404, detail=detail)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除品牌失敗：{e}")
