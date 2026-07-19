"""核心：从日本 NPO 库抽出一个未用过且有法人番号的 NPO，按法人番号在
Goodstack 上查到对应 organisationId，提交一次 validation claim。"""

from __future__ import annotations

import random
import time
from typing import Any

from fastapi import APIRouter, HTTPException

from .. import cfmail, confirm, db, goodstack, namegen, npodb
from ..config import settings


router = APIRouter(prefix="/api/claim", tags=["claim"])


def _pick_unused_npo() -> dict[str, Any]:
    """从本地 jp_npos 库抽一个未用过的（默认要求認定 NPO，否则放宽到全部）。"""
    npo = db.pick_unused_npo(recognized_only=True, mark_used=True)
    if npo:
        return npo
    npo = db.pick_unused_npo(recognized_only=False, mark_used=True)
    if not npo:
        raise RuntimeError("NPO 库为空或已用完，请先调用 /api/npo/refresh 导入 NPO 数据")
    return npo


def _pick_random_email_domain() -> str:
    return random.choice(settings.cfmail_org_domains)


@router.post("/one")
def submit_one() -> dict[str, Any]:
    """抽取一次 NPO + 邮箱并提交。"""
    if db.count_unused_npos() == 0:
        raise HTTPException(status_code=400, detail="NPO 库为空，请先 /api/npo/refresh")

    invite = goodstack.fetch_invite()
    npo = _pick_unused_npo()
    corp_num = npo["corporate_number"]

    # 用 13 位法人番号在 Goodstack 上查到对应组织
    org = goodstack.find_org_by_corporate_number(corp_num)
    goodstack_registry_id = (org or {}).get("registryId", corp_num)
    website = (org or {}).get("website") or npo.get("info_url") or ""

    # 生成联系邮箱：cfmail org 域名 + 随机人名前缀
    domain = _pick_random_email_domain()
    email = namegen.random_email(domain)
    for _ in range(8):
        if goodstack.validate_email(email):
            break
        domain = _pick_random_email_domain()
        email = namegen.random_email(domain)

    if not org:
        # Goodstack 未收录该法人番号 → 回收 NPO 标记并报错
        db.release_npo(corp_num)
        raise HTTPException(
            status_code=409,
            detail=f"Goodstack 未匹配法人番号 {corp_num}（已回收 {npo['name']}）",
        )

    result = goodstack.create_validation_submission(
        invite_id=invite.invite_id,
        organisation_id=org["id"],
        first_name=settings.contact_first_name,
        last_name=settings.contact_last_name,
        email=email,
        language=settings.contact_language,
        website=website or None,
    )

    status = "submitted" if result.ok else "error"
    row_id = db.insert_submission(
        invite_id=invite.invite_id,
        corporate_number=corp_num,
        organisation_name=org.get("name") or npo.get("name") or "",
        country_code=settings.default_country,
        website=website or None,
        contact_first_name=settings.contact_first_name,
        contact_last_name=settings.contact_last_name,
        email=email,
        language=settings.contact_language,
        status=status,
        submission_id=(result.payload or {}).get("id") or (result.payload or {}).get("data", {}).get("id"),
        raw_response=result.raw,
        note=None if result.ok else f"http={result.status_code}",
    )

    # 失败时不回收 used_at，避免同一 NPO 再被抽取（保留诊断信息）

    return {
        "ok": result.ok,
        "id": row_id,
        "invite_id": invite.invite_id,
        "organisation": {
            "id": org.get("id"),
            "name": org.get("name") or npo.get("name"),
            "registryId": goodstack_registry_id,
            "corporateNumber": corp_num,
            "website": website or None,
            "isRecognizedNPO": npo.get("is_recognized") == 1,
        },
        "country": settings.default_country,
        "contact": {
            "firstName": settings.contact_first_name,
            "lastName": settings.contact_last_name,
            "email": email,
        },
        "submission_id": (result.payload or {}).get("id"),
        "status": status,
        "response": result.payload,
        "npo_remaining": db.count_unused_npos(),
    }


