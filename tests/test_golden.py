import json
import os
from pathlib import Path

import pytest

ROOT = Path(os.environ.get("FC3D_ROOT", Path(__file__).resolve().parents[1]))
GOLDEN = ROOT / "raw" / "2026" / "2026258.json"

pytestmark = pytest.mark.skipif(
    not GOLDEN.exists(), reason="archive data not checked out (set FC3D_ROOT)"
)


def test_2026258_golden_fixture_is_locked():
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert data["status"] == "verified"
    assert data["fields"] == {
        "beijing": "踏霜行",
        "beijing_alt": "流水线",
        "taihu": "山君坐镇",
        "trial_number": "018",
        "focus": "546",
        "gold": "5",
        "corresponding": "369",
        "bottom_focus": ["1", "3"],
        "bottom_gold": "8",
    }
