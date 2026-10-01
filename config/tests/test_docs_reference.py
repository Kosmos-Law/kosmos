"""The generated reference pages and config/.env.example stay in step with
the code. See scripts/gen_docs_reference.py."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_reference_docs_and_env_example_are_current():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gen_docs_reference.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Reference docs or config/.env.example have drifted from the code:\n"
        + result.stderr
    )
