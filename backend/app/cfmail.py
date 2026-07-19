"""cfmail worker 客户端：收信查询 / 提取验证码 / 发信。"""

from __future__ import annotations

from typing import Any

import httpx

from .config import settings


def _headers(token: str | None = None) -> dict[str, str]:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get_mails(address: str, limit: int = 20) -> dict[str, Any] | list[Any]:
    """收件箱免密读（PUBLIC_READ_BY_ADDRESS=1）。"""
    with httpx.Client(timeout=20) as client:
        r = client.get(
            settings.cfmail_base + "/api/mails",
            params={"address": address, "limit": limit},
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json()


def get_latest_code(address: str) -> dict[str, Any] | None:
    """cfmail 内置取最新验证码。"""
    with httpx.Client(timeout=20) as client:
        r = client.get(
            settings.cfmail_base + "/api/code",
            params={"address": address},
            headers=_headers(),
        )
        if r.status_code >= 400:
            return None
        return r.json()


def send_mail(
    *,
    to_addr: str,
    subject: str,
    text: str,
    from_addr: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """需要 SEND_TOKEN 才能发信。"""
    token = token or settings.cfmail_send_token
    if not token:
        raise RuntimeError("未配置 CFMAIL_SEND_TOKEN")
    body = {
        "from": from_addr or f"noreply@{settings.cfmail_org_domains[0]}",
        "to": to_addr,
        "subject": subject,
        "text": text,
    }
    with httpx.Client(timeout=30) as client:
        r = client.post(
            settings.cfmail_base + "/api/send",
            json=body,
            headers=_headers(token),
        )
        r.raise_for_status()
        return r.json()