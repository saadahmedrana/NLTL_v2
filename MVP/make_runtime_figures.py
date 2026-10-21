#!/usr/bin/env python3
"""Read existing runtime evidence; create figures/tables without rerunning experiments.

Place beside NLTL_Runtime_and_Iterations.xlsx and run: python3 make_runtime_figures.py
Dependencies: python3 -m pip install matplotlib openpyxl
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import mean, median, stdev
import tempfile
from datetime import datetime

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'nltl-runtime-mpl'))
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator
    from openpyxl import load_workbook
except ImportError as exc:
    raise SystemExit('Install dependencies: python3 -m pip install matplotlib openpyxl') from exc

TEAL, RED, GREEN = '#087C82', '#BE4C44', '#208262'
DARK, GREY = '#263B47', '#D5DBDF'
HERE = Path(__file__).resolve().parent


def truth(value):
    return value is True or str(value).strip().lower() in {'true', '1'}


def latex_escape(value):
    text = str(value)
    for src, dst in {
        '\\': r'\textbackslash{}',
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }.items():
        text = text.replace(src, dst)
    return text


def read_runs(path):
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = book['Requirement_Runs']
        iterator = sheet.iter_rows(values_only=True)
        for _ in range(15):
            header = next(iterator)
            if 'Run ID' in header and 'Original experiment' in header:
                break
        else:
            raise ValueError('Cannot locate Requirement_Runs column headers')
        records = [dict(zip(header, row)) for row in iterator if any(v is not None for v in row)]
    finally:
        book.close()
    ids = [r['Run ID'] for r in records]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError('Missing/duplicate run IDs; resolve workbook provenance first')
    return records


def cohort(rows, label, expected):
    if len(rows) != expected or len({r['Requirement ID'] for r in rows}) != expected:
        raise ValueError(f'{label}: expected {expected} distinct requirements; got {len(rows)} rows')
    if len({r['Session ID'] for r in rows}) != 1:
        raise ValueError(f'{label}: multiple sessions selected; specify the experiment cohort explicitly')
    for row in rows:
        value = row.get('Elapsed (s)')
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f'{label}: missing/invalid elapsed time for {row["Run ID"]}')
        if not truth(row.get('Completed')):
            raise ValueError(f'{label}: incomplete run {row["Run ID"]}')
    return rows


def summary(label, rows):
    times = [r['Elapsed (s)'] for r in rows]
    attempts = [r.get('Candidate attempts') for r in rows]
    if any(not isinstance(n, (int, float)) or not math.isfinite(n) or n < 0 for n in attempts):
        raise ValueError(f'{label}: incomplete candidate-attempt evidence')
    return {
        'label': label, 'n': len(rows), 'mean_s': mean(times), 'sd_s': stdev(times),
        'median_s': median(times), 'total_s': sum(times),
        'accepted': sum(truth(r.get('Successful output')) for r in rows),
        'mean_attempts': mean(attempts), 'max_attempts': max(attempts),
        'sessions': sorted({r['Session ID'] for r in rows}),
        'model_roles': sorted({r['Model-role configuration'] for r in rows}),
        'semantic_calls': sum(r.get('Semantic-validator calls') or 0 for r in rows),
        'syntax_repair_calls': sum(r.get('Syntax-repair calls') or 0 for r in rows),
    }


def style():
    plt.rcParams.update({
        'font.family': 'serif', 'font.serif': ['DejaVu Serif'], 'font.size': 8,
        'axes.labelsize': 8, 'axes.titlesize': 9, 'xtick.labelsize': 7.5,
        'ytick.labelsize': 8, 'legend.fontsize': 7.5, 'text.color': '#222222',
        'axes.labelcolor': '#222222', 'xtick.color': '#222222',
        'ytick.color': '#222222', 'pdf.fonttype': 42, 'ps.fonttype': 42,
        'svg.fonttype': 'none', 'figure.facecolor': 'white', 'axes.facecolor': 'white',
    })


def axis(ax, labels, maximum, percentage=False):
    ax.set_xlim(0, maximum)
    ax.set_ylim(-.6, len(labels) - .4)
    ax.set_yticks(list(range(len(labels))), labels)
    ax.invert_yaxis()
    ax.grid(axis='x', color='#E4E9EC', linewidth=.65)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.spines['bottom'].set_color('#93A0A9')
    ax.tick_params(axis='y', length=0)
    if percentage:
        ax.set_xticks([0, 20, 40, 60, 80, 100], [f'{x}%' for x in [0, 20, 40, 60, 80, 100]])
    else:
        ticks = MaxNLocator(nbins=5).tick_values(0, maximum)
        ax.set_xticks([x for x in ticks if 0 <= x <= maximum])


def save(fig, folder, stem):
    fig.set_dpi(300)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for text in fig.findobj(matplotlib.text.Text):
        if text.get_visible() and text.get_text().strip():
            box = text.get_window_extent(renderer)
            canvas = fig.bbox
            if box.x0 < canvas.x0 - 1 or box.y0 < canvas.y0 - 1 or box.x1 > canvas.x1 + 1 or box.y1 > canvas.y1 + 1:
                raise ValueError(f'Text outside figure canvas: {text.get_text()}')
    for ext in ('pdf', 'png', 'svg'):
        fig.savefig(folder / f'{stem}.{ext}', dpi=300)
    plt.close(fig)
    return folder / f'{stem}.pdf'


def main_figure(primary, folder, width, single):
    labels = [s['label'] for s in primary]
    means = [s['mean_s'] for s in primary]
    medians = [s['median_s'] for s in primary]
    max_value = max(max(means), max(medians)) * 1.2 if max(means) or max(medians) else 1.0
    fig, ax = plt.subplots(figsize=(width / 25.4, (66 if single else 90) / 25.4))
    y = list(range(len(labels)))
    ax.barh(y, means, color=TEAL, alpha=.85, height=.42)
    ax.scatter(medians, y, color=RED, s=30, zorder=3)
    axis(ax, labels, max_value)
    ax.set_xlabel('Runtime (s)')
    ax.set_title('Recorded requirement-run time')
    handles = [
        Patch(facecolor=TEAL, label='Mean'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor=RED, markersize=6, label='Median'),
    ]
    ax.legend(handles=handles, loc='upper right', frameon=False)
    fig.subplots_adjust(left=0.35, bottom=0.32)
    return save(fig, folder, 'Figure_8_Runtime')


def model_figure(models, folder, width, single):
    labels = [s['label'] for s in models]
    means = [s['mean_s'] for s in models]
    acceptance = [s['accepted'] / s['n'] * 100 for s in models]
    max_value = max(means) * 1.2 if means else 1.0
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(width / 25.4, (70 if single else 90) / 25.4), constrained_layout=True)
    y = list(range(len(labels)))
    ax1.barh(y, means, color=GREEN, alpha=.85, height=.42)
    ax1.scatter([s['median_s'] for s in models], y, color=RED, s=30, zorder=3)
    axis(ax1, labels, max_value)
    ax1.set_xlabel('Runtime (s)')
    ax1.set_title('Runtime')

    ax2.barh(y, acceptance, color=TEAL, alpha=.85, height=.42)
    ax2.set_xlim(0, 100)
    ax2.set_xticks([0, 25, 50, 75, 100], ['0%', '25%', '50%', '75%', '100%'])
    ax2.set_yticks(y, [''] * len(labels))
    ax2.invert_yaxis()
    ax2.grid(axis='x', color='#E4E9EC', linewidth=.65)
    ax2.set_axisbelow(True)
    ax2.spines[['top', 'right', 'left']].set_visible(False)
    ax2.spines['bottom'].set_color('#93A0A9')
    ax2.set_xlabel('Accepted output (%)')
    for yi, val, count in zip(y, acceptance, [s['accepted'] for s in models]):
        ax2.text(val + 2, yi, f'{count}/{models[0]["n"]}', va='center', ha='left', fontsize=7, color=DARK)
    ax2.set_title('Acceptance')
    return save(fig, folder, 'Figure_9_Model_Runtime_Acceptance')


def write_tables(folder, primary, models):
    header = r'''% Requires booktabs. SD describes variation across requirement runtimes.
\begin{table}[tbp]
\centering
\small
\caption{Recorded runtime for the selected generation run of each workflow on
the same 268 requirements. Completed unsuccessful runs remain included.
Times exclude preparation before the start event and reporting after the finish event.}
\label{tab:recorded_runtime}
\begin{tabular}{@{}lrr@{}}
\toprule
Workflow & Mean $\pm$ SD (s) & Median (s) \\
\midrule
'''
    lines = [f"{latex_escape(s['label'])} & {s['mean_s']:.2f} $\\pm$ {s['sd_s']:.2f} & {s['median_s']:.2f} \\\\" for s in primary]
    (folder/'Table_Main_Runtime.tex').write_text(header+'\n'.join(lines)+
        '\n'+r'\bottomrule'+'\n'+r'\end{tabular}'+'\n'+r'\end{table}'+'\n', encoding='utf-8')
    header = r'''% Recorded candidate attempts are not API/transport retry counts.
\begin{table*}[t]
\centering
\small
\caption{Runtime and generation-stage acceptance on the shared 50-requirement
full-repair sample. Acceptance does not establish behavioural accuracy or
executable coverage. Candidate attempts use the recorded run-final count;
known attempt/terminal-iteration discrepancies remain provisional.}
\label{tab:model_runtime_attempts}
\begin{tabular}{@{}lrrrr@{}}
\toprule
Model & Mean $\pm$ SD (s) & Median (s) & Accepted & Mean attempts \\
\midrule
'''
    lines = [f"{latex_escape(s['label'])} & {s['mean_s']:.2f} $\\pm$ {s['sd_s']:.2f} & {s['median_s']:.2f} & {s['accepted']}/{s['n']} & {s['mean_attempts']:.2f} \\\\" for s in models]
    (folder/'Table_Model_Runtime.tex').write_text(header+'\n'.join(lines)+
        '\n'+r'\bottomrule'+'\n'+r'\end{tabular}'+'\n'+r'\end{table*}'+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, default=HERE/'NLTL_Runtime_and_Iterations.xlsx')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--main-repetition', default='RUN_01')
    args = parser.parse_args()
    path = args.workbook.expanduser().resolve()
    if not path.is_file():
        parser.error(f'Workbook not found: {path}. Place it beside this script or pass --workbook PATH.')
    rows = read_runs(path)
    selected = []
    for experiment, label in [('LUNA_CONTEXTUAL_SINGLESHOT', 'Single-shot'),
                              ('LUNA_NO_SEMANTIC_VALIDATOR', 'NLTL_v2')]:
        selected.append((label, cohort([r for r in rows if r['Original experiment']==experiment
            and r['Repetition']==args.main_repetition], label, 268)))
    if {r['Requirement ID'] for r in selected[0][1]} != {r['Requirement ID'] for r in selected[1][1]}:
        raise ValueError('The main workflows do not use the same requirement IDs')
    model_rows = [('GPT-5.6 Luna', cohort([r for r in rows if r['Original experiment']=='FULL_REPAIR_V2'
                        and truth(r.get('Scaling sample member'))], 'Luna sample', 50))]
    for key, label in [('sol', 'GPT-5.6 Sol'), ('gemini', 'Gemini 3.5 Flash'), ('gpt_oss', 'GPT-OSS 120B')]:
        model_rows.append((label, cohort([r for r in rows if r['Original experiment']=='MODEL_SCALING_FULL_REPAIR_V2_50'
                                         and r['Repetition']==key], label, 50)))
    shared = {r['Requirement ID'] for r in model_rows[0][1]}
    if any({r['Requirement ID'] for r in rs} != shared for _, rs in model_rows):
        raise ValueError('Model samples have different requirement IDs')
    primary = [summary(label, rs) for label, rs in selected]
    models = [summary(label, rs) for label, rs in model_rows]
    discrepancies = [{'model': label, 'run_id': r['Run ID'], 'recorded_attempts': r['Candidate attempts'],
                      'terminal_iteration': r['Terminal recorded iteration']}
                     for label, rs in model_rows for r in rs
                     if r.get('Terminal recorded iteration') is not None
                     and r['Candidate attempts'] != r['Terminal recorded iteration']]
    output = (args.output_dir.expanduser().resolve() if args.output_dir else
              HERE/'outputs'/('runtime_figures_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')))
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise SystemExit('Output directory is not empty. Omit --output-dir or choose a new directory.')
    output.mkdir(parents=True, exist_ok=True)
    style()
    for name, width, single in [('single_column',78.0,True), ('full_width',164.5,False)]:
        target=output/name
        target.mkdir()
        main_figure(primary,target,width,single)
        model_figure(models,target,width,single)
    write_tables(output, primary, models)
    payload = {'workbook': str(path), 'workbook_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'main_repetition': args.main_repetition, 'main': primary, 'models': models,
               'attempt_discrepancies': discrepancies,
               'selected_run_ids': {label:[r['Run ID'] for r in rs] for label,rs in selected+model_rows}}
    (output/'runtime_figure_data.json').write_text(json.dumps(payload,indent=2)+'\n', encoding='utf-8')
    with (output/'runtime_summary.csv').open('w', newline='', encoding='utf-8') as stream:
        keys=['label','n','mean_s','sd_s','median_s','total_s','accepted','mean_attempts','max_attempts']
        writer=csv.DictWriter(stream,fieldnames=['comparison']+keys)
        writer.writeheader()
        for kind, stats in [('Main',primary),('Full-repair model sample',models)]:
            for s in stats: writer.writerow({'comparison':kind, **{k:s[k] for k in keys}})
    notes = '''RECOMMENDED PAPER INSERTIONS

Use Table_Main_Runtime.tex for the two main workflow timings; Figure 8 is optional
if space permits. Use full_width/Figure_9_Model_Runtime_Acceptance.pdf for the
four-model comparison, with Table_Model_Runtime.tex if attempts are discussed.
PDFs are vector artwork. SVGs retain editable text. Do not shrink full-width
artwork into one column; use the supplied single_column variant instead.

FIGURE 8 CAPTION
Recorded requirement-run time for the selected run of each workflow on the
same 268 requirements. Bars show means and diamonds show medians. Completed
unsuccessful runs are included. The interval covers the recorded start and
finish events, excluding initial preparation and final tracker export.

FIGURE 9 CAPTION
Recorded runtime and generation-stage acceptance for four models on the same
50-requirement full-repair sample. (a) Bars show mean recorded requirement-run
time and diamonds show medians. (b) Bar lengths show recorded accepted-output
rates; labels give counts and percentages. All 50 attempted requirements per
model remain included. Acceptance reflects generation-stage checks and does
not establish semantic correctness, behavioural accuracy or executable coverage.

METHODS DETAILS TO ADD
Define recorded requirement-run timing boundaries and hardware/API conditions.
Distinguish the main 268-requirement workflows from the full-repair model sample.
Describe sample selection. Define acceptance and candidate attempts separately
from semantic correctness, syntax repairs and transport retries. SD is spread
across requirement runtimes, not a confidence interval or repeated-run accuracy SD.

EVIDENCE LIMITS
This script does not compute accuracy or executable coverage from generation
acceptance. It does not use historical 2186/381 RDF-case timings as current
2160/373-case evidence. No manual-authoring comparison is inferred.
Recorded model candidate-attempt discrepancies are listed in the JSON export;
resolve them before treating the attempt means as final manuscript results.
The main NLTL_v2 publication label is retained as instructed. Its actual semantic
and syntax-repair call counts are exported in JSON; reconcile the pipeline
description with those counters before submission.
'''
    (output/'Captions_and_Usage.txt').write_text(notes, encoding='utf-8')
    print(f'\nGenerated figures, tables, captions and data in:\n{output}')
    print(f'Model candidate-attempt discrepancies retained: {len(discrepancies)}')
    print('No generation, evaluation, API calls or workbook modifications were performed.')


if __name__ == '__main__':
    main()
