from scripts.collect import (
    discover_cz89_nightly_url,
    parse_cz89_nightly,
    parse_taihu,
    parse_tianqi,
)


def test_parse_tianqi_history_row():
    html = """
    <table>
      <tr><th>期数</th><th>日期</th><th>开机号</th><th>试机号</th><th>关注码</th><th>金码</th><th>对应码</th><th>开奖号</th></tr>
      <tr><td>2026258</td><td>09-25</td><td>364</td><td>018</td><td>546</td><td>5</td><td>369</td><td>635</td></tr>
    </table>
    """
    assert parse_tianqi(html)["2026258"] == {
        "trial_number": "018",
        "focus": "546",
        "gold": "5",
        "corresponding": "369",
        "draw_result": "635",
    }


def test_parse_tianqi_pending_draw_has_no_draw_result():
    html = """
    <table>
      <tr><th>期数</th><th>日期</th><th>开机号</th><th>试机号</th><th>关注码</th><th>金码</th><th>对应码</th><th>开奖号</th></tr>
      <tr><td>2026264</td><td>10-01</td><td>364</td><td>018</td><td>546</td><td>5</td><td>369</td><td></td></tr>
    </table>
    """
    row = parse_tianqi(html)["2026264"]
    assert "draw_result" not in row


def test_parse_taihu_history_row():
    html = """
    <table>
      <tr><th>期号</th><th>开奖号</th><th>试机号</th><th>太湖一语</th></tr>
      <tr><td>2026258</td><td>635</td><td>018</td><td>山君坐镇</td></tr>
    </table>
    """
    assert parse_taihu(html)["2026258"] == "山君坐镇"


def test_discover_cz89_nightly_url_for_issue():
    html = """
    <html><body>
      <a href="/read_10852801.htm">26年263期福彩3D晚间字谜汇总大全</a>
      <a href="/read_other.htm">26年263期牛彩网福彩3D字谜汇总大全〖晚间版〗</a>
    </body></html>
    """
    assert (
        discover_cz89_nightly_url(html, "2026263")
        == "https://m.cz89.com/read_10852801.htm"
    )


def test_parse_cz89_nightly_2026258_golden_fields():
    html = """
    <html><body>
      <p>千禧3D试机号2026年258期：</p>
      <p>试机号018</p>
      <p>关注码546</p>
      <p>金码5</p>
      <p>对应码：[369]</p>
      <p>牛彩关注码 9,5,4</p>
      <p>牛彩网关注码：1,3</p>
      <p>金码：8</p>
      <p>北京试机号谜语 踏霜行</p>
      <p>另版北京试机号谜语 其它内容</p>
      <p>太湖一语定胆 山君坐镇</p>
    </body></html>
    """
    assert parse_cz89_nightly(html) == {
        "trial_number": "018",
        "focus": "546",
        "gold": "5",
        "corresponding": "369",
        "beijing": "踏霜行",
        "beijing_alt": "其它内容",
        "bottom_focus": ["1", "3"],
        "bottom_gold": "8",
    }


def test_parse_cz89_nightly_2026263_current_shape():
    html = """
    <html><body>
      <p>试机号395</p>
      <p>关注码804</p>
      <p>金码8</p>
      <p>对应码：[048]</p>
      <p>牛彩关注码 1,8,5</p>
      <p>牛彩网关注码：6,9</p>
      <p>金码：5</p>
      <p>北京试机号谜语 访古寺</p>
      <p>另版北京试机号谜语 走天涯</p>
      <p>太湖一语定胆 摸哨</p>
    </body></html>
    """
    assert parse_cz89_nightly(html) == {
        "trial_number": "395",
        "focus": "804",
        "gold": "8",
        "corresponding": "048",
        "beijing": "访古寺",
        "beijing_alt": "走天涯",
        "bottom_focus": ["6", "9"],
        "bottom_gold": "5",
    }


def test_discover_cz89_historical_2026257_from_archive_page():
    html = """
    <html><body>
      <a href="/read_10831867.htm">26年257期福彩3D晚间字谜汇总大全</a>
      <a href="/read_other.htm">26年257期北京3d试机号后谜语汇总</a>
    </body></html>
    """
    assert (
        discover_cz89_nightly_url(
            html,
            "2026257",
            base_url="https://www.cz89.com/tag/4_56.htm?p=4",
        )
        == "https://www.cz89.com/read_10831867.htm"
    )


def test_parse_cz89_nightly_2026257_source_fields():
    html = """
    <html><body>
      <p>千禧3D试机号2026年257期：</p>
      <p>试机号275</p>
      <p>关注码392</p>
      <p>金码9</p>
      <p>对应码：[959]</p>
      <p>牛彩关注码 1,4,0</p>
      <p>牛彩网关注码：6,8</p>
      <p>金码：2</p>
      <p>北京试机号谜语 戏流泉</p>
      <p>另版北京试机号谜语 拉丁语</p>
      <p>太湖一语定胆 左手倒右手</p>
    </body></html>
    """
    assert parse_cz89_nightly(html) == {
        "trial_number": "275",
        "focus": "392",
        "gold": "9",
        "corresponding": "959",
        "beijing": "戏流泉",
        "beijing_alt": "拉丁语",
        "bottom_focus": ["6", "8"],
        "bottom_gold": "2",
    }
