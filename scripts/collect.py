#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# 数据目录默认为本仓库根目录；在 GitHub Actions 中通过 FC3D_ROOT 指向
# checkout 出来的私有归档仓库（suwei8/fc3d-archive）。
ROOT = Path(os.environ.get("FC3D_ROOT", Path(__file__).resolve().parents[1]))
UA = "fc3d-collector/0.1 (+https://github.com/suwei8/fc3d-collector)"

TIANQI_URL = "https://www.800820.cn/kj/3d_sjh.html"
TAIHU_URL = "https://www.cpzj.com/3d/yydd/"
CZ89_HOME_URL = "https://m.cz89.com/"
CZ89_ARCHIVE_URL = "https://www.cz89.com/tag/4_56.htm"

FIELDS = [
    "beijing", "beijing_alt", "taihu", "trial_number", "focus", "gold",
    "corresponding", "bottom_focus", "bottom_gold",
]

LABELS = {
    "beijing": "北京",
    "beijing_alt": "另版北京",
    "taihu": "太湖",
    "trial_number": "试机号",
    "focus": "关注码",
    "gold": "金码",
    "corresponding": "对应码",
    "bottom_focus": "底部关注码",
    "bottom_gold": "底部金码",
}


def fetch(url: str) -> str:
    r = requests.get(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        },
        timeout=25,
    )
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text


def safe_fetch(url: str, source_name: str) -> str | None:
    """Fetch one upstream without aborting the whole collection on source failure."""
    try:
        return fetch(url)
    except requests.RequestException as exc:
        print(f"[warn] {source_name} unavailable: {exc}")
        return None


def _cells(tr) -> list[str]:
    return [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]


def _issue_token(value: str) -> str | None:
    m = re.search(r"20\d{5}", value.replace(" ", ""))
    return m.group(0) if m else None


