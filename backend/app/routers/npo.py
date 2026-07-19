"""NPO 库管理：触发下载导入、查看统计、随机预览。"""

from __future__ import annotations

from fastapi import APIRouter

from .. import db, npodb


router = APIRouter(prefix="/api/npo", tags=["npo"])


@router.post("/refresh")
def refresh(idx_list: str = "0") -> dict:
    """触发下载并导入 NPO 全件数据。idx_list 用逗号分隔，默认 "0"（全国一括）。"""
    indexes = [int(x.strip()) for x in idx_list.split(",") if x.strip().isdigit()]
    if not indexes:
        indexes = [0]
    with db.get_conn() as conn:
        result = npodb.import_npos(conn, idx_list=indexes)
    return {"ok": True, **result, "stats": stats()}


@router.get("/stats")
def stats() -> dict:
    return {
        "total": db.count_npos(),
        "recognized": db.count_npos(recognized_only=True),
        "unused": db.count_unused_npos(),
        "unused_recognized": db.count_unused_npos(recognized_only=True),
    }


@router.get("/preview")
def preview(limit: int = 10, only_unused: bool = True, recognized_only: bool = False) -> dict:
    sql = "SELECT * FROM jp_npos"
    where = []
    if only_unused:
        where.append("used_at IS NULL")
    if recognized_only:
        where.append("is_recognized=1")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY random() LIMIT ?"
    with db.get_conn() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return {"count": len(rows), "data": [dict(r) for r in rows]}