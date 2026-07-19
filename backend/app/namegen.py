"""随机人名前缀生成（罗马字姓氏 + 名）。"""

from __future__ import annotations

import random
import secrets
import string

# 简单罗马字日本姓氏前缀池（用于邮箱 local-part，与本国姓名解耦）
JP_ROMAN_SURNAMES = [
    "Yamamoto", "Tanaka", "Suzuki", "Sato", "Watanabe", "Ito", "Nakamura",
    "Kobayashi", "Kato", "Yoshida", "Yamada", "Sasaki", "Matsumoto",
    "Inoue", "Kimura", "Hayashi", "Yamazaki", "Mori", "Abe", "Ikeda",
    "Hashimoto", "Yamaguchi", "Kojima", "Aoki", "Nishimura", "Fukuda",
    "Ota", "Fujita", "Okada", "Hasegawa", "Nakajima", "Ishikawa", "Maeda",
    "Sakamoto", "Murakami", "Endo", "Ono", "Takagi", "Tamura", "Takeuchi",
]

JP_GIVEN_NAMES = [
    "Hiroshi", "Kenji", "Yuki", "Akira", "Daichi", "Sora", "Haruto", "Ren",
    "Kaito", "Riku", "Souta", "Yuto", "Itsuki", "Minato", "Aoi", "Rai",
    "Naoki", "Sho", "Tatsuya", "Yuma", "Gaku", "Sora", "Hikaru", "Kai",
]


def random_local_part(style: str = "first.last") -> str:
    """随机生成邮箱 local-part。

    style:
      first.last      -> hiroshi.yamamoto
      firstlast       -> hiroshiyamamoto
      first.lastNN    -> hiroshi.yamamoto73
      random          -> 8 字符随机小写
    """
    if style == "random":
        return "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    surname = random.choice(JP_ROMAN_SURNAMES).lower()
    given = random.choice(JP_GIVEN_NAMES).lower()
    if style == "firstlast":
        return f"{given}{surname}"
    if style == "first.lastNN":
        suffix = "".join(secrets.choice(string.digits) for _ in range(random.randint(2, 4)))
        return f"{given}.{surname}{suffix}"
    return f"{given}.{surname}"


def random_email(domain: str, style: str | None = None) -> str:
    style = style or random.choice(["first.last", "first.lastNN", "firstlast"])
    return f"{random_local_part(style)}@{domain}"