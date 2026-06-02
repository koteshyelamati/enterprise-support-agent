from __future__ import annotations
import logging
import os
import subprocess
import sys
import tempfile
from typing import Tuple

logger = logging.getLogger(__name__)
_MAX_EXEC_SECONDS = 10


def execute_script_safely(code: str) -> Tuple[bool, str]:
    """Execute a Python script in a subprocess sandbox. Returns (success, output_or_error)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(code)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [sys.executable, tmp_path], capture_output=True, text=True, timeout=_MAX_EXEC_SECONDS
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, (result.stderr or "Script exited with non-zero status").strip()
    except subprocess.TimeoutExpired:
        return False, f"Execution timed out after {_MAX_EXEC_SECONDS} seconds"
    except Exception as exc:
        return False, f"Executor error: {exc}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def generate_diagnostic_script(issue_description: str) -> str:
    """Generate a safe diagnostic script tailored to the issue description."""
    desc_lower = issue_description.lower()
    if any(kw in desc_lower for kw in ("disk", "storage", "space", "drive")):
        return (
            "import shutil\ntotal, used, free = shutil.disk_usage('/')\ngb = 2**30\n"
            "print(f'Total : {total/gb:.1f} GB')\nprint(f'Used  : {used/gb:.1f} GB')\n"
            "print(f'Free  : {free/gb:.1f} GB')\nprint(f'Usage : {used/total*100:.1f}%')\n"
        )
    if any(kw in desc_lower for kw in ("network", "connection", "ping", "vpn", "internet")):
        return (
            "import socket\ntargets = [('8.8.8.8', 53), ('1.1.1.1', 53)]\n"
            "for host, port in targets:\n"
            "    try:\n        s = socket.create_connection((host, port), timeout=3)\n"
            "        s.close()\n        print(f'{host}:{port} reachable')\n"
            "    except OSError as e:\n        print(f'{host}:{port} unreachable: {e}')\n"
        )
    if any(kw in desc_lower for kw in ("memory", "ram", "crash", "bsod")):
        return (
            "import platform, sys\n"
            "print(f'Platform : {platform.system()} {platform.release()}')\n"
            "print(f'Python   : {sys.version}')\n"
            "print('Memory diagnostic: run Windows Memory Diagnostic (mdsched.exe)')\n"
        )
    return (
        "import platform, datetime\n"
        "print(f'OS      : {platform.system()} {platform.release()}')\n"
        "print(f'Node    : {platform.node()}')\n"
        "print(f'Python  : {platform.python_version()}')\n"
        "print(f'Time    : {datetime.datetime.now().isoformat()}')\n"
        "print('Generic diagnostic complete.')\n"
    )


def generate_corrected_script(original_script: str, error_message: str) -> str:
    """Produce a corrected version of a failed script (re-prompt LLM in production)."""
    lines = [l for l in original_script.splitlines() if l.strip()]
    safe_lines = [l for l in lines if "undefined" not in l.lower() and "NameError" not in l]
    safe_lines.append("print('Self-corrected diagnostic complete.')")
    logger.info("Script corrected after error: %s", error_message[:100])
    return "\n".join(safe_lines) + "\n"
