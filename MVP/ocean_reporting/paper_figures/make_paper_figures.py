#!/usr/bin/env python3
"""Reproduce the agreed manuscript figures. Requires Python 3.9+ and matplotlib.

Run: python make_paper_figures.py --output-dir outputs/paper_figures
Optional: --data-dir PATH (main_results.csv, manual_review.csv, models.csv).
Embedded defaults are an explicit snapshot, not an Excel extraction routine.
"""
import argparse
import csv
import hashlib
import json
import math
import platform
import shutil
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator, PercentFormatter

# Colourblind-friendly solid colours, reinforced by position and direct labels.
BLUE = '#0072B2'
ORANGE = '#D55E00'
INK = '#243442'
GREY = '#BBC2C7'
MANUAL_COLOURS = ['#0072B2', '#E69F00', '#D55E00', '#D9DDE0']
MODEL_COLOURS = ['#0072B2', '#D55E00', '#009E73', '#CC79A7']

MAIN = [
    {'group': group, 'requirements': n, 'cases': cases, 'condition': condition,
     'accuracy_pct': acc, 'executable_requirements': exe}
    for group, n, cases, acc1, acc2, exe1, exe2 in [
        ('Overall', 268, 2160, 68.468679788397, 76.10910144124009, 221, 246),
        ('Direct static', 190, 1516, 70.0713056564857, 76.37596633129874, 159, 176),
        ('Direct calculation', 41, 337, 62.63532537922782, 79.8349347129835, 31, 38),
        ('Complex readiness', 37, 307, 66.7029667029667, 70.61008811008811, 31, 32),
    ]
    for condition, acc, exe in [('Single-shot', acc1, exe1), ('NLTL_v2', acc2, exe2)]
]
MANUAL = [
    {'condition': 'Single-shot', 'reviewed': 70, 'correct': 22,
     'minor_defect': 5, 'major_defect': 33, 'unassessable': 10},
    {'condition': 'NLTL_v2', 'reviewed': 70, 'correct': 30,
     'minor_defect': 8, 'major_defect': 29, 'unassessable': 3},
]
# Model results are SINGLE-PASS outputs on 50 requirements / 373 cases.
# They are NOT the final outputs of the current syntax-repair pipeline.
MODELS = [
    {'model': model, 'accuracy_pct': accuracy, 'requirements': 50,
     'cases': 373, 'executable_requirements': executable, 'stage': 'Single-pass'}
    for model, accuracy, executable in [
        ('Luna', 72.42, 42), ('Sol', 88.76, 50),
        ('Gemini', 71.14, 45), ('GPT-OSS', 52.06, 34),
    ]
]
GROUPS = ['Overall', 'Direct static', 'Direct calculation', 'Complex readiness']
CONDITIONS = ['Single-shot', 'NLTL_v2']


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_rows(data_dir, name, defaults):
    if data_dir is None:
        return [dict(row) for row in defaults], 'Embedded agreed data snapshot'
    path = (data_dir / name).resolve()
    with path.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f'Empty input: {path}')
    return rows, str(path)