def parse_tianqi(html: str) -> dict[str, dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: dict[str, dict[str, str]] = {}
    for tr in soup.find_all("tr"):
        cells = _cells(tr)
        if len(cells) < 7:
            continue
        issue = _issue_token(cells[0])
        if not issue:
            continue
        compact = [re.sub(r"\s+", "", c) for c in cells]
        trial = re.sub(r"\D", "", compact[3])
        focus = re.sub(r"\D", "", compact[4])
        gold = re.sub(r"\D", "", compact[5])
        corresponding = re.sub(r"\D", "", compact[6])
        row: dict[str, str] = {}
        if len(trial) == 3 and len(focus) == 3 and len(gold) == 1 and len(corresponding) == 3:
            row = {
                "trial_number": trial,
                "focus": focus,
                "gold": gold,
                "corresponding": corresponding,
            }
        if len(compact) > 7:
            draw = re.sub(r"\D", "", compact[7])
            if len(draw) == 3:
                row["draw_result"] = draw
        if row:
            rows[issue] = row
    return rows


def parse_taihu(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    rows: dict[str, str] = {}
    for tr in soup.find_all("tr"):
        cells = _cells(tr)
        if len(cells) < 4:
            continue
        issue = _issue_token(cells[0])
        if not issue:
            continue
        phrase = re.sub(r"\s+", "", cells[3])
        if phrase:
            rows[issue] = phrase
    return rows


def discover_cz89_nightly_url(home_html: str, issue: str, base_url: str = CZ89_HOME_URL) -> str | None:
    """Find the issue-specific 牛彩网“福彩3D晚间字谜汇总大全” page in one listing page."""
    soup = BeautifulSoup(home_html, "html.parser")
    year2 = issue[2:4]
    issue_no = str(int(issue[-3:]))
    pattern = re.compile(
        rf"(?:20)?{re.escape(year2)}年0*{re.escape(issue_no)}期福彩3D晚间字谜汇总大全"
    )
    for a in soup.find_all("a", href=True):
        title = re.sub(r"\s+", "", a.get_text(" ", strip=True))
        if pattern.search(title):
            return urljoin(base_url, a["href"])
    return None


def discover_cz89_nightly_history(issue: str, max_pages: int = 12) -> str | None:
    """Search the 3D字谜总汇 archive for a historical issue."""
    for page in range(1, max_pages + 1):
        listing_url = CZ89_ARCHIVE_URL if page == 1 else f"{CZ89_ARCHIVE_URL}?p={page}"
        html = safe_fetch(listing_url, f"cz89-archive-p{page}")
        if not html:
            continue
        found = discover_cz89_nightly_url(html, issue, base_url=listing_url)
        if found:
            print(f"[info] cz89 historical issue {issue} found on archive page {page}: {found}")
            return found
    print(f"[warn] cz89 historical issue {issue} not found in first {max_pages} archive pages")
    return None


CZ89_ITEM4_URL = "https://www.cz89.com/3d/item_4.htm"
SINA_API = "https://mix.lottery.sina.com.cn/gateway/index/entry"

# "26年264期…福彩3D晚间字谜汇总大全" -> 2026264；兼容 "2026年264期" 写法
_CZ89_TITLE_ISSUE_RE = re.compile(r"(?:20)?(\d{2})年0*(\d{1,3})期")
_CZ89_DIGEST_TITLE_RE = re.compile(r"(?:20)?\d{2}年0*\d{1,3}期福彩3D晚间字谜汇总大全")


def _cz89_title_issue(title: str) -> str | None:
    m = _CZ89_TITLE_ISSUE_RE.search(title.replace(" ", ""))
    if not m:
        return None
    return f"20{m.group(1)}{int(m.group(2)):03d}"


def index_cz89_nightly(lo: str, hi: str, max_pages: int = 2500) -> dict[str, str]:
    """扫描 tag/4_56 字谜汇总标签列表（按时间倒序、?p=N 分页），建立 {期号: 汇总大全文章URL} 索引。

    注意：item_4 分类页深翻后不再含"晚间字谜汇总大全"文章，历史回填必须用
    tag/4_56.htm（按期连续：每页约覆盖 1.7 期，26年初约在 130-160 页深）。
    列表按时间倒序，但置顶/顶贴会混入老期号，因此需要"连续 3 页最大期号均 < lo"
    才判定已越过区间，避免单页老帖导致提前停止。
    """
    idx: dict[str, str] = {}
    old_streak = 0
    for page in range(1, max_pages + 1):
        listing_url = CZ89_ARCHIVE_URL if page == 1 else f"{CZ89_ARCHIVE_URL}?p={page}"
        html = safe_fetch(listing_url, f"cz89-tag-p{page}")
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        page_issues: list[str] = []
        for a in soup.find_all("a", href=True):
            title = re.sub(r"\s+", "", a.get_text(" ", strip=True))
            issue = _cz89_title_issue(title)
            if issue:
                page_issues.append(issue)
            if issue and lo <= issue <= hi and _CZ89_DIGEST_TITLE_RE.search(title) and issue not in idx:
                idx[issue] = urljoin(listing_url, a["href"])
        if page_issues and max(page_issues) < lo:
            old_streak += 1
            if old_streak >= 3:
                print(f"[info] cz89 index scan stopped at page {page} (3 consecutive pages below {lo})")
                break
        else:
            old_streak = 0
        if page % 20 == 0:
            print(f"[info] cz89 index scan: page {page}, {len(idx)} issues indexed")
        time.sleep(0.3)
    print(f"[info] cz89 index: {len(idx)} digest pages in [{lo}, {hi}]")
    return idx


def fetch_taihu_history(lo: str, max_pages: int = 15) -> dict[str, str]:
    """彩之家太湖列表 index_N.html 翻页，返回 {期号: 太湖一语}（含首页）。"""
    rows: dict[str, str] = {}
    for page in range(1, max_pages + 1):
        url = TAIHU_URL if page == 1 else urljoin(TAIHU_URL, f"index_{page}.html")
        html = safe_fetch(url, f"cpzj-taihu-p{page}")
        if not html:
            break
        page_rows = parse_taihu(html)
        rows.update(page_rows)
        if page_rows and min(page_rows) < lo:
            break
        time.sleep(0.3)
    return rows


def fetch_sina_draws(wanted: set[str], max_pages: int = 25) -> dict[str, str]:
    """新浪开奖 API（lottoType=102 福彩3D）：翻页直到 wanted 期号全部命中。

    返回 {期号: '987'}。官方 cwl.gov.cn 接口被网宿 WAF 拦海外 IP，Actions/Worker
    均在海外运行，故用与 Lottery_Assistant 同款的新浪接口。
    """
    draws: dict[str, str] = {}
    pending = set(wanted)
    for page in range(1, max_pages + 1):
        try:
            r = requests.get(
                SINA_API,
                params={
                    "format": "json", "__caller__": "wap", "__version__": "1.0.0",
                    "__verno__": "10000", "cat1": "gameOpenList", "paginationType": "1",
                    "dpc": "1", "lottoType": "102", "page": str(page), "pageSize": "50",
                },
                headers={"Accept": "application/json", "User-Agent": UA},
                timeout=15,
            )
            r.raise_for_status()
            data = (r.json().get("result") or {})
        except (requests.RequestException, ValueError) as exc:
            print(f"[warn] sina draw api page {page} failed: {exc}")
            break
        for it in data.get("data") or []:
            issue = str(it.get("issueNo") or "")
            if re.fullmatch(r"\d{5}", issue):
                issue = "20" + issue
            draw = re.sub(r"\D", "", "".join(it.get("openResults") or []))
            if re.fullmatch(r"20\d{5}", issue) and len(draw) == 3:
                draws[issue] = draw
        pending -= draws.keys()
        total_page = int((data.get("pagination") or {}).get("totalPage") or 1)
        if not pending or page >= total_page:
            break
        time.sleep(0.4)
    return draws


def parse_cz89_nightly(html: str) -> dict[str, Any]:
    """Parse nightly digest fields, including core trial data as a fallback."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    result: dict[str, Any] = {}

    core = re.search(
        r"(?ms)^试机号\s*[:：]?\s*(\d{3})\s*$.*?"
        r"^关注码\s*[:：]?\s*(\d{3})\s*$.*?"
        r"^金码\s*[:：]?\s*(\d)\s*$.*?"
        r"^对应码\s*[:：]?\s*[\[【]?\s*(\d{3})",
        text,
    )
    if core:
        result.update({
            "trial_number": core.group(1),
            "focus": core.group(2),
            "gold": core.group(3),
            "corresponding": core.group(4),
        })

    beijing = re.search(
        r"(?m)^北京试机号谜语\s*[:：]?\s*([^\n]+?)\s*$",
        text,
    )
    if beijing:
        result["beijing"] = beijing.group(1).strip()

    beijing_alt = re.search(
        r"(?m)^另版北京试机号谜语\s*[:：]?\s*([^\n]+?)\s*$",
        text,
    )
    if beijing_alt:
        result["beijing_alt"] = beijing_alt.group(1).strip()

    bottom_focus = re.search(
        r"(?m)^牛彩网关注码\s*[:：]\s*([0-9０-９,，、\s]+?)\s*$",
        text,
    )
    if bottom_focus:
        digits = re.findall(r"\d", bottom_focus.group(1))
        if digits:
            result["bottom_focus"] = digits

        tail = text[bottom_focus.end():]
        bottom_gold = re.search(
            r"(?m)^金码\s*[:：]\s*(\d)\s*$",
            tail,
        )
        if bottom_gold:
            result["bottom_gold"] = bottom_gold.group(1)

    return result


def newest_issue(*collections) -> str:
    issues: set[str] = set()
    for collection in collections:
        issues.update(collection.keys())
    if not issues:
        raise RuntimeError("No issue number could be parsed from upstream sources")
    return max(issues, key=int)


def load_existing(issue: str) -> dict[str, Any] | None:
    path = ROOT / "raw" / issue[:4] / f"{issue}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _is_locked(existing: dict[str, Any] | None, key: str, fields: dict[str, Any]) -> bool:
    if not existing:
        return False
    if key in (existing.get("locked_fields") or []):
        return True
    return existing.get("status") == "verified" and fields.get(key) is not None


def build_record(issue: str, tianqi: dict[str, dict[str, str]], taihu: dict[str, str], cz89: dict[str, Any] | None = None, cz89_url: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    existing = load_existing(issue)
    fields = {key: None for key in FIELDS}
    if existing:
        fields.update(existing.get("fields", {}))

    sources: dict[str, Any] = {}
    draw_result = existing.get("draw_result") if existing else None
    if issue in tianqi:
        for key in ("trial_number", "focus", "gold", "corresponding"):
            value = tianqi[issue].get(key)
            if value is None:
                continue
            if not _is_locked(existing, key, fields):
                fields[key] = value
        # 开奖号是客观结果，只在缺失时补入，已收录的不覆盖
        if not draw_result and tianqi[issue].get("draw_result"):
            draw_result = tianqi[issue]["draw_result"]
        sources["tianqi-sjh"] = {
            "url": TIANQI_URL,
            "fetched_at": now,
            "fields": [
                key for key in ("trial_number", "focus", "gold", "corresponding", "draw_result")
                if key in tianqi[issue]
            ],
        }

    if issue in taihu:
        if not _is_locked(existing, "taihu", fields):
            fields["taihu"] = taihu[issue]
        sources["cpzj-taihu"] = {
            "url": TAIHU_URL,
            "fetched_at": now,
            "fields": ["taihu"],
        }

    if cz89:
        # cz89 carries the same trial/focus/gold/corresponding quartet. Use it only
        # as a fallback when the primary Tianqi source is unavailable/missing.
        for key in ("trial_number", "focus", "gold", "corresponding"):
            if key in cz89 and fields.get(key) in (None, ""):
                fields[key] = cz89[key]

        for key in ("beijing", "beijing_alt", "bottom_focus", "bottom_gold"):
            if key not in cz89:
                continue
            if not _is_locked(existing, key, fields):
                fields[key] = cz89[key]

        sources["cz89-nightly"] = {
            "url": cz89_url or CZ89_HOME_URL,
            "fetched_at": now,
            "fields": [
                key for key in (
                    "trial_number", "focus", "gold", "corresponding",
                    "beijing", "beijing_alt", "bottom_focus", "bottom_gold",
                )
                if key in cz89
            ],
        }

    status = "verified" if existing and existing.get("status") == "verified" else "candidate"
    return {
        "issue": issue,
        "status": status,
        "verified_by": existing.get("verified_by") if existing else None,
        "locked_fields": existing.get("locked_fields", []) if existing else [],
        "fields": fields,
        "draw_result": draw_result,
        "sources": sources,
        "collected_at": now,
        "notes": existing.get("notes", []) if existing else [],
    }


def render_md(record: dict[str, Any]) -> str:
    status = record["status"]
    lines = [
        f"# 福彩3D {record['issue']}期",
        "",
        f"> 当前状态：**{status}**",
        "",
    ]
    if record.get("draw_result"):
        lines.extend([f"> 开奖号：**{record['draw_result']}**", ""])
    lines.extend([
        "| 字段 | 数据 |",
        "| --- | --- |",
    ])
    locked = set(record.get("locked_fields") or [])
    for key in FIELDS:
        value = record["fields"].get(key)
        shown = "、".join(value) if isinstance(value, list) else (value or "—")
        if key in locked:
            shown += "（人工修正）"
        lines.append(f"| {LABELS[key]} | {shown} |")

    lines.extend(["", "## 数据源", ""])
    if record.get("sources"):
        for source_id, meta in record["sources"].items():
            lines.append(f"- {source_id}: {meta['url']}")
    else:
        lines.append("- 暂无自动来源记录")

    lines.extend([
        "",
        "## 说明",
        "",
        "- 自动采集结果默认保持 candidate，未经人工核图不得升级为 verified。",
        "- 已人工确认的字段不会被后续自动采集覆盖。",
        "",
    ])
    return "\n".join(lines)


def write_record(record: dict[str, Any]) -> None:
    issue = record["issue"]
    year = issue[:4]
    raw_dir = ROOT / "raw" / year
    data_dir = ROOT / "data" / year
    raw_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{issue}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (data_dir / f"{issue}.md").write_text(render_md(record), encoding="utf-8")


def backfill(lo: str, hi: str) -> int:
    """按数值区间回填历史期号（期号=年份*1000+年内日序，数值递增即时间递增）。

    - 天齐表只留最近 ~10 期，历史期自动缺失其四字段（与 draw 无关字段）
    - 太湖列表翻页补齐；cz89 先建 issue->文章URL 索引再逐期抓详情页
    - 开奖号用新浪接口按缺失期号集合定向翻页补齐
    - 跨年无效期号（如 2025400）上游无数据，自动跳过不写文件
    """
    tianqi_html = safe_fetch(TIANQI_URL, "tianqi-sjh")
    tianqi = parse_tianqi(tianqi_html) if tianqi_html else {}
    taihu = fetch_taihu_history(lo)

    # 先建 cz89 汇总大全文章索引（O(页数)），再逐期抓详情页（O(期数)）
    cz89_index = index_cz89_nightly(lo, hi)

    # 开奖号：新浪按缺失集合定向翻页；写入时只在缺失才补
    wanted = {
        str(i) for i in range(int(lo), int(hi) + 1)
        if re.fullmatch(r"20\d{5}", str(i))
    }
    sina_draws = fetch_sina_draws(wanted)
    print(f"[info] sina draws fetched: {len(sina_draws)} issues")

    written = skipped = 0
    for i in range(int(lo), int(hi) + 1):
        issue = str(i)
        cz89: dict[str, Any] = {}
        cz89_url = cz89_index.get(issue)
        if cz89_url:
            page_html = safe_fetch(cz89_url, f"cz89-{issue}")
            if page_html:
                cz89 = parse_cz89_nightly(page_html)

        has_data = issue in tianqi or issue in taihu or bool(cz89)
        existing = load_existing(issue)
        if not has_data:
            skipped += 1
            continue  # 无效期号/无上游数据：不写垃圾记录，已有记录也不动
        record = build_record(issue, tianqi, taihu, cz89=cz89, cz89_url=cz89_url)
        if not record["draw_result"] and issue in sina_draws:
            record["draw_result"] = sina_draws[issue]
            record["sources"]["sina-open"] = {
                "url": SINA_API,
                "fetched_at": record["collected_at"],
                "fields": ["draw_result"],
            }
        write_record(record)
        written += 1
        print(f"[ok] {issue} written" + ("" if existing else " (new)"))
        time.sleep(0.3)

    print(f"[done] backfill [{lo}, {hi}]: {written} written, {skipped} skipped")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue", help="期号，例如 2026263；省略则取上游最新期")
    parser.add_argument("--from", dest="from_issue", help="回填起始期号（配合 --to）")
    parser.add_argument("--to", dest="to_issue", help="回填结束期号（配合 --from）")
    parser.add_argument("--tianqi-file", help="离线调试：读取天齐 HTML")
    parser.add_argument("--taihu-file", help="离线调试：读取太湖 HTML")
    parser.add_argument("--cz89-home-file", help="离线调试：读取牛彩网首页 HTML")
    parser.add_argument("--cz89-page-file", help="离线调试：直接读取牛彩网晚间字谜页 HTML")
    args = parser.parse_args()

    if args.from_issue and args.to_issue:
        return backfill(args.from_issue, args.to_issue)

    tianqi_html = (
        Path(args.tianqi_file).read_text(encoding="utf-8")
        if args.tianqi_file
        else safe_fetch(TIANQI_URL, "tianqi-sjh")
    )
    taihu_html = (
        Path(args.taihu_file).read_text(encoding="utf-8")
        if args.taihu_file
        else safe_fetch(TAIHU_URL, "cpzj-taihu")
    )

    tianqi = parse_tianqi(tianqi_html) if tianqi_html else {}
    taihu = parse_taihu(taihu_html) if taihu_html else {}
    issue = args.issue or newest_issue(tianqi, taihu)

    if issue not in tianqi and issue not in taihu and not load_existing(issue):
        print(f"[warn] issue {issue} absent from primary upstream pages; trying cz89")

    cz89: dict[str, Any] = {}
    cz89_url: str | None = None
    if args.cz89_page_file:
        cz89_url = "file://" + str(Path(args.cz89_page_file).resolve())
        cz89 = parse_cz89_nightly(Path(args.cz89_page_file).read_text(encoding="utf-8"))
    else:
        home_html = (
            Path(args.cz89_home_file).read_text(encoding="utf-8")
            if args.cz89_home_file
            else safe_fetch(CZ89_HOME_URL, "cz89-home")
        )
        if home_html:
            cz89_url = discover_cz89_nightly_url(home_html, issue)
        if not cz89_url:
            cz89_url = discover_cz89_nightly_history(issue)
        if cz89_url:
            page_html = safe_fetch(cz89_url, "cz89-nightly")
            if page_html:
                cz89 = parse_cz89_nightly(page_html)

    # 注意按"本期是否命中任一上游"判断：tianqi/taihu 是整表 dict，历史期号查不到行
    # 但表本身非空，若按表判空会为无效期号写出全空字段的垃圾记录。
    has_data = issue in tianqi or issue in taihu or bool(cz89)
    if not has_data:
        if load_existing(issue):
            print(f"[info] issue {issue} not in upstream pages today; keep existing record")
            return 0
        raise SystemExit(f"No usable upstream data for issue {issue}")

    record = build_record(issue, tianqi, taihu, cz89=cz89, cz89_url=cz89_url)
    write_record(record)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
