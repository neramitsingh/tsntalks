"""infra/contabo/trigger-collect.sh runs from ney's crontab on Contabo and asks GitHub to run collect.yml every
hour — the only clock since GitHub's own `schedule` was dropped on 2026-09-21. These tests keep it a Linux script that
targets the right workflow and stays inert without a token; the live dispatch is verified by hand."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "infra" / "contabo" / "trigger-collect.sh"


def _bash() -> str | None:
    """A bash that accepts a Windows path: Git Bash on the two Windows boxes, whatever is on PATH elsewhere. WSL's
    launcher in System32 comes first on the desktop's PATH and mangles `C:\\...` into nothing, so it is never used."""
    for candidate in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"):
        if Path(candidate).exists():
            return candidate
    found = shutil.which("bash")
    if found and "system32" in found.lower():
        return None
    return found


def test_trigger_script_is_a_linux_bash_script():
    raw = SCRIPT.read_bytes()
    assert raw.startswith(b"#!/usr/bin/env bash\n")
    assert b"\r" not in raw, "a CR after the shebang breaks the script on Contabo"


def test_trigger_script_targets_the_collector_workflow_on_main():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'REPO="neramitsingh/tsntalks"' in text
    assert 'WORKFLOW="collect.yml"' in text
    assert 'REF="main"' in text
    assert "/actions/workflows/$WORKFLOW/dispatches" in text


@pytest.mark.skipif(_bash() is None, reason="needs a bash that takes a Windows path")
def test_trigger_script_is_disarmed_without_a_token(tmp_path):
    """No token file: exit 0, one log line saying so, and nothing else touched — a cron with no token is silent."""
    env = dict(os.environ, HOME=str(tmp_path), TSN_GH_TOKEN_FILE=str(tmp_path / "no-such-token"))
    r = subprocess.run([_bash(), str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    log = tmp_path / ".config" / "tsntalks" / "trigger.log"
    assert log.exists()
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and "disarmed" in lines[0]
    assert not (tmp_path / ".config" / "tsntalks" / "trigger.state").exists()
