"""Independent controls for the generated EDA and its signal calculations."""
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from analyze import ROOT, counter_boundaries, sha256, welch_exported


def verify():
    # A known continuous sinusoid has a known frequency and mean-square power.
    n = 8192
    signal = (2 * np.sin(2*np.pi*.125*np.arange(n)))[:,None]
    frequency,power,count = welch_exported(signal,[(0,n)])
    assert abs(frequency[np.argmax(power[:,0])]-.125) < 1e-12
    assert abs(np.trapezoid(power[:,0],frequency)-2) < .01
    assert count == 7
    # A short discontinuous prefix must not be joined to a constant segment.
    broken = np.r_[np.arange(512), np.ones(4096)][:,None]
    _,power,count = welch_exported(broken,[(0,512),(512,4608)])
    assert count == 3 and np.max(power) == 0
    boundaries,valid = counter_boundaries([254,255,0,1,8,9])
    assert boundaries.tolist()==[4] and valid.all()

    result=json.loads((ROOT/'reports/analysis.json').read_text(encoding='utf-8'))
    assert result['total_rows']==353120
    summary=pd.read_csv(ROOT/'reports/quality_summary.csv')
    assert len(summary)==6 and summary.rows_removed.sum()==0
    assert summary.counter_discontinuities.sum()==5
    assert summary.invalid_numeric_cells.sum()==0
    assert summary.duplicate_full_rows.sum()==0
    assert summary.finite_signal_values_changed.sum()==0
    for recording in result['recordings']:
        raw=ROOT/'data/raw'/recording['filename']
        original=Path.home()/'Downloads'/recording['filename']
        assert sha256(raw)==recording['sha256']
        if original.exists():
            assert sha256(original)==recording['sha256']
        source=pd.read_csv(raw,float_precision='round_trip')
        annotated=pd.read_csv(ROOT/'data/cleaned'/f'{recording["id"]}_annotated.csv',float_precision='round_trip')
        assert len(source)==len(annotated)==recording['rows']
        assert np.array_equal(source.to_numpy(dtype=float),annotated[source.columns].to_numpy(dtype=float),equal_nan=True)
        assert np.array_equal(annotated.sample_index,np.arange(len(source)))
        assert np.array_equal(annotated.source_csv_row,np.arange(len(source))+2)
        breaks,_=counter_boundaries(source.Counter)
        assert annotated.flag_counter_break_before.sum()==len(breaks)
    images=list((ROOT/'reports/figures').glob('*.png'))
    assert len(images)==28
    for image in images:
        with Image.open(image) as im:
            assert im.width>=1000 and im.height>=500
            im.verify()
    report=(ROOT/'reports/eda_report.html').read_text(encoding='utf-8')
    import re
    from urllib.parse import urlparse
    for relative in re.findall(r'(?:src|href)="([^"]+)"',report):
        if urlparse(relative).scheme or relative.startswith('#'):
            continue
        assert (ROOT/'reports'/relative).exists(),relative
    assert result['configuration']['filter_settings']['notch_selected_hz']==50
    assert result['configuration']['filter_settings']['brain_documented_cutoff_hz']==45
    assert result['configuration']['filter_settings']['screenshot_version']=='2.7.0a'
    assert result['configuration']['filter_settings']['inspected_source_version']=='2.7.1a'
    assert 'Filter settings and export provenance' in report
    workbook=ROOT/'reports/outputs/npg_eda/quality_summary.xlsx'
    from zipfile import ZipFile
    with ZipFile(workbook) as archive:
        assert len([name for name in archive.namelist() if name.startswith('xl/worksheets/sheet') and name.endswith('.xml')])==2
    print('PASS: source hashes, all 353120 numeric rows preserved, five counter boundaries, analytic PSD checks, 28 figures, report links and workbook structure.')


if __name__=='__main__':
    verify()