def validate(main, manual, models):
    for rows in [main, models]:
        for row in rows:
            for key in ['requirements', 'cases', 'executable_requirements']:
                value = float(row[key])
                if not value.is_integer() or value < 0:
                    raise ValueError(f'Invalid count {key}: {row}')
                row[key] = int(value)
            row['accuracy_pct'] = float(row['accuracy_pct'])
            if not 0 <= row['accuracy_pct'] <= 100:
                raise ValueError(f'Accuracy must be a percentage: {row}')
            if not 0 < row['requirements'] or not 0 < row['cases']:
                raise ValueError(f'Empty denominator: {row}')
            if row['executable_requirements'] > row['requirements']:
                raise ValueError(f'Coverage exceeds denominator: {row}')
            row['coverage_pct'] = 100 * row['executable_requirements'] / row['requirements']
    keys = [(r['group'], r['condition']) for r in main]
    expected = {(g, c) for g in GROUPS for c in CONDITIONS}
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('main_results.csv needs exactly one row per group/condition.')
    for condition in CONDITIONS:
        overall = next(r for r in main if r['group'] == 'Overall' and r['condition'] == condition)
        categories = [r for r in main if r['group'] != 'Overall' and r['condition'] == condition]
        for key in ['requirements', 'cases', 'executable_requirements']:
            if sum(r[key] for r in categories) != overall[key]:
                raise ValueError(f'Category totals do not match overall {key}.')
        weighted_accuracy = sum(r['accuracy_pct'] * r['requirements'] for r in categories) / overall['requirements']
        if abs(weighted_accuracy - overall['accuracy_pct']) > .02:
            raise ValueError('Overall accuracy is inconsistent with requirement-weighted categories.')
    if len(manual) != 2 or {r['condition'] for r in manual} != set(CONDITIONS):
        raise ValueError('manual_review.csv needs one row per condition.')
    for row in manual:
        for key in ['reviewed', 'correct', 'minor_defect', 'major_defect', 'unassessable']:
            v = float(row[key])
            if not v.is_integer() or v < 0:
                raise ValueError(f'Invalid manual count: {row}')
            row[key] = int(v)
        if row['reviewed'] == 0 or sum(row[k] for k in ['correct', 'minor_defect', 'major_defect', 'unassessable']) != row['reviewed']:
            raise ValueError(f'Manual categories do not sum to reviewed outputs: {row}')
    if len({r['model'] for r in models}) != len(models) or not models:
        raise ValueError('Duplicate or missing models.')
    if len({(r['requirements'], r['cases'], r['stage']) for r in models}) != 1:
        raise ValueError('Models must share the sample and evaluation stage.')
    if any(r['stage'] != 'Single-pass' for r in models):
        raise ValueError('This figure is for single-pass outputs, not semantic-feedback final outputs.')


def style():
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'Liberation Serif', 'DejaVu Serif'],
        'font.size': 10,
        'axes.labelsize': 10, 'axes.titlesize': 10,
        'text.color': INK, 'axes.labelcolor': INK,
        'xtick.color': INK, 'ytick.color': INK,
        'axes.edgecolor': '#89949C', 'axes.linewidth': .7,
        'figure.facecolor': 'white', 'savefig.facecolor': 'white',
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
    })


def clean_axis(ax, percentages=True):
    ax.spines[['top', 'right']].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis='x', color='#E5E9EC', linewidth=.6)
    if percentages:
        ax.set_xlim(0, 100)
        ax.xaxis.set_major_locator(MultipleLocator(20))
        ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))


def export(fig, output, name, dpi):
    for extension in ['pdf', 'svg', 'png']:
        # Preserve physical dimensions: 10-pt labels remain 10 pt at native width.
        fig.savefig(output / f'{name}.{extension}', dpi=dpi)
    plt.close(fig)


def main_chart(rows, output, dpi):
    fig, axes = plt.subplots(1, 2, figsize=(6.48, 4.3), sharey=True)
    fig.subplots_adjust(left=.245, right=.95, bottom=.15, top=.80, wspace=.20)
    positions = [0, 1.35, 2.35, 3.35]
    lookup = {(r['group'], r['condition']): r for r in rows}
    for ax, metric, title in zip(axes, ['accuracy_pct', 'coverage_pct'],
                                  ['(a) Accuracy', '(b) Executable coverage']):
        for condition, offset, colour, hatch in [
            ('Single-shot', -.18, BLUE, ''), ('NLTL_v2', .18, ORANGE, '')]:
            values = [lookup[(g, condition)][metric] for g in GROUPS]
            ys = [y + offset for y in positions]
            ax.barh(ys, values, height=.30, color=colour, hatch=hatch,
                    edgecolor='white', linewidth=.6)
            for y, value in zip(ys, values):
                x, align, colour_text = value - 2, 'right', 'white'
                ax.text(x, y, f'{value:.2f}', va='center', ha=align,
                        fontsize=10, color=colour_text)
        ax.set_title(title, loc='left', pad=13)
        ax.set_xlabel('Accuracy (%)' if metric == 'accuracy_pct' else 'Coverage (%)')
        clean_axis(ax)
        ax.axhline(.68, color='#CBD2D7', linewidth=.7)
    axes[0].set_yticks(positions, [f'{g}\n(n = {lookup[(g, CONDITIONS[0])]["requirements"]})' for g in GROUPS])
    axes[0].invert_yaxis()
    handles = [Patch(facecolor=BLUE, label='Single-shot'),
               Patch(facecolor=ORANGE, edgecolor='white', label='NLTL_v2')]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.59, .98),
               ncol=2, frameon=False)
    export(fig, output, '01_main_results', dpi)


