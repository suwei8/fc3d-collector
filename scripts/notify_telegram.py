#!/usr/bin/env python3
"""把归档仓库中最新一期记录推送到 Telegram。

用法:  python scripts/notify_telegram.py [归档根目录]
需要环境变量 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID（缺失时返回非零）。
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

QUARTET = [
    ("trial_number", "试机号"),
    ("focus", "关注码"),
    ("gold", "金码"),
    ("corresponding", "对应码"),
]
RIDDLES = [
    ("beijing", "北京"),
    ("beijing_alt", "另版"),
]
BOTTOM = [
    ("bottom_focus", "底部关注码"),
    ("bottom_gold", "底部金码"),
]

_CST = timezone(timedelta(hours=8))


def latest_record(root: Path) -> dict[str, Any] | None:
    files = sorted(root.glob("raw/*/20*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def archive_blob_url(root: Path, issue: str) -> str | None:
    try:
        remote = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote)
    if not m:
        return None
    return (
        f"https://github.com/{m.group(1)}/{m.group(2)}"
        f"/blob/{branch}/data/{issue[:4]}/{issue}.md"
    )


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _join(fields: dict[str, Any], pairs: list[tuple[str, str]]) -> str:
    items = []
    for key, label in pairs:
        value = fields.get(key)
        if value in (None, "", []):
            continue
        shown = "、".join(value) if isinstance(value, list) else _esc(value)
        items.append(f"{label} {shown}")
    return " · ".join(items)


def format_message(record: dict[str, Any], link: str | None = None) -> str:
    fields = record.get("fields") or {}
    title = f"<b>福彩3D {_esc(record['issue'])}期</b>"
    if record.get("status"):
        title += f"（{_esc(record['status'])}）"
    lines = [title]
    if record.get("draw_result"):
        lines.append(f"开奖号：<b>{_esc(record['draw_result'])}</b>")
    lines.append("")

    for row in (
        _join(fields, QUARTET),
        f"太湖 {_esc(fields['taihu'])}" if fields.get("taihu") else "",
        _join(fields, RIDDLES),
        _join(fields, BOTTOM),
    ):
        if row:
            lines.append(row)

    footer = []
    if record.get("collected_at"):
        try:
            cst = datetime.fromisoformat(record["collected_at"]).astimezone(_CST)
            footer.append(f"采集于 {cst:%m-%d %H:%M}（北京）")
        except ValueError:
            pass
    if link:
        footer.append(f'<a href="{link}">完整记录</a>')
    if footer:
        lines.extend(["", " · ".join(footer)])
    return "\n".join(lines)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    record = latest_record(root)
    if not record:
        print(f"[warn] no records under {root}/raw; nothing to send")
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[error] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")
        return 1

    text = format_message(record, archive_blob_url(root, record["issue"]))
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    ok = r.status_code == 200 and r.json().get("ok")
    if not ok:
        print(f"[error] telegram sendMessage failed: {r.status_code} {r.text[:300]}")
        return 1
    print(f"[ok] sent issue {record['issue']} to chat {chat_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
