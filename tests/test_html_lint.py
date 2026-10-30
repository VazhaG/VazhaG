"""The page's HTML passes djlint — ADR-0012's lint command for site/, run here because a gate runs one command."""

from __future__ import annotations

import subprocess
import sys

from support import ROOT


def test_djlint_site() -> None:
    r = subprocess.run([sys.executable, "-m", "djlint", "site", "--lint"], cwd=ROOT, check=False,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
