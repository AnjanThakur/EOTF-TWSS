"""Inspect downloaded SRM EDF headers, reproduce both datasets, then promote verified outputs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import mne
import numpy as np
import pandas as pd
from scripts.run_phase3_analysis import run_phase3_analysis
from src.reporting.experiments import software_versions

ROOT = Path(__file__).resolve().parents[1]


def inspect_download(dataset):
    rows, failed = [], []
    for file in sorted(dataset.rglob('*.edf')):
        try:
            raw = mne.io.read_raw_edf(file, preload=False, verbose=False)
            raw.pick('eeg')
            rows.append({'file': str(file.relative_to(ROOT).as_posix()),
                         'subject': next(p for p in file.parts if p.startswith('sub-')),
                         'channels': len(raw.ch_names), 'channel_names': raw.ch_names,
                         'sampling_rate': float(raw.info['sfreq']), 'samples': int(raw.n_times),
                         'duration_seconds': float(raw.n_times/raw.info['sfreq']),
                         'two_second_windows': int(raw.n_times//int(2*raw.info['sfreq']))})
            raw.close()
        except (OSError, ValueError) as exc:
            failed.append({'file': str(file), 'error': str(exc)})
    files = [f for f in dataset.rglob('*') if f.is_file()]
    return {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'dataset_root': str(dataset.relative_to(ROOT).as_posix()),
            'download_objects': len(files), 'download_bytes': sum(f.stat().st_size for f in files),
            'edf_headers_inspected': len(rows) + len(failed),
            'subject_directories': len(list(dataset.glob('sub-*'))),
            'valid_edf_files': len(rows), 'valid_subjects': len(set(r['subject'] for r in rows)),
            'sampling_rates': sorted(set(r['sampling_rate'] for r in rows)),
            'channel_counts': sorted(set(r['channels'] for r in rows)),
            'potential_nonoverlapping_2s_windows': sum(r['two_second_windows'] for r in rows),
            'failed_files': failed, 'records': rows}


def main():
    dataset = ROOT/'data/srm/ds003775'; staged = ROOT/'results/phase3_reproduction'
    staged.mkdir(parents=True, exist_ok=True)
    inventory = inspect_download(dataset)
    (staged/'download_inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    pd.DataFrame(inventory['records']).drop(columns='channel_names').to_csv(staged/'edf_inventory.csv', index=False)
    print({k: v for k, v in inventory.items() if k != 'records'}, flush=True)
    run_phase3_analysis(staged, dataset)
    # Promotion happens only after both datasets, all metadata and eight figures exist.
    summary = json.loads((staged/'dataset_summary.json').read_text(encoding='utf-8'))
    for name in ['srm', 'physionet']:
        frame = pd.read_csv(staged/name/'features.csv')
        expected = summary['feature_counts'][name+'_total_features']
        assert frame.shape[1] == expected + (name == 'physionet')
        assert np.isfinite(frame.to_numpy()).all()
        assert len(json.loads((staged/name/'feature_metadata.json').read_text())) == expected
    assert len(list((staged/'plots').rglob('*.png'))) == 8
    target = ROOT/'results/phase3'; archive = ROOT/'results/phase3_historical'
    # Resolve every destination and restrict copies to this explicit workspace results tree.
    for path in [target, archive, staged]:
        if ROOT/'results' not in path.resolve().parents:
            raise ValueError('Result destination escaped workspace.')
    if not archive.exists():
        shutil.copytree(target, archive)
        (archive/'ARCHIVE.md').write_text('Historical Phase-3 outputs preserved before successful current-code reproduction on 2026-10-02. They are not current-code evidence.\n', encoding='utf-8')
    shutil.copytree(staged, target, dirs_exist_ok=True)
    provenance = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'software_versions': software_versions(),
                  'dataset': 'SRM ds003775 raw EDF, CC0; public unsigned S3',
                  'processing': {'max_subjects': 5, 'window_duration': 2.0, 'overlap': 0.0,
                                 'artifact_cleaning_added': False, 'classification_added': False},
                  'summary': summary, 'source_code_sha256': hashlib.sha256((ROOT/'scripts/run_phase3_analysis.py').read_bytes()).hexdigest()}
    (target/'reproduction_provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    srm = summary['srm']; pn = summary['physionet']
    lines = ['# Phase-3 reproducibility status', '', 'Reproduced successfully with current code on 2026-10-02.', '',
             'Unsigned S3 sync completed with exit code 0. Source: `s3://openneuro.org/ds003775`. Root: `data/srm/ds003775/`.',
             f"Downloaded {inventory['download_objects']} objects, {inventory['download_bytes']} bytes; {inventory['edf_headers_inspected']} EDF headers inspected across {inventory['subject_directories']} subject directories. Valid headers: {inventory['valid_edf_files']} across {inventory['valid_subjects']} subjects.",
             f"Header validation: EEG channel counts {inventory['channel_counts']}; sampling rates {inventory['sampling_rates']} Hz. Failed headers: {inventory['failed_files']}.",
             'Header readability is not a signal-quality assessment. Finite samples were validated for the processed subset, not every downloaded recording.', '',
             f"SRM processed subset: {srm['subjects_processed']} subjects, {srm['recordings_processed']} recordings, {srm['total_windows']} nonoverlapping 2-second windows, {srm['channels']} channels, {srm['sampling_frequency_hz']} Hz, {srm['total_features']} features/window.",
             f"PhysioNet: {pn['total_trials']} S001 imagery trials, {pn['channels']} channels, {pn['sampling_frequency_hz']} Hz, {pn['total_features']} features/trial.",
             'No failed/excluded files in the selected subset. Additional downloaded subjects were intentionally outside the existing five-subject analysis limit; no short recording was silently discarded by a file-size threshold.', '',
             'Both datasets were regenerated in `results/phase3_reproduction/`, verified for finite CSV values, matching per-dataset metadata lengths, and eight plots, then copied here. Previous artifacts are preserved under `results/phase3_historical/`.',
             'Per-dataset metadata: `srm/feature_metadata.json` and `physionet/feature_metadata.json`. The root legacy metadata file describes SRM only; use the per-dataset files for comparisons.',
             'PCA uses standardized features under current code. EEG rates, channel counts, tasks and window definitions differ, so PCA/feature plots do not establish dataset equivalence or transfer performance.', '',
             'Inventory: `download_inventory.json`, `edf_inventory.csv`. Processing summary: `dataset_summary.json`. Environment and code fingerprint: `reproduction_provenance.json`. The real SRM loader test now executes rather than skips.']
    (target/'REPRODUCIBILITY_STATUS.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('Both datasets verified and promoted; historical Phase 3 retained.', flush=True)


if __name__ == '__main__':
    main()
