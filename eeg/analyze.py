"""Conservative, reproducible EDA of six exported NPG recordings.

No fitting, classification, rereferencing, filtering, interpolation, deletion,
amplitude correction or assumed conversion to volts is performed. Raw snapshots
are byte-identical to their sources. Flags are observations, not artifact diagnoses.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
# Optional task-local plotting packages; bundled Python supplies NumPy/pandas.
if (ROOT / '.analysis_deps').is_dir():
    sys.path.insert(0, str(ROOT / '.analysis_deps'))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from numpy.lib.stride_tricks import sliding_window_view

CHANNELS = [f'Channel{i}' for i in range(1, 7)]
COLORS = ['#2563eb', '#d97706', '#059669', '#9333ea', '#dc2626', '#0891b2']
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.titleweight': 'bold', 'axes.grid': True,
                     'grid.alpha': .17, 'figure.facecolor': 'white',
                     'savefig.facecolor': 'white'})


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def counter_boundaries(counter, modulus=256):
    """Flag anything except +1 or the observed 255-to-0 wrap.

    This does not establish packet-loss counts or reconstruct elapsed time.
    A modulo counter cannot reveal losses of whole counter cycles.
    """
    counter = np.asarray(counter, dtype=float)
    valid = np.isfinite(counter) & (counter == np.floor(counter))
    valid &= (counter >= 0) & (counter < modulus)
    delta = np.diff(counter)
    adjacent_valid = valid[1:] & valid[:-1]
    continuous = adjacent_valid & ((delta == 1) | ((counter[:-1] == modulus - 1) & (counter[1:] == 0)))
    boundaries = np.flatnonzero(~continuous) + 1
    return boundaries, valid


def contiguous_ranges(n, boundaries, row_valid):
    """Return valid uninterrupted [start, end) ranges without bridging bad rows."""
    starts = np.r_[0, boundaries]
    ends = np.r_[boundaries, n]
    ranges = []
    for start, end in zip(starts, ends):
        mask = np.asarray(row_valid[start:end], dtype=bool)
        switches = np.diff(np.r_[False, mask, False].astype(int))
        for a, b in zip(np.flatnonzero(switches == 1), np.flatnonzero(switches == -1)):
            ranges.append((int(start + a), int(start + b)))
    return ranges


def welch_exported(values, ranges, nperseg=2048):
    """One-sided Hann/50%-overlap Welch PSD, fs=1 cycle/sample.

    Each window is demeaned. Only full windows inside uninterrupted valid ranges
    are used. PSD is native-unit squared per cycle/sample. No band interpretation.
    """
    accum = None
    count = 0
    window = np.hanning(nperseg)
    for start, end in ranges:
        if end - start < nperseg:
            continue
        view = sliding_window_view(values[start:end], nperseg, axis=0)[::nperseg // 2]
        blocks = view.transpose(0, 2, 1)
        blocks = blocks - blocks.mean(axis=1, keepdims=True)
        transformed = np.fft.rfft(blocks * window[None, :, None], axis=1)
        power = np.abs(transformed) ** 2 / np.sum(window ** 2)
        power[:, 1:-1, :] *= 2
        subtotal = power.sum(axis=0)
        accum = subtotal if accum is None else accum + subtotal
        count += len(blocks)
    if not count:
        return np.fft.rfftfreq(nperseg), None, 0
    return np.fft.rfftfreq(nperseg), accum / count, count


def envelope_points(values, max_bins=1300):
    """Min/max plotting envelope retains extrema, unlike taking every Nth sample."""
    edges = np.linspace(0, len(values), min(max_bins, len(values)) + 1, dtype=int)
    centers, lo, hi = [], [], []
    for a, b in zip(edges[:-1], edges[1:]):
        centers.append((a + b - 1) / 2)
        lo.append(np.nanmin(values[a:b], axis=0))
        hi.append(np.nanmax(values[a:b], axis=0))
    return np.asarray(centers), np.asarray(lo), np.asarray(hi)


def save_figure(fig, path):
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def per_file_figures(rec, figures, config):
    key, values = rec['id'], rec['values']
    positions = config['channel_positions']
    title = rec['filename']
    boundaries = rec['boundaries']
    centers, lo, hi = envelope_points(values)
    fig, axes = plt.subplots(6, 1, figsize=(12, 10), sharex=True, layout='constrained')
    for j, ax in enumerate(axes):
        ax.fill_between(centers, lo[:, j], hi[:, j], color=COLORS[j], alpha=.8, linewidth=.25)
        for boundary in boundaries:
            ax.axvline(boundary, color='#b91c1c', linestyle='--', linewidth=.9)
        ax.set_ylabel(f'CH{j+1} / {positions[j]}\nNative units')
    axes[-1].set_xlabel('Acquired sample index (zero-based; counter breaks marked red)')
    fig.suptitle(f'{title}: complete recording\nMin/max envelopes preserve peaks; axes use independent amplitude scales', fontsize=13)
    save_figure(fig, figures / f'{key}_overview.png')

    ranges = rec['ranges']
    longest = max(ranges, key=lambda span: span[1]-span[0]) if ranges else (0, len(values))
    a = min(longest[0] + 1000, max(longest[0], longest[1]-1000))
    b = min(a + 1000, longest[1])
    fig, axes = plt.subplots(6, 1, figsize=(12, 9), sharex=True, layout='constrained')
    for j, ax in enumerate(axes):
        ax.plot(np.arange(a,b), values[a:b,j], color=COLORS[j], linewidth=.8)
        ax.set_ylabel(f'CH{j+1} / {positions[j]}\nNative units')
    axes[-1].set_xlabel('Acquired sample index (no task events supplied)')
    fig.suptitle(f'{title}: first fixed 1,000-sample inspection window after startup\nDeterministic selection, not chosen to show a particular answer', fontsize=12)
    save_figure(fig, figures / f'{key}_zoom.png')

    fig, ax = plt.subplots(figsize=(10, 8), layout='constrained')
    im = ax.imshow(rec['corr'], vmin=-1, vmax=1, cmap='RdBu_r')
    labels = [f'CH{i+1}\n{position}' for i, position in enumerate(positions)]
    ax.set_xticks(range(6), labels)
    ax.set_yticks(range(6), labels)
    ax.grid(False)
    for i in range(6):
        for j in range(6):
            ax.text(j, i, f'{rec["corr"][i,j]:.2f}', ha='center', va='center',
                    color='white' if abs(rec['corr'][i,j]) > .65 else '#172033')
    fig.colorbar(im, ax=ax, label='Pearson correlation')
    ax.set_title(f'{title}: exported-channel correlation\nHigh correlation alone does not identify its cause', pad=15)
    save_figure(fig, figures / f'{key}_correlation.png')

    fig, ax = plt.subplots(figsize=(12, 5), layout='constrained')
    frequency, power = rec['frequency'], rec['psd']
    if power is not None:
        for j in range(6):
            ax.semilogy(frequency[1:], power[1:,j], color=COLORS[j], label=f'CH{j+1} / {positions[j]}')
    ax.set_xlim(0, .5)
    ax.set_xlabel('Frequency (cycles per sample; independent of sampling-rate assumption)')
    ax.set_ylabel('PSD (native units² / [cycle/sample])')
    ax.set_title(f'{title}: spectrum of the exported signal\nWelch estimate; windows do not cross counter discontinuities')
    rate = config['analysis_sample_rate_hz']
    sec = ax.secondary_xaxis('top', functions=(lambda f:f*rate, lambda hz:hz/rate))
    sec.set_xlabel(f'Frequency (Hz only if assumed {rate:g} Hz sample rate is correct)')
    ax.legend(ncol=3, fontsize=9)
    save_figure(fig, figures / f'{key}_spectrum.png')


def comparison_figures(records, stats, windows, figures, config):
    matrix = np.array([[stats[(stats.dataset==r['id']) & (stats.channel==f'Channel{j+1}')].rms.iloc[0]
                        for j in range(6)] for r in records])
    fig, ax = plt.subplots(figsize=(11, 6), layout='constrained')
    im = ax.imshow(matrix, cmap='Blues', aspect='auto', vmin=0)
    ax.set_xticks(range(6), [f'CH{i+1} / {p}' for i,p in enumerate(config['channel_positions'])])
    ax.set_yticks(range(len(records)), [r['id'].upper() for r in records])
    ax.grid(False)
    for i in range(len(records)):
        for j in range(6):
            ax.text(j,i,f'{matrix[i,j]:.3f}',ha='center',va='center',color='white' if matrix[i,j]>matrix.max()*.65 else '#172033')
    ax.set_title('Whole-recording RMS of exported values\nAmplitude differences do not establish YES/NO separability')
    fig.colorbar(im, ax=ax, label='RMS (native units)')
    save_figure(fig, figures/'comparison_rms.png')

    fig, axes = plt.subplots(3, 2, figsize=(13, 11), layout='constrained')
    for j,ax in enumerate(axes.flat):
        data = [r['values'][np.isfinite(r['values'][:,j]),j] for r in records]
        ax.boxplot(data, tick_labels=[r['id'].upper() for r in records], showfliers=False, whis=(1,99))
        ax.set_title(f'CH{j+1} / {config["channel_positions"][j]}')
        ax.set_ylabel('Native units')
    fig.suptitle('Amplitude distributions by recording\nBoxes: 25th–75th percentiles; whiskers: 1st–99th; extremes remain in data', fontsize=13)
    save_figure(fig, figures/'comparison_distributions.png')

    fig, axes = plt.subplots(3, 2, figsize=(13, 10), layout='constrained')
    for j,ax in enumerate(axes.flat):
        for color,rec in zip(COLORS,records):
            data = windows[(windows.dataset==rec['id']) & (windows.channel==f'Channel{j+1}')]
            # NaN between separate segments prevents drawing across discontinuities.
            for segment, part in data.groupby('segment_id'):
                ax.plot(part.start_sample, part.rms, color=color, linewidth=1,
                        label=rec['id'].upper() if segment==data.segment_id.min() else None)
        ax.set_title(f'CH{j+1} / {config["channel_positions"][j]}')
        ax.set_xlabel('Acquired sample index')
        ax.set_ylabel('Window RMS (native units)')
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=6)
    fig.suptitle(f'Activity over non-overlapping {config["window_samples"]}-sample windows\nWindows never cross counter breaks or invalid rows', fontsize=13)
    save_figure(fig, figures/'comparison_window_rms.png')

    fig, axes = plt.subplots(3,2,figsize=(13,10),layout='constrained')
    for j,ax in enumerate(axes.flat):
        for color,rec in zip(COLORS,records):
            if rec['psd'] is not None:
                ax.semilogy(rec['frequency'][1:],rec['psd'][1:,j],label=rec['id'].upper(),color=color,linewidth=.9)
        ax.set_title(f'CH{j+1} / {config["channel_positions"][j]}')
        ax.set_xlabel('Frequency (cycles/sample)')
        ax.set_ylabel('PSD (native² / [cycle/sample])')
    fig.legend(*axes.flat[0].get_legend_handles_labels(),loc='outside lower center',ncol=6)
    fig.suptitle('Frequency comparison of exported recordings\nNo physiological band or word-decoding claim is inferred', fontsize=13)
    save_figure(fig, figures/'comparison_spectra.png')


def summarize_findings(summary, pairs, peaks):
    total = sum(r['rows'] for r in summary)
    best = max(pairs, key=lambda p: abs(p['correlation']))
    shared_peak_count = sum(.198 < p['peak_cycles_per_sample'] < .202 for p in peaks)
    return [
        f'All six files contain the expected Counter plus six-channel schema, with {total:,} total sample rows.',
        f'{sum(r["invalid_numeric_cells"] for r in summary)} missing/nonfinite/unparseable numeric cells and {sum(r["duplicate_full_rows"] for r in summary)} duplicate complete rows were found. No rows were deleted.',
        f'{sum(r["counter_discontinuities"] for r in summary)} non-wrap counter discontinuities were found across {sum(r["counter_discontinuities"]>0 for r in summary)} files. All occur at acquired sample indices 210–460 (zero-based). Causes remain unverified.',
        f'The strongest channel correlation is {best["correlation"]:.3f} between {best["channel_a"]} and {best["channel_b"]} in {best["dataset"]}. Correlation is not evidence that a channel is faulty or that its signal is neural.',
        f'{shared_peak_count} of {len(peaks)} channel/recording spectra have their largest non-DC peak near 0.20 cycles/sample. This would be about 100 Hz if the provisional 500 Hz rate is correct. The repeated peak warrants review of interference and export processing; its cause is not identified by EDA.',
        'YES/NO files include thinking and speaking. Changes may reflect speech, muscle/eye activity, recording conditions or neural activity; EDA cannot separate their contributions.',
        'There are no within-file task markers or verified acquisition timestamps. The mixed file cannot be scored as a labelled YES/NO test from its name alone.',
        'No model was trained and no classification accuracy is claimed. Thousands of neighboring samples are not thousands of independent word trials.'
    ]


def report_html(result, root):
    e = html.escape
    filters = result['configuration'].get('filter_settings', {})
    filter_section = ''
    if filters:
        filter_section = f'''<h2>Filter settings and export provenance</h2>
<p>The user-provided Chords Web {e(filters['screenshot_version'])} screenshot shows Brain mode and a {filters['notch_selected_hz']} Hz notch selected on all six channels. The notch setting is not a sampling rate. <a href="{e(filters['documentation_url'])}">Manufacturer documentation</a> describes Brain as a {filters['brain_documented_cutoff_hz']} Hz low-pass; the effective response in these recordings has not been measured.</p>
<p>The <a href="{e(filters['recording_source_url'])}">public recording path inspected</a> saves filtered channel values. The inspected version is {e(filters['inspected_source_version'])}, not the screenshot version {e(filters['screenshot_version'])}. This supports treating these exports as likely already processed, while the exact capture build and scaling remain unverified. No additional filters were applied or undone.</p>
<p>Frequency peaks and attenuation belong to the exported signal, which may include prior-filter effects and residual interference. Low-pass filters attenuate rather than erase all higher-frequency components. The folder named <code>data/raw</code> preserves untouched CSV exports; it does not establish that they are unfiltered ADC data.</p>'''
    summary = pd.DataFrame(result['quality_summary'])
    display = summary[['dataset','rows','invalid_numeric_cells','counter_discontinuities','segments','flagged_amplitude_rows','sample_duration_seconds_assuming_rate']].copy()
    display.columns = ['Recording','Samples','Invalid cells','Counter breaks','Segments','Flagged amplitude rows','Sample count / assumed rate (s)']
    display.iloc[:,-1] = display.iloc[:,-1].round(2)
    channels = pd.DataFrame(result['channel_statistics'])
    strongest = sorted(result['correlation_pairs'],key=lambda p:abs(p['correlation']),reverse=True)[:5]
    notes = result['findings']
    charts = [('comparison_rms.png','RMS amplitude by recording and channel'),
              ('comparison_distributions.png','Distribution comparison'),
              ('comparison_window_rms.png','Changes in activity within each recording'),
              ('comparison_spectra.png','Frequency comparison in cycles per sample')]
    sections = ''.join(f'<figure><img loading="lazy" src="figures/{name}" alt="{e(caption)}"><figcaption>{e(caption)}</figcaption></figure>' for name,caption in charts)
    detail = []
    for recording in result['recordings']:
        key = recording['id']
        table = channels[channels.dataset==key][['channel','position','mean','std','rms','minimum','maximum','flagged_amplitude_samples']].round(5).to_html(index=False,border=0)
        figures = ''.join(f'<figure><img loading="lazy" src="figures/{key}_{kind}.png" alt="{e(key)} {kind}"><figcaption>{e(caption)}</figcaption></figure>' for kind,caption in [('overview','Complete exported recording; extrema preserved in plotting envelopes.'),('zoom','Fixed inspection window; no YES/NO event timing is available.'),('spectrum','Spectrum excludes windows across discontinuities. Upper Hz axis assumes 500 Hz.'),('correlation','Correlation is descriptive and cannot establish neural origin.')])
        detail.append(f'<details><summary>{e(key.upper())}: {e(recording["filename"])}</summary><p>{e(recording["condition"])}</p><div class="scroll">{table}</div>{figures}</details>')
    break_table = pd.DataFrame(result['counter_events']).to_html(index=False,border=0)
    pair_table = pd.DataFrame(strongest)[['dataset','channel_a','channel_b','correlation']].round(4).to_html(index=False,border=0)
    sources = ''.join(f'<li>{e(r["filename"])} — {r["rows"]:,} samples; SHA-256 <code>{r["sha256"]}</code></li>' for r in result['recordings'])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NPG recordings: exploratory analysis</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;color:#172033;background:#f4f6fa;margin:0}}main{{max-width:1120px;margin:auto;padding:36px 24px;background:white}}h1{{font-size:32px;line-height:1.2}}h2{{margin-top:36px}}.note{{border-left:4px solid #d97706;background:#fff7e7;padding:16px}}table{{border-collapse:collapse;font-size:14px;width:100%}}th{{background:#203b62;color:white;text-align:left}}th,td{{padding:9px;border-bottom:1px solid #dce2ea}}td{{vertical-align:top}}.scroll{{overflow:auto}}img{{width:100%;height:auto}}figure{{margin:26px 0}}figcaption{{color:#526177;font-size:14px}}details{{margin:20px 0;border:1px solid #dce2ea;padding:16px;border-radius:8px}}summary{{font-size:18px;font-weight:650;cursor:pointer}}code{{font-size:12px;word-break:break-all}}a{{color:#2455a0}}li{{margin:8px 0}}@media print{{body{{background:white}}main{{padding:0}}details{{break-inside:avoid}}}}</style></head><body><main>
<h1>NPG recordings: exploratory analysis</h1><p>Six exported recordings, six channels, {result['total_rows']:,} acquired samples. Generated {e(result['generated_utc'])}.</p>
<div class="note"><strong>How to interpret this report</strong><br>Values are native exported units. Brain mode and the 50 Hz notch were selected on all six channels. Documentation describes Brain as a 45 Hz low-pass; exact capture-version processing and scaling remain unverified. Sampling rate is provisionally {result['configuration']['analysis_sample_rate_hz']:g} Hz, inferred from approximate two-minute recordings; it is not clock-verified. Primary plots use sample index or cycles/sample. YES/NO recordings include spoken answers. No trial labels, question times or speech-onset markers were supplied.</div>
{filter_section}
<h2>Findings</h2><ul>{''.join('<li>'+e(n)+'</li>' for n in notes)}</ul>
<h2>Recording quality</h2><div class="scroll">{display.to_html(index=False,border=0)}</div>
<p>Counter breaks split analysis segments. The repeated 255-to-0 transition is the normal observed counter wrap. A counter jump can represent lost samples, resets or another acquisition event; its cause and elapsed gap cannot be recovered from these CSVs alone.</p>
<h2>What cleaning changed</h2><p>Original files were copied byte-for-byte and hashed. Cleaned copies keep all rows in source order, preserve every finite signal value and add source-row, segment and quality-flag columns. No filter, interpolation, rereferencing, normalization or amplitude replacement was applied. Large-amplitude flags use a within-file/channel robust deviation threshold of 8; flags do not label samples as artifacts.</p>
<p>Cleaned files therefore remain <strong>annotated exports, not artifact-free EEG or a training-ready word dataset</strong>. No individual YES/NO labels were invented for the mixed recording.</p>
<h2>Counter discontinuities</h2><div class="scroll">{break_table}</div>
<h2>Recording comparisons</h2>{sections}<h2>Strongest channel correlations</h2><div class="scroll">{pair_table}</div><p>Shared activity, reference, filtering, interference and other acquisition effects can all influence correlations. Their cause cannot be determined here.</p>
<h2>Detailed plots and statistics</h2><p>Expand a recording to inspect its four figures and channel measurements.</p>{''.join(detail)}
<h2>Files and reproducibility</h2><ul><li><a href="quality_summary.csv">Quality summary</a></li><li><a href="channel_statistics.csv">Channel statistics</a></li><li><a href="cleaning_log.csv">Cleaning log</a></li><li><a href="counter_events.csv">Counter-event details</a></li><li><a href="window_statistics.csv">Window measurements</a></li><li><a href="spectral_peaks.csv">Spectral peak measurements</a></li><li><a href="outputs/npg_eda/quality_summary.xlsx">Excel quality workbook</a></li><li><a href="../eda.ipynb">Reproducible analysis notebook</a></li></ul>
<h2>What is still needed before classification</h2><ul><li>Exact sampling-rate/export settings and confirmation of channel order.</li><li>Task and speech-onset timestamps, particularly for the mixed file.</li><li>Independent labelled recording sessions for evaluation, rather than randomly splitting neighboring windows from one condition-specific file.</li><li>Silent-answer recordings if the claim is recognition without speaking; no inference of silent word decoding follows from these spoken-answer files.</li></ul>
<h2>Source snapshots</h2><ul>{sources}</ul><p>Channel locations in user-reported order: C3, C4, F3, F4, P3, P4. Left/right clenching body part and timing remain unconfirmed. These files contain no absolute acquisition timestamps.</p>
</main></body></html>'''


def run_analysis(root=ROOT, source_dir=None):
    root = Path(root)
    config = json.loads((root/'recordings.json').read_text(encoding='utf-8'))
    source_dir = Path(source_dir or Path.home()/'Downloads')
    raw_dir, cleaned_dir, reports = root/'data/raw',root/'data/cleaned',root/'reports'
    figures = reports/'figures'
    for folder in (raw_dir,cleaned_dir,reports,figures):
        folder.mkdir(parents=True,exist_ok=True)
    records, summary, statistics, events, logs, windows, peaks, pairs = [],[],[],[],[],[],[],[]
    for entry in config['recordings']:
        source = source_dir/entry['filename']
        snapshot = raw_dir/entry['filename']
        if source.exists():
            if snapshot.exists() and sha256(source)!=sha256(snapshot):
                raise ValueError(f'Source changed since the preserved snapshot: {source.name}. Use a new analysis folder.')
            if not snapshot.exists():
                shutil.copy2(source,snapshot)
        if not snapshot.exists():
            raise FileNotFoundError(source)
        frame = pd.read_csv(snapshot, float_precision='round_trip')
        if list(frame.columns)!=['Counter']+CHANNELS:
            raise ValueError(f'Unexpected CSV schema: {snapshot.name}')
        numeric = frame.apply(pd.to_numeric,errors='coerce')
        original_array = numeric.to_numpy(dtype=float)
        invalid = ~np.isfinite(original_array)
        signal = original_array[:,1:].copy()
        signal[~np.isfinite(signal)] = np.nan
        boundaries, valid_counter = counter_boundaries(original_array[:,0],config['counter_modulus'])
        segments = np.searchsorted(boundaries,np.arange(len(frame)),side='right')
        valid_rows = (~invalid.any(axis=1)) & valid_counter
        ranges = contiguous_ranges(len(frame),boundaries,valid_rows)
        med = np.nanmedian(signal,axis=0)
        mad = np.nanmedian(np.abs(signal-med),axis=0)
        robust_z = np.divide(np.abs(signal-med),1.4826*mad,out=np.zeros_like(signal),where=mad>0)
        extreme = robust_z>config['robust_amplitude_flag_threshold']
        flat = np.nanmax(signal,axis=0)==np.nanmin(signal,axis=0)
        cleaned = numeric.copy()
        cleaned.replace([np.inf,-np.inf],np.nan,inplace=True)
        cleaned.insert(0,'source_csv_row',np.arange(len(frame))+2)
        cleaned.insert(0,'sample_index',np.arange(len(frame)))
        cleaned['segment_id'] = segments
        cleaned['flag_invalid_numeric'] = invalid.any(axis=1)
        cleaned['flag_counter_invalid'] = ~valid_counter
        cleaned['flag_counter_break_before'] = np.isin(np.arange(len(frame)),boundaries)
        cleaned['flag_extreme_amplitude'] = extreme.any(axis=1)
        clean_path = cleaned_dir/f'{entry["id"]}_annotated.csv'
        cleaned.to_csv(clean_path,index=False,float_format='%.17g')
        # Exact round-trip check: serialization must preserve finite numeric values.
        reread = pd.read_csv(clean_path,float_precision='round_trip')
        expected = numeric.to_numpy(dtype=float)
        actual = reread[['Counter']+CHANNELS].to_numpy(dtype=float)
        finite = np.isfinite(expected)
        if not np.array_equal(actual[finite],expected[finite]):
            raise AssertionError(f'Numeric serialization changed source values: {entry["id"]}')
        rate = float(config['analysis_sample_rate_hz'])
        row = dict(dataset=entry['id'],filename=entry['filename'],rows=len(frame),channels=6,
                   invalid_numeric_cells=int(invalid.sum()),invalid_counter_rows=int((~valid_counter).sum()),
                   duplicate_full_rows=int(frame.duplicated().sum()),counter_wraps=int((np.diff(original_array[:,0])==-255).sum()),
                   counter_discontinuities=len(boundaries),segments=int(len(boundaries)+1),
                   flagged_amplitude_rows=int(extreme.any(axis=1).sum()),flat_channels=int(flat.sum()),
                   assumed_sample_rate_hz=rate,sample_duration_seconds_assuming_rate=len(frame)/rate,
                   rows_retained=len(cleaned),rows_removed=0,finite_signal_values_changed=0)
        summary.append(row)
        for boundary in boundaries:
            before, after = original_array[boundary-1,0], original_array[boundary,0]
            events.append(dict(dataset=entry['id'],sample_before=int(boundary-1),source_csv_row_before=int(boundary+1),
                               sample_after=int(boundary),source_csv_row_after=int(boundary+2),
                               counter_before=float(before),counter_after=float(after),
                               raw_counter_change=float(after-before),action='Start new analysis segment; preserve values'))
        for channel in range(6):
            x = signal[:,channel]
            finite_x = x[np.isfinite(x)]
            statistics.append(dict(dataset=entry['id'],channel=CHANNELS[channel],position=config['channel_positions'][channel],
                                   valid_samples=len(finite_x),mean=float(np.mean(finite_x)),median=float(np.median(finite_x)),
                                   std=float(np.std(finite_x,ddof=1)),rms=float(np.sqrt(np.mean(finite_x**2))),
                                   minimum=float(np.min(finite_x)),maximum=float(np.max(finite_x)),mad=float(mad[channel]),
                                   p01=float(np.percentile(finite_x,1)),p99=float(np.percentile(finite_x,99)),
                                   flagged_amplitude_samples=int(extreme[:,channel].sum()),
                                   flagged_amplitude_fraction=float(np.mean(extreme[:,channel])),
                                   min_value_occurrences=int((finite_x==finite_x.min()).sum()),
                                   max_value_occurrences=int((finite_x==finite_x.max()).sum())))
        valid_signal = signal[np.isfinite(signal).all(axis=1)]
        corr = np.corrcoef(valid_signal.T)
        for a in range(6):
            for b in range(a+1,6):
                pairs.append(dict(dataset=entry['id'],channel_a=CHANNELS[a],channel_b=CHANNELS[b],correlation=float(corr[a,b])))
        frequency,power,count = welch_exported(signal,ranges)
        if power is not None:
            for channel in range(6):
                peak = 1+int(np.argmax(power[1:,channel]))
                peaks.append(dict(dataset=entry['id'],channel=CHANNELS[channel],position=config['channel_positions'][channel],
                                  peak_cycles_per_sample=float(frequency[peak]),peak_hz_assuming_rate=float(frequency[peak]*rate),
                                  assumed_sample_rate_hz=rate,welch_windows=count,interpretation='Exported-signal peak; source/filter/physiological cause unverified'))
        for a,b in ranges:
            for start in range(a,b-config['window_samples']+1,config['window_samples']):
                block = signal[start:start+config['window_samples']]
                for channel in range(6):
                    x = block[:,channel]
                    windows.append(dict(dataset=entry['id'],channel=CHANNELS[channel],segment_id=int(segments[start]),
                                        start_sample=start,end_sample_exclusive=start+len(block),
                                        rms=float(np.sqrt(np.mean(x*x))),mean=float(np.mean(x)),
                                        std=float(np.std(x,ddof=1)),flat=bool(np.ptp(x)==0)))
        for operation,changed,note in [
                ('Preserve source snapshot',0,'Byte-for-byte copy with SHA-256; original Downloads file untouched'),
                ('Numeric validation',int(invalid.sum()),'Nonfinite/unparseable cells become blank in annotated copy only; no affected cells in current inputs'),
                ('Counter segmentation',len(boundaries),'Boundary flags only; not inferred clock time or proven packet loss'),
                ('Amplitude review flags',int(extreme.any(axis=1).sum()),'Within-file/channel median/MAD threshold; all flagged values retained'),
                ('Signal transformation',0,'No new filters, unit conversion, rereferencing, normalization or interpolation'),
                ('Row removal',0,'All source rows retained in original order')]:
            logs.append(dict(dataset=entry['id'],operation=operation,affected_or_flagged_count=changed,note=note))
        rec = dict(**entry,sha256=sha256(snapshot),rows=len(frame),values=signal,boundaries=boundaries,
                   ranges=ranges,corr=corr,frequency=frequency,psd=power)
        per_file_figures(rec,figures,config)
        records.append(rec)
        print(f'Analyzed {entry["id"]}: {len(frame):,} rows, {len(boundaries)} counter break(s)',flush=True)
    stats = pd.DataFrame(statistics)
    window_frame = pd.DataFrame(windows)
    comparison_figures(records,stats,window_frame,figures,config)
    total = sum(r['rows'] for r in summary)
    findings = summarize_findings(summary,pairs,peaks)
    result = dict(generated_utc=datetime.now(timezone.utc).isoformat(),configuration=config,total_rows=total,
                  quality_summary=summary,channel_statistics=statistics,counter_events=events,
                  cleaning_log=logs,correlation_pairs=pairs,spectral_peaks=peaks,findings=findings,
                  recordings=[{k:v for k,v in r.items() if k in ('id','filename','condition','sha256','rows')} for r in records])
    for name,rows in [('quality_summary',summary),('channel_statistics',statistics),('counter_events',events),
                      ('cleaning_log',logs),('window_statistics',windows),('correlation_pairs',pairs),('spectral_peaks',peaks)]:
        pd.DataFrame(rows).to_csv(reports/f'{name}.csv',index=False)
    (reports/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    (reports/'eda_report.html').write_text(report_html(result,root),encoding='utf-8')
    (raw_dir/'manifest.json').write_text(json.dumps(result['recordings'],indent=2),encoding='utf-8')
    (cleaned_dir/'metadata.json').write_text(json.dumps({'configuration':config,'cleaning':'Annotation only; all finite numeric signal values preserved exactly; all rows retained','source_manifest':result['recordings']},indent=2),encoding='utf-8')
    print(f'Finished: {total:,} samples; {len(list(figures.glob("*.png")))} figures; report {reports/"eda_report.html"}',flush=True)
    return result


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,help='Defaults to Downloads; preserved local snapshots work if originals are unavailable')
    args = parser.parse_args()
    run_analysis(source_dir=args.source_dir)
