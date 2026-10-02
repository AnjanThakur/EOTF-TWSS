"""CSV/JSON/Markdown exports with protocol and environment provenance."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FROZEN_FILES = ('models/csp_lda_s001.joblib', 'configs/phase1_config.yaml',
                'src/preprocessing/preprocess.py', 'results/phase1/results.json',
                'results/phase1/fold_metrics.csv', 'results/phase1/summary.md')


def freeze_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FROZEN_FILES}


def software_versions():
    packages = ('mne', 'numpy', 'scipy', 'matplotlib', 'scikit-learn', 'pandas',
                'joblib', 'pyttsx3', 'streamlit', 'pylsl', 'PyYAML', 'pyriemann')
    return {'python': platform.python_version(), **{p: version(p) for p in packages}}


def export_experiment(folder, config, tables, description, details=None):
    folder = Path(folder)
    # Never let a new experiment overwrite a historical phase report.
    for protected in (ROOT / 'results/phase1', ROOT / 'results/phase2'):
        if folder.resolve() == protected.resolve() or protected.resolve() in folder.resolve().parents:
            raise ValueError('New experiment output must be separate from frozen/historical results.')
    folder.mkdir(parents=True, exist_ok=True)
    tables = {name: pd.DataFrame(rows) for name, rows in tables.items()}
    for name, frame in tables.items():
        frame.to_csv(folder / f'{name}.csv', index=False)
    payload = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
               'configuration': config, 'software_versions': software_versions(),
               'description': description, 'details': details or {},
               'tables': {name: json.loads(frame.to_json(orient='records', double_precision=15))
                          for name, frame in tables.items()}}
    (folder / 'report.json').write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')
    (folder / 'configuration.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    lines = ['# ' + config['experiment'], '', description, '', '## Protocol', '',
             '```json', json.dumps(config, indent=2), '```', '',
             'Timestamp (UTC): ' + payload['timestamp_utc'], '', '## Results', '']
    for name, frame in tables.items():
        lines += ['### ' + name, '', f'Rows: {len(frame)}. Complete table: `{name}.csv`.', '']
        if len(frame) <= 60:
            # Render without adding the optional tabulate dependency.
            shown = frame.fillna('Not defined')
            lines += ['| ' + ' | '.join(map(str, shown.columns)) + ' |',
                      '| ' + ' | '.join('---' for _ in shown.columns) + ' |']
            lines += ['| ' + ' | '.join(str(v).replace('|', '/') for v in row) + ' |'
                      for row in shown.itertuples(index=False, name=None)]
            lines += ['']
    lines += ['## Details', '', '```json', json.dumps(details or {}, indent=2), '```', '',
              '## Software versions', '', '```json', json.dumps(payload['software_versions'], indent=2), '```']
    (folder / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return payload


def metric_summary(folds, group='variant'):
    frame = pd.DataFrame(folds)
    rows = []
    for name, selected in frame.groupby(group, sort=False):
        row = {group: name, 'folds': len(selected), 'subjects': selected.subject.nunique()}
        for metric in ('accuracy', 'balanced_accuracy', 'f1', 'mcc'):
            row[f'{metric}_mean'] = float(selected[metric].mean())
            row[f'{metric}_std'] = float(selected[metric].std(ddof=1))
        rows.append(row)
    return pd.DataFrame(rows)
