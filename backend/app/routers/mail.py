"""cfmail 直查（不绑定具体 submission）。"""

from __future__ import annotations

from fastapi import APIRouter

from .. import cfmail


router = APIRouter(prefix="/api/mail", tags=["mail"])


@router.get("/inbox")
def inbox(address: str, limit: int = 20) -> dict:
    return {"ok": True, "address": address, "mails": cfmail.get_mails(address, limit=limit)}


@router.get("/code")
def code(address: str) -> dict:
    return {"ok": True, "address": address, "code": cfmail.get_latest_code(address)}


@router.post("/send")
def send(to_addr: str, subject: str, text: str, from_addr: str | None = None) -> dict:
    try:
        return {"ok": True, "result": cfmail.send_mail(to_addr=to_addr, subject=subject, text=text, from_addr=from_addr)}
    except Exception as e:
        return {"ok": False, "error": str(e)}