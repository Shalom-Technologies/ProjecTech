import pathlib
import subprocess
import sys

import pytest

FLOWS = pathlib.Path(__file__).parent / "flows"


@pytest.mark.parametrize("script", sorted(FLOWS.glob("check_*.py")), ids=lambda p: p.stem)
def test_flow(script):
    # -I: isolated mode, so nothing in the environment can change what the script imports.
    result = subprocess.run(
        [sys.executable, "-I", str(script)], capture_output=True, text=True, timeout=120
    )
    failures = [line for line in result.stdout.splitlines() if line.startswith("FAIL")]
    assert result.returncode == 0 and not failures, (
        f"{script.name} failed\n" + "\n".join(failures) + "\n" + result.stdout[-1500:] + result.stderr[-1500:]
    )
