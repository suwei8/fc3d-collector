import json

from scripts.notify_telegram import format_message, latest_record

RECORD = {
    "issue": "2026264",
    "status": "candidate",
    "draw_result": "119",
    "fields": {
        "beijing": "渡浅滩",
        "beijing_alt": "鸡大腿",
        "taihu": "官封白吃侯",
        "trial_number": "741",
        "focus": "169",
        "gold": "1",
        "corresponding": "236",
        "bottom_focus": ["2", "4"],
        "bottom_gold": "7",
    },
    "collected_at": "2026-10-05T12:17:55.958519+00:00",
}


def test_format_message_full_record():
    msg = format_message(RECORD, "https://example.com/x.md")
    assert "<b>福彩3D 2026264期</b>（candidate）" in msg
    assert "开奖号：<b>119</b>" in msg
    assert "试机号 741 · 关注码 169 · 金码 1 · 对应码 236" in msg
    assert "太湖 官封白吃侯" in msg
    assert "北京 渡浅滩 · 另版 鸡大腿" in msg
    assert "底部关注码 2、4 · 底部金码 7" in msg
    assert "采集于 10-05 20:17（北京）" in msg
    assert 'href="https://example.com/x.md"' in msg


def test_format_message_partial_record():
    rec = {
        "issue": "2026265",
        "status": "candidate",
        "fields": {"taihu": "某某一语"},
        "collected_at": "2026-10-06T10:00:00+00:00",
    }
    msg = format_message(rec)
    assert "2026265期" in msg
    assert "太湖 某某一语" in msg
    assert "开奖号" not in msg
    assert "试机号" not in msg
    assert "采集于 10-06 18:00（北京）" in msg


def test_latest_record_picks_max_issue(tmp_path):
    raw = tmp_path / "raw" / "2026"
    raw.mkdir(parents=True)
    for issue in ("2026263", "2026264", "2026262"):
        (raw / f"{issue}.json").write_text(json.dumps({"issue": issue}))
    assert latest_record(tmp_path)["issue"] == "2026264"


def test_latest_record_empty(tmp_path):
    assert latest_record(tmp_path) is None