def table_alternative(rows, output, dpi):
    lookup = {(r['group'], r['condition']): r for r in rows}
    cells = []
    for group in GROUPS:
        single, pipeline = [lookup[(group, c)] for c in CONDITIONS]
        cells.append([group] + [f'{r[m]:.2f}%' for m in ['accuracy_pct', 'coverage_pct']
                                for r in [single, pipeline]])
    fig, ax = plt.subplots(figsize=(6.48, 2.7))
    fig.subplots_adjust(left=.02, right=.98, bottom=.05, top=.95)
    ax.axis('off')
    table = ax.table(cellText=cells, colLabels=['Requirement\ngroup', 'Single-shot\naccuracy',
        'NLTL_v2\naccuracy', 'Single-shot\ncoverage', 'NLTL_v2\ncoverage'],
        colWidths=[.27, .18, .18, .18, .19], cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for (row, col), cell in table.get_celld().items():
        cell.set_height(.20 if row == 0 else .15)
        cell.set_edgecolor('#E0E5E8')
        cell.set_linewidth(.6)
        if row == 0:
            cell.set_facecolor('#EAF0F3')
            cell.get_text().set_weight('bold')
        if col == 0:
            cell.get_text().set_ha('left')
    for i, group in enumerate(GROUPS, 1):
        for metric, columns in [('accuracy_pct', (1, 2)), ('coverage_pct', (3, 4))]:
            values = [lookup[(group, c)][metric] for c in CONDITIONS]
            if abs(values[0] - values[1]) > 1e-10:
                winner = columns[int(values[1] > values[0])]
                table[i, winner].set_facecolor('#E0F0E5')
                table[i, winner].get_text().set_weight('bold')
    export(fig, output, '01_main_results_table_alternative', dpi)


def manual_chart(rows, output, dpi):
    rows = [next(r for r in rows if r['condition'] == c) for c in CONDITIONS]
    fig, ax = plt.subplots(figsize=(6.48, 2.9))
    fig.subplots_adjust(left=.17, right=.98, bottom=.24, top=.70)
    categories = ['correct', 'minor_defect', 'major_defect', 'unassessable']
    names = ['Correct', 'Minor defect', 'Major defect', 'Unassessable']
    hatches = ['', '', '', '']
    for i, row in enumerate(rows):
        left = 0
        for category, colour, hatch in zip(categories, MANUAL_COLOURS, hatches):
            count = row[category]
            width = 100 * count / row['reviewed']
            ax.barh(i, width, left=left, height=.48, color=colour,
                    hatch=hatch, edgecolor='white', linewidth=1)
            if count:
                ax.text(left + width/2, i, str(count), ha='center', va='center',
                        color='white' if category in ['correct', 'major_defect'] else INK,
                        fontsize=10, weight='bold',
                        bbox={'facecolor': colour, 'edgecolor': 'none', 'pad': .7})
            left += width
    ax.set_yticks(range(len(rows)), [f'{r["condition"]}\n(n = {r["reviewed"]})' for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel('Share of reviewed requirements (%)')
    clean_axis(ax)
    fig.legend(handles=[Patch(facecolor=c, hatch=h, edgecolor='white', label=n)
                        for c, h, n in zip(MANUAL_COLOURS, hatches, names)],
               loc='upper center', bbox_to_anchor=(.55, .98), ncol=4,
               frameon=False, columnspacing=1.2, handlelength=1.5)
    export(fig, output, '02_manual_bars_alternative', dpi)


def manual_pies(rows, output, dpi):
    rows = [next(r for r in rows if r['condition'] == c) for c in CONDITIONS]
    fig, axes = plt.subplots(1, 2, figsize=(6.48, 3.8))
    fig.subplots_adjust(left=.05, right=.95, bottom=.05, top=.70, wspace=.25)
    categories = ['correct', 'minor_defect', 'major_defect', 'unassessable']
    for ax, row in zip(axes, rows):
        counts = [row[k] for k in categories]
        wedges, _ = ax.pie(counts, colors=MANUAL_COLOURS, startangle=90,
                           counterclock=False,
                           wedgeprops={'edgecolor': 'white', 'linewidth': 1.4})
        for i, (wedge, count) in enumerate(zip(wedges, counts)):
            if not count:
                continue
            angle = math.radians((wedge.theta1 + wedge.theta2) / 2)
            x, y = math.cos(angle), math.sin(angle)
            pct = 100 * count / row['reviewed']
            label = f'{count}\n({pct:.1f}%)'
            if pct >= 15:
                ax.text(.63*x, .63*y, label, ha='center', va='center', fontsize=10,
                        color='white' if i in [0, 2] else INK)
            else:
                ax.annotate(label, (x*.93, y*.93), xytext=(x*1.28, y*1.28),
                            ha='left' if x > 0 else 'right', va='center', fontsize=10,
                            arrowprops={'arrowstyle': '-', 'color': '#7B858C', 'lw': .8})
        ax.set_title(f'{row["condition"]} (n = {row["reviewed"]})', pad=20)
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.35, 1.35)
    fig.legend(handles=[Patch(facecolor=c, label=n) for c, n in zip(MANUAL_COLOURS,
               ['Correct', 'Minor defect', 'Major defect', 'Unassessable'])],
               loc='upper center', bbox_to_anchor=(.5, .98), ncol=2,
               frameon=False, columnspacing=2)
    export(fig, output, '02_manual_review', dpi)


def model_scatter(rows, output, dpi):
    fig, ax = plt.subplots(figsize=(3.07, 3.3))
    fig.subplots_adjust(left=.24, right=.94, bottom=.18, top=.95)
    markers = ['o', 's', '^', 'D']
    # The coverage axis intentionally starts at 40%; this is a scatter, not bars.
    ax.set_xlim(40, 103)
    ax.set_ylim(0, 100)
    ax.xaxis.set_major_locator(MultipleLocator(20))
    ax.yaxis.set_major_locator(MultipleLocator(20))
    ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(color='#E5E9EC', linewidth=.6)
    ax.set_axisbelow(True)
    for i, row in enumerate(rows):
        x, y = row['coverage_pct'], row['accuracy_pct']
        ax.scatter(x, y, s=85, marker=markers[i % len(markers)],
                   color=MODEL_COLOURS[i % len(MODEL_COLOURS)], edgecolors='white', zorder=3)
        # Rightmost label points inward; others sit above/left of their point.
        offset = (-8, 7) if x >= 98 else (-7, 9)
        if row['model'] == 'Gemini':
            offset = (-2, -24)
        ax.annotate(row['model'], (x, y), xytext=offset, textcoords='offset points',
                    ha='right' if offset[0] < 0 else 'left', va='bottom', fontsize=10,
                    color=INK)
    ax.set_xlabel('Executable coverage (%)')
    ax.set_ylabel('Requirement-level accuracy (%)')
    # Direct labels replace a legend. No caption, ranking line, or implied scaling law.
    export(fig, output, '03_model_accuracy_coverage', dpi)


def model_bar_alternative(rows, output, dpi):
    fig, ax = plt.subplots(figsize=(6.48, 3.7))
    fig.subplots_adjust(left=.15, right=.97, bottom=.16, top=.82)
    for metric, offset, colour, hatch, name in [
        ('accuracy_pct', -.18, BLUE, '', 'Accuracy'),
        ('coverage_pct', .18, ORANGE, '', 'Executable coverage')]:
        values = [r[metric] for r in rows]
        ys = [i + offset for i in range(len(rows))]
        ax.barh(ys, values, height=.30, color=colour, hatch=hatch,
                edgecolor='white', label=name)
        for y, value in zip(ys, values):
            inside = value > 93
            ax.text(value - 1 if inside else value + 1, y, f'{value:.2f}',
                    ha='right' if inside else 'left', va='center', fontsize=10,
                    color='white' if inside else INK,
                    bbox={'facecolor': colour, 'edgecolor': 'none', 'pad': .3}
                    if inside else None)
    ax.set_yticks(range(len(rows)), [r['model'] for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel('Performance (%)')
    clean_axis(ax)
    fig.legend(*ax.get_legend_handles_labels(), loc='upper center',
               bbox_to_anchor=(.55, 1), ncol=2, frameon=False)
    export(fig, output, '03_model_bars_alternative', dpi)


def latex_tables(main_rows, manual_rows, output):
    lookup = {(r['group'], r['condition']): r for r in main_rows}
    main_lines = [r'% Requires booktabs and \usepackage[table]{xcolor}.',
                  r'% Add the table environment, caption and label in your manuscript.',
                  r'\begin{tabular}{lrrrr}', r'\toprule',
                  r'Requirement group & \shortstack{Single-shot\\accuracy} & \shortstack{NLTL\_v2\\accuracy} & \shortstack{Single-shot\\coverage} & \shortstack{NLTL\_v2\\coverage} \\',
                  r'\midrule']
    for group in GROUPS:
        cells = [group]
        for metric in ['accuracy_pct', 'coverage_pct']:
            values = [lookup[(group, c)][metric] for c in CONDITIONS]
            for value in values:
                cell = f'{value:.2f}' + r'\%'
                if value == max(values) and values[0] != values[1]:
                    cell = r'\cellcolor{green!10}\textbf{' + cell + '}'
                cells.append(cell)
        main_lines.append(' & '.join(cells) + r' \\')
    main_lines += [r'\bottomrule', r'\end{tabular}']
    (output / 'main_results_table.tex').write_text('\n'.join(main_lines)+'\n', encoding='utf-8')
    manual_lines = [r'% Requires booktabs. Add your own table environment/caption.',
                    r'\begin{tabular}{lrrrrr}', r'\toprule',
                    r'Condition & Reviewed & Correct & Minor defect & Major defect & Unassessable \\', r'\midrule']
    for condition in CONDITIONS:
        row = next(r for r in manual_rows if r['condition'] == condition)
        cells = [condition.replace('_', r'\_')] + [str(row[k]) for k in
                 ['reviewed', 'correct', 'minor_defect', 'major_defect', 'unassessable']]
        manual_lines.append(' & '.join(cells) + r' \\')
    manual_lines += [r'\bottomrule', r'\end{tabular}']
    (output / 'manual_review_table.tex').write_text('\n'.join(manual_lines)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/paper_figures'))
    parser.add_argument('--data-dir', type=Path, help='Optional directory of replacement plotting CSVs')
    parser.add_argument('--dpi', type=int, default=600)
    args = parser.parse_args()
    if args.dpi < 100:
        parser.error('--dpi must be at least 100')
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sources = {}
    datasets = []
    for filename, defaults in [('main_results.csv', MAIN), ('manual_review.csv', MANUAL), ('models.csv', MODELS)]:
        rows, source = load_rows(args.data_dir, filename, defaults)
        datasets.append(rows)
        sources[filename] = source
    main_rows, manual_rows, model_rows = datasets
    validate(*datasets)
    style()
    main_chart(main_rows, output, args.dpi)
    table_alternative(main_rows, output, args.dpi)
    manual_chart(manual_rows, output, args.dpi)
    manual_pies(manual_rows, output, args.dpi)
    model_scatter(model_rows, output, args.dpi)
    model_bar_alternative(model_rows, output, args.dpi)
    latex_tables(main_rows, manual_rows, output)
    used = output / 'plot_data'
    used.mkdir(exist_ok=True)
    for filename, rows in zip(sources, datasets):
        write_csv(used / filename, rows)
    manifest = {'python': platform.python_version(), 'matplotlib': matplotlib.__version__,
                'script': str(Path(__file__).resolve()), 'input_sources': sources,
                'output_directory': str(output), 'model_stage': 'Single-pass',
                'data_precision': 'Main accuracy uses the verified full-precision summaries; model accuracy is the agreed two-decimal snapshot.',
                'files': {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'run_manifest.json'}}
    (output / 'run_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    lines = ['# Figure data summary', '', 'Accuracy averages the fraction of correct cases for each requirement.',
             'Unsuccessful outputs receive no accuracy credit.',
             'Coverage counts requirements with a completed verdict for every assigned case, regardless of correctness.',
             'Manual segment labels are counts; segment widths are percentages of the reviewed sample.',
             'Models are single-pass outputs on a separate common sample, not final NLTL_v2 outputs.', '',
             '| Group | Condition | Accuracy (%) | Coverage (%) | Requirements | Cases |',
             '|---|---|---:|---:|---:|---:|']
    lines += [f'| {r["group"]} | {r["condition"]} | {r["accuracy_pct"]:.2f} | {r["coverage_pct"]:.2f} | {r["requirements"]} | {r["cases"]} |' for r in main_rows]
    lines += ['', '| Model | Stage | Accuracy (%) | Coverage (%) | Requirements | Cases |',
              '|---|---|---:|---:|---:|---:|']
    lines += [f'| {r["model"]} | {r["stage"]} | {r["accuracy_pct"]:.2f} | {r["coverage_pct"]:.2f} | {r["requirements"]} | {r["cases"]} |' for r in model_rows]
    (output / 'data_summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    archive = shutil.make_archive(str(output), 'zip', root_dir=output)
    print('\n'.join(lines))
    print(f'\nFigures and plotted data: {output}\nShareable ZIP: {archive}')


if __name__ == '__main__':
    main()