@router.post("/batch")
def submit_batch(count: int = 1) -> dict[str, Any]:
    count = max(1, min(20, count))
    results = []
    errors = []
    for i in range(count):
        try:
            results.append(submit_one())
        except HTTPException as e:
            errors.append({"index": i, "status": e.status_code, "error": e.detail})
        except Exception as e:
            errors.append({"index": i, "error": str(e)})
        time.sleep(random.uniform(1.5, 3.5))
    return {"ok": len(errors) == 0, "count": len(results), "results": results, "errors": errors}


@router.get("/history")
def history(limit: int = 50) -> dict[str, Any]:
    rows = db.list_submissions(limit=limit)
    return {"count": len(rows), "data": rows}


@router.get("/{row_id}/mails")
def fetch_mails(row_id: int, limit: int = 20) -> dict[str, Any]:
    row = db.get_submission(row_id)
    if not row:
        return {"ok": False, "error": "not found"}
    mails = cfmail.get_mails(row["email"], limit=limit)
    return {"ok": True, "email": row["email"], "mails": mails}


@router.get("/{row_id}/code")
def fetch_code(row_id: int) -> dict[str, Any]:
    row = db.get_submission(row_id)
    if not row:
        return {"ok": False, "error": "not found"}
    code = cfmail.get_latest_code(row["email"])
    return {"ok": True, "email": row["email"], "code": code}


@router.post("/{row_id}/update")
def update_status(row_id: int, status: str = "pending", note: str | None = None) -> dict[str, Any]:
    db.update_status(row_id, status, note)
    return {"ok": True, "id": row_id, "status": status}


@router.get("/stats")
def stats() -> dict[str, Any]:
    return {
        "npos_total": db.count_npos(),
        "npos_recognized": db.count_npos(recognized_only=True),
        "npos_unused": db.count_unused_npos(),
        "npos_unused_recognized": db.count_unused_npos(recognized_only=True),
        "submissions": len(db.list_submissions(limit=10000)),
    }


def _confirm_one_row(row: dict[str, Any]) -> dict[str, Any]:
    """对单条历史记录：找最新确认邮件 → 若与已点的 mail_id 不同则点链接。
    二次验证场景下，Goodstack 会发新的验证邮件，这里靠 confirm_mail_id 比对识别。"""
    result = confirm.confirm_email(row["email"])
    result["id"] = row["id"]
    result["prev_mail_id"] = row.get("confirm_mail_id")
    # 已点过同一封验证邮件 → 视为已确认，跳过点击}
    if result.get("mail_id") and result["mail_id"] == row.get("confirm_mail_id"):
        result["ok"] = True
        result["reason"] = "already_confirmed_same_mail"
        result["click"] = result.get("click") or {"ok": True, "status_code": None, "final_url": ""}
        return result
    if result.get("ok"):
        db.mark_confirmed_with_mail(
            row["id"], result.get("mail_id"),
            note=(result.get("click") or {}).get("final_url")
        )
    return result


@router.post("/confirm-all")
def confirm_all() -> dict[str, Any]:
    """一键确认：遍历全部已提交历史（含已确认）。

    - 未确认过：找验证邮件并点击；
    - 已点击同一封验证邮件 → 跳过；
    - 已确认但收件箱出现新的验证邮件（二次验证）→ 重新点击新的链接。
    """
    rows = db.list_submitted()
    results = []
    done = 0
    no_mail = 0
    failed = 0
    skipped = 0
    for row in rows:
        try:
            r = _confirm_one_row(row)
        except Exception as exc:
            r = {"ok": False, "id": row["id"], "email": row["email"], "error": str(exc)}
        results.append(r)
        if r.get("reason") == "already_confirmed_same_mail":
            skipped += 1
            done += 1
        elif r.get("ok"):
            done += 1
        elif r.get("reason") == "no_verify_mail":
            no_mail += 1
        else:
            failed += 1
        time.sleep(random.uniform(0.8, 2.0))
    return {
        "ok": True,
        "total": len(rows),
        "confirmed": done,
        "skipped_same_mail": skipped,
        "no_verify_mail": no_mail,
        "failed": failed,
        "results": results,
    }


@router.post("/{row_id}/confirm")
def confirm_one(row_id: int) -> dict[str, Any]:
    """确认单条历史记录的邮箱。"""
    row = db.get_submission(row_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return _confirm_one_row(row)
