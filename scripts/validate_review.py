"""Capture reproducible review checks without modifying the frozen model."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/review_2026-10-02"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / ".cache/review_temp"
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TEMP=str(scratch), TMP=str(scratch),
               MPLCONFIGDIR=str(ROOT / ".cache/matplotlib"), PYTHONIOENCODING="utf-8")
    checks = {
        "tests": ["-m", "unittest", "discover", "-v"],
        "dependencies": ["-m", "pip", "check"],
        "lsl_discovery": ["-m", "src.acquisition.list_lsl"],
        "heldout_demo": ["-m", "src.realtime.heldout_demo"],
        "phase1": ["-c", "from pathlib import Path; from src.models.phase1_evaluation import run_evaluation; import json; r=run_evaluation(output_dir=Path('.cache/review_phase1')); print(json.dumps(r['summary'], indent=2)); print('Skipped:', r['skipped'])"],
        "phase2": ["-m", "src.models.phase2_evaluation"],
    }
    records = {}
    for name, arguments in checks.items():
        start = time.monotonic()
        result = subprocess.run([sys.executable, *arguments], cwd=ROOT, env=env,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        (OUTPUT / f"{name}.stdout.log").write_text(result.stdout, encoding="utf-8")
        (OUTPUT / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
        records[name] = {"command": [sys.executable, *arguments], "returncode": result.returncode,
                         "seconds": round(time.monotonic() - start, 3)}
        (OUTPUT / "checks.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"{name}: exit={result.returncode}, seconds={records[name]['seconds']}", flush=True)
    return int(any(record["returncode"] for record in records.values()))


if __name__ == "__main__":
    raise SystemExit(main())
