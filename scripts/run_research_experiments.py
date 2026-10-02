"""Separate, reproducible software research: python -m scripts.run_research_experiments."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mne
import numpy as np
import pandas as pd
from src.models.fbcsp import load_subject_fbcsp
from src.models.phase1_config import load_phase1_config
from src.models.research_evaluation import evaluate_epochs, run_split, threshold_metrics
from src.models.train_csp_lda import CHANNELS, build_pipeline, load_subject
from src.reporting.experiments import export_experiment, freeze_hashes, metric_summary

MONTAGES = {
    'baseline': CHANNELS,
    'anterior_midline': ('FC3', 'FC4', 'C3', 'C4', 'Cz', 'FCz'),
    'posterior_midline': ('CP3', 'CP4', 'C3', 'C4', 'Cz', 'CPz'),
    'central_wide': ('C1', 'C2', 'C3', 'C4', 'C5', 'C6'),
    'frontal_nearby': ('FC1', 'FC2', 'FC3', 'FC4', 'C3', 'C4'),
    'posterior_nearby': ('CP1', 'CP2', 'CP3', 'CP4', 'C3', 'C4'),
}
BANDS = {'8-12': (8., 12.), '12-30': (12., 30.), '8-20': (8., 20.), '8-30': (8., 30.)}
METRICS = ['accuracy', 'balanced_accuracy', 'f1', 'mcc']
CM = ['cm_11', 'cm_12', 'cm_21', 'cm_22']


def protocol(experiment, **extra):
    config = load_phase1_config(ROOT / 'configs/phase1_config.yaml')
    return {**config, 'experiment': experiment, 'dataset': 'PhysioNet EEGMMIDB 1.0.0',
            'source_root': 'data/', 'baseline': None,
            'evaluation': 'Within-subject leave-one-run-out; CSP and LDA fit on two runs only',
            'f1_positive_label': 'LEFT=1', 'confusion_order': 'rows actual, columns predicted; LEFT, RIGHT',
            'frozen_phase1_changed': False, **extra}


def save_plot(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def subject_table(folds, group=None):
    keys = ([group] if group else []) + ['subject']
    means = folds.groupby(keys, sort=False)[METRICS].mean()
    means['run_accuracy_std'] = folds.groupby(keys, sort=False).accuracy.std(ddof=1)
    return means.join(folds.groupby(keys, sort=False)[CM].sum()).reset_index()


def analyze_frozen():
    source = ROOT / 'results/phase1/results.json'
    payload = json.loads(source.read_text(encoding='utf-8'))
    folds = pd.DataFrame(payload['folds'])
    subjects = subject_table(folds)
    folder = ROOT / 'results/analysis'; plots = folder / 'plots'
    confusion = pd.DataFrame([dict(zip(CM, folds[CM].sum().astype(int)))])
    export_experiment(folder, protocol('Frozen Phase-1 descriptive analysis', source_file=str(source.relative_to(ROOT))),
                      {'subject_metrics': subjects, 'fold_analysis': folds, 'confusion_summary': confusion},
                      'Descriptive aggregation of stored fold values only; no model fitting or replacement of frozen metrics.',
                      {'stored_summary': payload.get('summary', payload.get('overall', {}))})
    for metric, ylim in (('accuracy', (0, 1)), ('mcc', (-1, 1))):
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.bar(subjects.subject, subjects[metric], color='#285977')
        ax.set(title=f'Frozen Phase 1: subject {metric}', ylabel=metric, ylim=ylim)
        save_plot(fig, plots / f'subject_{metric}.png')
    fig, ax = plt.subplots(figsize=(10, 4))
    pivot = folds.pivot(index='subject', columns='test_run', values='accuracy')
    pivot.plot.bar(ax=ax, ylim=(0, 1), ylabel='Accuracy', title='Held-out run accuracy')
    save_plot(fig, plots / 'fold_accuracy.png')
    fig, ax = plt.subplots(figsize=(4, 4))
    matrix = folds[CM].sum().to_numpy().reshape(2, 2)
    ax.imshow(matrix, cmap='Blues'); ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=['LEFT', 'RIGHT'], yticklabels=['LEFT', 'RIGHT'], xlabel='Predicted', ylabel='Actual', title='Frozen aggregate confusion')
    for (i, j), value in np.ndenumerate(matrix):
        ax.text(j, i, str(value), ha='center', va='center')
    save_plot(fig, plots / 'confusion_summary.png')
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.errorbar(subjects.subject, subjects.accuracy, yerr=subjects.run_accuracy_std, fmt='o', capsize=4, color='#285977')
    ax.set(ylim=(0, 1.1), ylabel='Accuracy (mean ± SD over three runs)', title='Run variability and subject variability')
    save_plot(fig, plots / 'subject_variability.png')
    best = subjects.loc[subjects.accuracy.idxmax()]; worst = subjects.loc[subjects.accuracy.idxmin()]
    lines = ['# Frozen Phase-1 descriptive analysis', '',
             'All fold values and confusion counts were loaded from `results/phase1/results.json`. No fitting, tuning, or frozen-value rewriting occurred.', '',
             f'Best subject: {best.subject}, {best.accuracy:.2%}; worst: {worst.subject}, {worst.accuracy:.2%}.',
             f'Across ten subject mean accuracies: mean {subjects.accuracy.mean():.6f}, sample SD {subjects.accuracy.std(ddof=1):.6f}.',
             f'Across thirty folds: mean {folds.accuracy.mean():.6f}, sample SD {folds.accuracy.std(ddof=1):.6f}.', '',
             'These SDs describe different units. Three folds from the same subject are not independent; SD is not a confidence interval.',
             'F1 is binary with LEFT positive; MCC can range from −1 to 1. Subject metrics average the three stored fold scores. Summed confusion matrices are counts, not re-scored pooled metrics.', '',
             'Run-to-run sample SD is in `subject_metrics.csv`; all per-run metrics and confusion cells are in `fold_analysis.csv`.', '',
             '![Accuracy](plots/subject_accuracy.png)', '![MCC](plots/subject_mcc.png)',
             '![Fold accuracy](plots/fold_accuracy.png)', '![Confusion](plots/confusion_summary.png)', '![Variability](plots/subject_variability.png)']
    (folder / 'analysis_summary.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(f'Frozen analysis: best {best.subject} {best.accuracy:.2%}; worst {worst.subject} {worst.accuracy:.2%}', flush=True)


def run_comparison(kind):
    choices = MONTAGES if kind == 'channel_selection' else BANDS
    folds, predictions, skipped = [], [], []
    config = protocol('Exploratory '+kind, candidates=choices)
    for name, setting in choices.items():
        for subject in config['subjects']:
            try:
                with mne.use_log_level('ERROR'):
                    channels = setting if kind == 'channel_selection' else CHANNELS
                    band = (8., 30.) if kind == 'channel_selection' else setting
                    X, y, groups = load_subject_fbcsp(ROOT/'data', subject, tuple(config['runs']), (band,), tuple(channels))
                    rows, trials = evaluate_epochs(X[:, 0], y, groups, subject, name)
                folds.extend(rows); predictions.extend(trials)
                print(f'{kind} {name} {subject}: {np.mean([r["accuracy"] for r in rows]):.2%}', flush=True)
            except FileNotFoundError as exc:
                skipped.append({'variant': name, 'subject': subject, 'reason': str(exc)})
    frame = pd.DataFrame(folds)
    if frame.empty:
        raise RuntimeError('No subject data available for experiment.')
    subjects = subject_table(frame, 'variant')
    ranking = metric_summary(frame)
    # Ranking is over all subject means, never one selected subject.
    for metric in METRICS:
        values = subjects.groupby('variant')[metric]
        ranking[f'{metric}_subject_mean'] = ranking.variant.map(values.mean())
        ranking[f'{metric}_subject_std'] = ranking.variant.map(values.std(ddof=1))
    ranking['eligible_for_ranking'] = ranking.subjects == len(config['subjects'])
    ranking['setting'] = ranking.variant.map(lambda name: json.dumps(choices[name]))
    ranking = ranking.sort_values(['eligible_for_ranking', 'accuracy_subject_mean', 'variant'], ascending=[False, False, True])
    folder = ROOT/'results'/kind
    export_experiment(folder, config, {'ranking': ranking, 'fold_metrics': frame, 'subject_metrics': subjects,
                      'heldout_predictions': predictions},
                      'Exploratory fixed candidates; selection across ten subject means. No independent confirmation set; Phase 1 stays unchanged.',
                      {'skipped': skipped, 'dispersion': 'metric_std: sample SD over 30 folds; metric_subject_std: sample SD over 10 subject means',
                       'montage_rationale': 'Bilateral C3/C4 motor sites, adjacent frontal/posterior sensorimotor pairs, and central midline sites. Six predefined montages; no exhaustive search.'})
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(ranking.variant, ranking.accuracy_subject_mean, yerr=ranking.accuracy_subject_std, color='#285977', capsize=3)
    ax.set(ylim=(0, 1), ylabel='Mean accuracy ± subject SD', title=kind.replace('_', ' ').title()); ax.tick_params(axis='x', rotation=20)
    save_plot(fig, folder/'plots/comparison.png')
    print(f'{kind} ranking: {ranking.iloc[0].variant} {ranking.iloc[0].accuracy_subject_mean:.6f}', flush=True)
    return frame, predictions


def analyze_confidence():
    source = ROOT/'results/frequency_analysis/heldout_predictions.csv'
    predictions = pd.read_csv(source)
    predictions = predictions[predictions.variant == '8-30']
    thresholds = np.round(np.arange(.50, 1., .05), 2)
    table = threshold_metrics(predictions, thresholds)
    folder = ROOT/'results/confidence_analysis'
    export_experiment(folder, protocol('Held-out confidence and command rejection', thresholds=thresholds.tolist(),
                      prediction_source=str(source.relative_to(ROOT))),
                      {'threshold_metrics': table, 'heldout_predictions': predictions},
                      'Only out-of-fold probabilities from fixed baseline CSP+LDA. UNKNOWN is a rejection, not a learned REST state.',
                      {'false_command_rate_denominator': 'all held-out attempts', 'conditional_false_command_rate_denominator': 'accepted attempts',
                       'probability_calibration': 'LDA predict_proba; not independently calibrated',
                       'selection_warning': 'No threshold is optimized or deployed here. Choosing on these predictions needs independent confirmation.'})
    for metric, label in [('acceptance_rate', 'Acceptance rate'), ('accepted_command_accuracy', 'Accepted-command accuracy'), ('false_command_rate', 'Incorrect accepted / all attempts')]:
        fig, ax = plt.subplots(figsize=(7, 4)); ax.plot(table.threshold, table[metric], 'o-', color='#285977')
        ax.set(xlabel='Confidence threshold', ylabel=label, ylim=(0, 1), title='Held-out command rejection')
        save_plot(fig, folder/'plots'/f'{metric}.png')
    lines = ['# Held-out confidence/rejection analysis', '',
             f'{len(predictions)} predictions: ten subjects, three disjoint held-out runs each. Train/test run identifiers are exported for every trial.', '',
             'Correct accepted = accepted and predicted label equals the imagery annotation. Incorrect accepted = accepted and wrong. Rejected commands have no mapped word/sentence/audio.',
             'False-command rate = incorrect accepted / all attempts. Conditional false-command rate = incorrect accepted / accepted attempts. Accepted-command accuracy = correct accepted / accepted attempts. Zero acceptance yields undefined conditional metrics, exported as null/blank.', '',
             'A higher threshold reduces coverage. It can reduce false commands per attempt while conditional accuracy need not improve monotonically. These probabilities are not a validated measure of user certainty.', '',
             'UNKNOWN is confidence rejection; REST was never trained. No threshold is selected as optimal without a declared cost for wrong commands versus rejection and an independent confirmation set.', '',
             '| Threshold | Accepted | Rejected | Correct accepted | Incorrect accepted | Coverage | Accepted accuracy | False commands/attempt |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in table.itertuples():
        lines.append(f'| {row.threshold:.2f} | {row.accepted_predictions} | {row.rejected_predictions} | {row.correct_accepted} | {row.incorrect_accepted} | {row.acceptance_rate:.2%} | {row.accepted_command_accuracy:.2%} | {row.false_command_rate:.2%} |')
    lines += ['', '![Acceptance](plots/acceptance_rate.png)', '![Accepted accuracy](plots/accepted_command_accuracy.png)', '![False commands](plots/false_command_rate.png)']
    (folder/'summary.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def analyze_csp():
    stored = json.loads((ROOT/'results/phase1/results.json').read_text(encoding='utf-8'))
    subject_scores = subject_table(pd.DataFrame(stored['folds']))
    subjects = list(dict.fromkeys(['S001', subject_scores.loc[subject_scores.accuracy.idxmax(), 'subject'], subject_scores.loc[subject_scores.accuracy.idxmin(), 'subject']]))
    folder = ROOT/'results/csp_analysis'; tables = []; weights = []
    for subject in subjects:
        with mne.use_log_level('ERROR'):
            X, y, groups = load_subject(ROOT/'data', subject)
            train, test = run_split(groups, 'R04')
            model = build_pipeline(); model.fit(X[train], y[train])
            csp = model.named_steps['csp']; features = csp.transform(X[test])
        info = mne.create_info(list(CHANNELS), 160, 'eeg'); info.set_montage('standard_1020')
        fig, axes = plt.subplots(1, 4, figsize=(12, 3))
        limit = float(np.max(np.abs(csp.patterns_[:4])))
        for component, ax in enumerate(axes):
            mne.viz.plot_topomap(csp.patterns_[component], info, axes=ax, show=False, contours=0,
                                names=list(CHANNELS), vlim=(-limit, limit))
            ax.set_title(f'Pattern {component+1}')
            for channel, pattern, filt in zip(CHANNELS, csp.patterns_[component], csp.filters_[component]):
                weights.append({'subject': subject, 'component': component+1, 'channel': channel, 'pattern': float(pattern), 'filter': float(filt), 'test_run': 'R04', 'train_runs': 'R08+R12'})
        fig.suptitle(f'{subject}: two-run fitted CSP patterns (six sensors)')
        save_plot(fig, folder/'plots'/f'{subject}_patterns.png')
        fig, ax = plt.subplots(figsize=(8, 3)); image = ax.imshow(csp.filters_[:4], cmap='RdBu_r', aspect='auto')
        ax.set(xticks=range(6), xticklabels=CHANNELS, yticks=range(4), yticklabels=range(1, 5), xlabel='Input sensor', ylabel='Component', title=f'{subject}: CSP filters'); fig.colorbar(image, ax=ax)
        save_plot(fig, folder/'plots'/f'{subject}_filters.png')
        fig, axes = plt.subplots(1, 4, figsize=(12, 3))
        for component, ax in enumerate(axes):
            ax.boxplot([features[y[test] == label, component] for label in [1, 2]], tick_labels=['LEFT', 'RIGHT'])
            ax.set_title(f'Feature {component+1}'); ax.set_ylabel('Log mean square power')
        fig.suptitle(f'{subject}: R04 held-out feature distributions')
        save_plot(fig, folder/'plots'/f'{subject}_features.png')
        for trial, (label, feature) in enumerate(zip(y[test], features), 1):
            tables.append({'subject': subject, 'trial': trial, 'actual': int(label), 'test_run': 'R04', 'train_runs': 'R08+R12',
                           **{f'feature_{i+1}': float(value) for i, value in enumerate(feature)}})
    export_experiment(folder, protocol('CSP interpretability', subjects=subjects, held_out_run='R04', train_runs=['R08', 'R12']),
                      {'heldout_features': tables, 'spatial_weights': weights},
                      'Descriptive analysis with CSP trained on R08+R12; R04 features are held out. Subject selection uses frozen subject scores.')
    lines = ['# CSP interpretation', '',
             f'Representatives: {", ".join(subjects)}. S001 is the MVP subject; high/low subjects are selected using stored mean fold accuracy. All plots use R08+R12 training and R04 held-out trials.', '',
             'Filters are the rows of the projection matrix: each maps six sensor signals to a component. They are extraction weights and are not anatomical activation maps.',
             'Patterns describe the sensor-space projection of those components. Sparse six-sensor topographic interpolation is illustrative; it is neither source localization nor proof of activity in a named brain structure. Component sign is arbitrary.',
             'Classifier features are the four log mean-square powers returned by the existing CSP transform (average-power mode, log enabled). LDA separates these feature vectors; it does not classify topographic images.',
             'The feature plots show only the fifteen held-out R04 trials. Overlap is expected, especially for low-performing subjects. Visual separation is descriptive; no components or subjects were tuned from these plots.', '',
             'Component order follows the unchanged MNE defaults. Magnitudes/signs across independently fitted subjects are not directly comparable. Sensor patterns and feature distributions can reveal separation or instability, but cannot determine whether residual artifacts drove a component.', '']
    means = pd.DataFrame(tables).groupby(['subject', 'actual']).feature_1.mean()
    contrast = '; '.join(f'{subject} {means.loc[subject, 1]:.4f} / {means.loc[subject, 2]:.4f}' for subject in subjects)
    lines += ['## Observed held-out feature contrast', '',
              f'Mean feature 1 (LEFT / RIGHT): {contrast}. These observations describe this R04 fold only; the boxplots and exported trial values show the spread around each mean. Larger class-mean differences alone do not establish better classification.', '',
              'Pattern colors use one symmetric range per subject across the four components. Red/blue indicate pattern polarity; signs may flip between fits and are not class labels.', '']
    for subject in subjects:
        lines += [f'## {subject}', '', f'![Patterns](plots/{subject}_patterns.png)', f'![Filters](plots/{subject}_filters.png)', f'![Features](plots/{subject}_features.png)', '']
    (folder/'csp_analysis.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def reproduce_phase2():
    from src.models.phase2_evaluation import run_phase2_evaluation
    from scripts.generate_phase2_plots import generate_plots
    folder = ROOT/'results/phase2_reproduction'
    current = run_phase2_evaluation(output_dir=folder)
    old = json.loads((ROOT/'results/phase2/results.json').read_text(encoding='utf-8'))
    rows = []
    for name, summary in current['model_summaries'].items():
        for metric in METRICS:
            observed = summary[metric]['mean']; previous = old['model_summaries'][name][metric]['mean']
            rows.append({'model': name, 'metric': metric, 'historical_mean': previous, 'current_mean': observed, 'difference': observed-previous,
                         'current_fold_std': summary[metric]['std'], 'matches_at_1e_12': bool(abs(observed-previous) <= 1e-12)})
    export_experiment(folder, {'experiment': 'Phase-2 deterministic reproduction', **current['config'],
                      'dataset': 'PhysioNet EEGMMIDB 1.0.0', 'evaluation': 'Within-subject leave-one-run-out', 'historical_source': 'results/phase2/results.json',
                      'plot_seed': 0, 'baseline': None, 'f1_positive_label': 'LEFT=1'},
                      {'comparison': rows, 'current_folds': current['folds']},
                      'Historical Phase-2 outputs retained. FBCSP mutual-information selection and plotting jitter use seed zero.', {'skipped': current['skipped']})
    generate_plots(folder, seed=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', nargs='+', choices=['analysis', 'channels', 'bands', 'confidence', 'csp', 'phase2'],
                        default=['analysis', 'channels', 'bands', 'confidence', 'csp', 'phase2'])
    args = parser.parse_args(); before = freeze_hashes()
    operations = {'analysis': analyze_frozen, 'channels': lambda: run_comparison('channel_selection'),
                  'bands': lambda: run_comparison('frequency_analysis'), 'confidence': analyze_confidence,
                  'csp': analyze_csp, 'phase2': reproduce_phase2}
    for name in args.tasks:
        operations[name]()
        if freeze_hashes() != before:
            raise RuntimeError('Frozen Phase-1 files changed during research execution.')
    print('Research tasks complete; frozen Phase-1 hashes unchanged.', flush=True)


if __name__ == '__main__':
    main()
