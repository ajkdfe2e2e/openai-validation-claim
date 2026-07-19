"""Goodstack 确认邮件处理：从收件箱找 verify 邮件，解 quoted-printable，
提取「Verify your email」跟踪链接并自动访问，完成邮箱确认。"""
from __future__ import annotations

import quopri
import re
from typing import Any

import httpx

from . import cfmail


# 确认邮件主题特征
VERIFY_SUBJECT_RE = re.compile(r"verify your email", re.IGNORECASE)

# 「Verify your email ( https://... )」中的跟踪链接
VERIFY_LINK_RE = re.compile(
    r"Verify your email\s*\(\s*(https?://[^\s)]+)", re.IGNORECASE
)

# 兜底：邮件里任意 mail.goodstack 跟踪链接
ANY_TRACK_LINK_RE = re.compile(r"https?://url\d+\.mail\.goodstack\.[a-z.]+/ls/click\?[^\s)>\"']+")


def _decode_qp(raw: str) -> str:
    """quoted-printable 解码。

    cfmail 存信时把换行压成了空格，QP 软换行（= CRLF）变成 "= "，
    先把 "= " 接回原行，再标准 QP 解码，否则长 URL 会被截断。
    """
    joined = re.sub(r"=[ \t]+", "", raw or "")
    return quopri.decodestring(joined.encode("utf-8", "replace")).decode("utf-8", "replace")


def extract_verify_link(mail_text: str) -> str | None:
    """从邮件正文提取确认链接。优先取「Verify your email (...)」里的链接。"""
    decoded = _decode_qp(mail_text or "")
    m = VERIFY_LINK_RE.search(decoded)
    if m:
        return m.group(1).rstrip(".,;")
    links = ANY_TRACK_LINK_RE.findall(decoded)
    return links[0] if links else None


def find_verify_mail(address: str, limit: int = 20) -> dict[str, Any] | None:
    """在收件箱里找确认邮件，返回 {mail, link} 或 None。"""
    try:
        data = cfmail.get_mails(address, limit=limit)
    except Exception:
        return None
    mails = (data or {}).get("results") or (data or {}).get("mails") or []
    if isinstance(mails, dict):
        mails = mails.get("results") or []
    for mail in mails:
        subject = (mail or {}).get("subject") or ""
        if not VERIFY_SUBJECT_RE.search(subject):
            continue
        link = extract_verify_link((mail or {}).get("text") or "")
        if link:
            return {"mail": mail, "link": link}
    return None


def click_verify_link(link: str) -> dict[str, Any]:
    """访问确认链接（跟跳转），返回结果。"""
    try:
        with httpx.Client(
            follow_redirects=True, timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        ) as client:
            r = client.get(link)
        ok = 200 <= r.status_code < 400
        return {
            "ok": ok,
            "status_code": r.status_code,
            "final_url": str(r.url)[:300],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def confirm_email(address: str) -> dict[str, Any]:
    """对单个邮箱：找确认邮件 → 点链接。"""
    found = find_verify_mail(address)
    if not found:
        return {"ok": False, "email": address, "reason": "no_verify_mail"}
    result = click_verify_link(found["link"])
    return {
        "ok": bool(result.get("ok")),
        "email": address,
        "link": found["link"][:200],
        "mail_subject": (found["mail"] or {}).get("subject"),
        "click": result,
    }
