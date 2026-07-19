"""组织搜索预览（前端下拉/搜索用）。"""

from __future__ import annotations

from fastapi import APIRouter

from .. import goodstack, db
from ..config import settings


router = APIRouter(prefix="/api/organisations", tags=["organisations"])


@router.get("/search")
def search(query: str = "", page: int = 1, page_size: int = 25) -> dict:
    data = goodstack.list_organisations(
        country_code=settings.default_country,
        query=query,
        page=page,
        page_size=page_size,
        require_registry_id=True,
    )
    # 标记哪些已用过
    items = data.get("data") or []
    for o in items:
        o["_used"] = db.is_org_used(o["id"])
    return data


@router.get("/countries")
def countries() -> dict:
    import httpx
    with httpx.Client(timeout=30) as client:
        r = client.get(
            settings.goodstack_base + "v1/countries",
            headers={
                "Authorization": settings.partner_public_key,
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )
        r.raise_for_status()
        return r.json()