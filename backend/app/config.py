"""运行时配置。敏感 token 走环境变量或本地 .env。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("VALCLAIM_DATA_DIR", PROJECT_ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


# 仅放入经 Goodstack advanced-email-validation 验证为 isValid=True 的 cfmail org 域名
def _org_domains() -> tuple[str, ...]:
    raw = os.getenv(
        "CFMAIL_ORG_DOMAINS",
        "foejapanjp.org,jaapfjp.org,living-in-peacejp.org,"
        "edu.foejapanjp.org,edu.jaapfjp.org,edu.lk1950.online,"
        "lk1950.online,lk1940.cc.cd",
    )
    return tuple(d.strip() for d in raw.split(",") if d.strip())


@dataclass
class Settings:
    # Goodstack
    goodstack_base: str = "https://api.goodstack.io/"
    entry_url: str = os.getenv(
        "GOODSTACK_ENTRY_URL", "https://validate.poweredbypercent.com/openai"
    )
    partner_public_key: str = os.getenv(
        "GOODSTACK_PARTNER_KEY",
        "pk_3f371f2f-b470-43d5-9605-dc1a58b8ccb3",
    )
    default_country: str = "JPN"
    default_query_pool: tuple[str, ...] = (
        "NPO", "Foundation", "Charity", "Association", "Society", "Welfare",
    )

    # cfmail worker
    cfmail_base: str = os.getenv("CFMAIL_BASE", "https://cfmail.lk1950.online")
    cfmail_send_token: str = os.getenv("CFMAIL_SEND_TOKEN", "")
    cfmail_admin_token: str = os.getenv("CFMAIL_ADMIN_TOKEN", "")
    cfmail_org_domains: tuple[str, ...] = field(default_factory=_org_domains)

    # 固定申请人 = 川博
    contact_first_name: str = os.getenv("VALCLAIM_FIRST_NAME", "博")
    contact_last_name: str = os.getenv("VALCLAIM_LAST_NAME", "川")
    contact_language: str = "en"

    host: str = "127.0.0.1"
    port: int = 8765
    db_path: Path = field(default_factory=lambda: DATA_DIR / "valclaim.db")


settings = Settings()