"""日本 NPO 法人ポータルサイトの全件データダウンロード + 法人番号フィルタ + SQLite 入庫。

参考: https://www.npo-homepage.go.jp/npoportal/download/all
全件ファイル: /npoportal/download/zip/gyousei_000.zip （全国一括）
1ファイル内に 1 CSV:
    000_AdministrativeInputData_YYYYMMDD.csv
列 (cp932):
    0  法人名称
    1  法人名称カナ
    4  主たる事務所の所在地
    5  主たる事業所の郵便番号
    7  代表者氏名
    8  代表者名カナ
    9  法人設立認証年月日
   32  認定（認定・特例認定１）
   48  法人情報URL
   49  法人番号
   60 列
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import httpx

from .config import settings


NPO_ZIP_INDEX = 0  # gyousei_000.zip は全国一括
NPO_ZIP_URL_TMPL = "https://www.npo-homepage.go.jp/npoportal/download/zip/gyousei_{idx:03d}.zip"

# CSV 列インデックス
COL_NAME = 0
COL_NAME_KANA = 1
COL_ADDRESS = 4
COL_POSTAL = 5
COL_REPRESENTATIVE = 7
COL_CERTIFIED_YMD = 9
COL_RECOGNIZED_FLAG = 32  # 認定（認定・特例認定１）
COL_INFO_URL = 48
COL_CORPORATE_NUMBER = 49


CORPORATE_NUMBER_RE = re.compile(r"^\d{13}$")


def _download_zip(idx: int, dest: Path) -> Path:
    url = NPO_ZIP_URL_TMPL.format(idx=idx)
    with httpx.stream("GET", url, timeout=300, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    return dest


def _iter_zips(idx_list: Iterable[int], work_dir: Path):
    work_dir.mkdir(parents=True, exist_ok=True)
    for idx in idx_list:
        zip_path = work_dir / f"gyousei_{idx:03d}.zip"
        if not zip_path.exists():
            _download_zip(idx, zip_path)
        yield idx, zip_path


def _read_csv_from_zip(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = next(
            (n for n in zf.namelist() if n.lower().endswith(".csv")),
            None,
        )
        if not csv_name:
            return
        info = zf.getinfo(csv_name)
        # cp932 / shift_jis
        raw = zf.read(info)
        try:
            text = raw.decode("cp932")
        except UnicodeDecodeError:
            text = raw.decode("shift_jis", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    yield header
    for row in reader:
        yield row


def _safe(row, i):
    if i is None or i >= len(row):
        return ""
    val = row[i]
    if isinstance(val, str):
        val = val.strip()
    return val or ""


def _is_recognized(row: list[str]) -> bool:
    """認定・特例認定 NPO かどうかの簡易判定。"""
    for i in (32, 33, 34, 35, 36, 37, 38):
        if _safe(row, i) and _safe(row, i) not in ("0", "false", "False", "無", ""):
            return True
    return False


def collect_npos_from_zip(zip_path: Path):
    """yield dict per NPO with corporate_number present and 13 digit."""
    gen = _read_csv_from_zip(zip_path)
    header = next(gen, None)
    if not header:
        return
    for row in gen:
        if not isinstance(row, list):
            continue
        corp_num = _safe(row, COL_CORPORATE_NUMBER).replace("-", "")
        if not CORPORATE_NUMBER_RE.match(corp_num):
            continue
        yield {
            "corporate_number": corp_num,
            "name": _safe(row, COL_NAME),
            "name_kana": _safe(row, COL_NAME_KANA),
            "address": _safe(row, COL_ADDRESS),
            "postal_code": _safe(row, COL_POSTAL),
            "representative": _safe(row, COL_REPRESENTATIVE),
            "certified_ymd": _safe(row, COL_CERTIFIED_YMD),
            "info_url": _safe(row, COL_INFO_URL),
            "is_recognized": _is_recognized(row),
        }


def import_npos(conn, idx_list=None, prefer_recognized: bool = True, progress_cb=None) -> dict:
    """从 zip 抽出有法人番号的 NPO 入库。conn: sqlite3.Connection。"""
    if idx_list is None:
        idx_list = [NPO_ZIP_INDEX]
    work_dir = settings.db_path.parent / "npo_zips"
    inserted = 0
    skipped = 0
    for idx, zip_path in _iter_zips(idx_list, work_dir):
        n = 0
        for entry in collect_npos_from_zip(zip_path):
            cur = conn.execute(
                """INSERT OR IGNORE INTO jp_npos(
                    corporate_number, name, name_kana, address, postal_code,
                    representative, certified_ymd, info_url, is_recognized, used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                (
                    entry["corporate_number"], entry["name"], entry["name_kana"],
                    entry["address"], entry["postal_code"],
                    entry["representative"], entry["certified_ymd"],
                    entry["info_url"], int(entry["is_recognized"]),
                ),
            )
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1
            n += 1
            if progress_cb and n % 2000 == 0:
                progress_cb(idx, n, inserted, skipped)
    return {"inserted": inserted, "skipped": skipped, "zips": len(idx_list)}