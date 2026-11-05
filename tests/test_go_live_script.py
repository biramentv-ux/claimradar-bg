import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "go_live.ps1"


def test_go_live_script_targets_the_space_api():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "https://huggingface.co/api/spaces/$SpaceId" in text
    for path in ("'/runtime'", "'/variables'", "'/secrets'", "'/restart'"):
        assert path in text
    assert "DyrakArmy/claimradar-bg" in text
    assert "claimradar.dyrakarmy.eu" in text


def test_go_live_script_has_no_hardcoded_secrets():
    text = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"hf_[A-Za-z0-9]{20,}", text)
    assert not re.search(r"sk-[A-Za-z0-9]{20,}", text)
    assert "-AsSecureString" in text


def test_go_live_script_braces_are_balanced():
    text = SCRIPT.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert code.count("{") == code.count("}")
    assert code.count("(") == code.count(")")
