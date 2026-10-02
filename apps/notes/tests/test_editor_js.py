"""Runs the notes editor's JavaScript tests under Node.

The editor's markdown conversion, outline and shortcut handling are plain
ES modules in static/js; their tests live in tests/js and use Node's
built-in runner (no packages). This wrapper puts them in the pytest run.
Without a recent Node they are skipped; run them by hand with:

    node --test "apps/notes/tests/js/*.test.mjs"
"""

import shutil
import subprocess
from pathlib import Path

import pytest

JS_TESTS = Path(__file__).parent / "js"

# The modules are .js files with ES module syntax and no package.json, which
# Node loads as modules from 22.7 on
MIN_NODE = (22, 7)


def _node():
    node = shutil.which("node")
    if not node:
        return None
    version = subprocess.run(
        [node, "--version"], capture_output=True, text=True, check=False
    ).stdout
    try:
        major, minor = (
            int(part) for part in version.strip().lstrip("v").split(".")[:2]
        )
    except ValueError:
        return None
    return node if (major, minor) >= MIN_NODE else None


@pytest.mark.parametrize(
    "script", sorted(path.name for path in JS_TESTS.glob("*.test.mjs"))
)
def test_editor_js(script):
    node = _node()
    if node is None:
        pytest.skip("needs Node 22.7 or later on PATH")
    result = subprocess.run(
        [node, "--test", str(JS_TESTS / script)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
