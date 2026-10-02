"""Record exact final test output, dependency health, freeze and Git staging checks."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from src.reporting.experiments import freeze_hashes, software_versions

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT/'results/software_improvements'; folder.mkdir(parents=True, exist_ok=True)
    before = json.loads((folder/'freeze_before.json').read_text())
    environment = {**os.environ, 'MPLBACKEND': 'Agg', 'PYTHONDONTWRITEBYTECODE': '1'}
    commands = [([sys.executable, '-m', 'unittest', 'discover', '-v'], 'unittest'),
                ([sys.executable, '-m', 'pip', 'check'], 'pip_check')]
    execution = {}
    for command, name in commands:
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True)
        stdout, stderr = result.stdout.decode('utf-8', errors='replace'), result.stderr.decode('utf-8', errors='replace')
        (folder/f'{name}.stdout.log').write_bytes(result.stdout)
        (folder/f'{name}.stderr.log').write_bytes(result.stderr)
        execution[name] = {'command': command, 'exit_code': result.returncode,
                           'stdout_file': f'results/software_improvements/{name}.stdout.log',
                           'stderr_file': f'results/software_improvements/{name}.stderr.log'}
        if name == 'unittest':
            match = re.search(r'Ran (\d+) tests in ([\d.]+)s', stderr)
            skipped = len(re.findall(r'\.\.\. skipped ', stderr))
            failures = len(re.findall(r'\.\.\. FAIL\b', stderr)); errors = len(re.findall(r'\.\.\. ERROR\b', stderr))
            count = int(match[1]) if match else None
            execution[name].update({'tests': count, 'seconds': float(match[2]) if match else None,
                                    'skipped': skipped, 'failed': failures, 'errors': errors,
                                    'passed': count-skipped-failures-errors if count is not None else None})
        print(f'{name}: exit {result.returncode}', flush=True)
        print((stderr if name == 'unittest' else stdout)[-450:], flush=True)
    after = freeze_hashes(); (folder/'freeze_after.json').write_text(json.dumps(after, indent=2)+'\n')
    frozen = {path: {'before': before[path], 'after': digest, 'unchanged': before[path] == digest}
              for path, digest in after.items()}
    freeze_commit = '7a19eddf045cd7ffc4deb6c8416a922f3d3bf805'
    original_match = {}
    for path in after:
        historic = subprocess.run(['git', 'show', f'{freeze_commit}:{path}'], cwd=ROOT, capture_output=True, check=True).stdout
        current = (ROOT/path).read_bytes()
        original_match[path] = {'bytes_equal': current == historic,
                               'equal_after_crlf_normalization': current.replace(b'\r\n', b'\n') == historic.replace(b'\r\n', b'\n')}
    staged = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'], cwd=ROOT, capture_output=True, check=True).stdout.decode().splitlines()
    staged_large = [name for name in staged if (ROOT/name).exists() and (ROOT/name).stat().st_size > 10_000_000]
    sensitive_names = [name for name in staged if re.search(r'(^|/)(\.env|credentials|id_rsa|id_ed25519|.*\.pem)(\.|$)', name, re.I)]
    ignore = subprocess.run(['git', 'check-ignore', 'data/srm/ds003775/README'], cwd=ROOT, capture_output=True)
    split_errors = []
    import pandas as pd
    for directory in ['channel_selection', 'frequency_analysis', 'phase2_reproduction']:
        filename = 'current_folds.csv' if directory == 'phase2_reproduction' else 'fold_metrics.csv'
        frame = pd.read_csv(ROOT/'results'/directory/filename)
        split_errors.extend([f'{directory}:{r.subject}:{r.test_run}' for r in frame.itertuples() if r.test_run in r.train_runs.split('+')])
    payload = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'execution': execution,
               'phase1_frozen_files': frozen, 'original_freeze_commit': freeze_commit, 'original_artifact_comparison': original_match,
               'train_test_overlap_errors': split_errors, 'staged_added_or_modified_files': staged,
               'staged_files_over_10MB': staged_large, 'staged_sensitive_filenames': sensitive_names,
               'raw_srm_ignored': ignore.returncode == 0, 'software_versions': software_versions()}
    (folder/'validation.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    ok = (all(item['exit_code'] == 0 for item in execution.values()) and before == after
          and all(item['equal_after_crlf_normalization'] for item in original_match.values())
          and not split_errors and not staged_large and not sensitive_names and ignore.returncode == 0)
    print('Freeze/leakage/staging checks:', 'PASS' if ok else 'FAIL', flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
