"""Goodstack 官方 API 客户端。

- 入口跳转拿到 validationinvite_* + JWT
- 列表/搜索国家组织
- advanced-email-validation
- POST validation-submissions 提交
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from .config import settings


INVITE_RE = re.compile(r"validationinvite_[a-zA-Z0-9-]+")
TOKEN_RE = re.compile(r"token=([^&]+)")


@dataclass
class InviteInfo:
    invite_id: str
    token: str
    partner_public_key: str
    redirect_url: str


def fetch_invite(entry_url: str | None = None) -> InviteInfo:
    """打开 OpenAI 入口，跟随 302，拿到 invite 与 token。"""
    url = entry_url or settings.entry_url
    with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = client.get(url)
        final = str(resp.url)
    m = INVITE_RE.search(final)
    t = TOKEN_RE.search(final)
    if not m or not t:
        raise RuntimeError(f"无法从入口解析 invite/token: {final}")
    return InviteInfo(
        invite_id=m.group(0),
        token=t.group(1),
        partner_public_key=settings.partner_public_key,
        redirect_url=final,
    )


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    h = {
        "Authorization": settings.partner_public_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "en",
        "User-Agent": "Mozilla/5.0",
    }
    if extra:
        h.update(extra)
    return h


def list_organisations(
    *,
    country_code: str = settings.default_country,
    query: str = "",
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    params = {
        "countryCode": country_code,
        "query": query,
        "page": page,
        "pageSize": page_size,
    }
    with httpx.Client(timeout=40) as client:
        r = client.get(
            settings.goodstack_base + "v1/organisations",
            params=params,
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json()


def find_org_by_corporate_number(corporate_number: str, country_code: str | None = None) -> dict[str, Any] | None:
    """用 13 位法人番号做 query 精准命中 Goodstack 上已有组织。"""
    cc = country_code or settings.default_country
    data = list_organisations(country_code=cc, query=corporate_number, page=1, page_size=5)
    items = data.get("data") or []
    for o in items:
        if (o.get("registryId") or "").replace("-", "") == corporate_number:
            return o
    if items:
        return items[0]
    return None


def validate_email(email: str) -> bool:
    with httpx.Client(timeout=30) as client:
        r = client.get(
            settings.goodstack_base + "v1/advanced-email-validation/results",
            params={"email": email},
            headers=_headers(),
        )
        if r.status_code >= 400:
            return False
        return bool((r.json().get("result") or {}).get("isValid"))


@dataclass
class SubmissionResult:
    status_code: int
    ok: bool
    payload: dict[str, Any]
    raw: str


def create_validation_submission(
    *,
    invite_id: str,
    organisation_id: str,
    first_name: str,
    last_name: str,
    email: str,
    language: str = "en",
    website: str | None = None,
) -> SubmissionResult:
    """已知 organisationId 的提交方式（推荐）。

    - organisationId 已存在 → 不能再带 organisationName
    """
    body: dict[str, Any] = {
        "validationInviteId": invite_id,
        "organisationId": organisation_id,
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "language": language,
    }
    if website:
        body["website"] = website
    with httpx.Client(timeout=60) as client:
        r = client.post(
            settings.goodstack_base + "v1/validation-submissions",
            json=body,
            headers=_headers(),
        )
        text = r.text
        try:
            data = r.json() if text else {}
        except Exception:
            data = {"raw": text}
    return SubmissionResult(
        status_code=r.status_code,
        ok=(r.status_code in (200, 201)),
        payload=data,
        raw=text,
    )


def list_registries(country_code: str | None = None) -> list[dict[str, Any]]:
    cc = country_code or settings.default_country
    with httpx.Client(timeout=30) as client:
        r = client.get(
            settings.goodstack_base + "v1/registries",
            params={"countryCode": cc, "pageSize": 100},
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json().get("data") or []