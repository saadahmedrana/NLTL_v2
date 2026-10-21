#!/usr/bin/env python3
"""Plot behavioural accuracy against median requirement-run time."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter

# Shared 50-requirement full-repair sample.
# Requirement-macro behavioural accuracy on the retained 373-case set.
DATA = [
    {
        'model': 'GPT-5.6 Luna',
        'median_s': 49.935,
        'accuracy_pct': 72.03246753246754,
        'colour': '#087C82',
        'marker': 'o',
    },
    {
        'model': 'GPT-5.6 Sol',
        'median_s': 43.898,
        'accuracy_pct': 82.19343434343435,
        'colour': '#208262',
        'marker': 's',
    },
    {
        'model': 'Gemini 3.5 Flash',
        'median_s': 64.560,
        'accuracy_pct': 73.53701298701299,
        'colour': '#E2B85B',
        'marker': '^',
    },
    {
        'model': 'GPT-OSS 120B',
        'median_s': 59.0075,
        'accuracy_pct': 47.04191919191919,
        'colour': '#BE4C44',
        'marker': 'D',
    },
]
EVALUATION_CASE_COUNT = 373
ACCURACY_SOURCE = (
    'Retained 373-case behavioural evaluation ledger for the shared 50-requirement '
    'full-repair model comparison; requirement macro accuracy computed with no verdicts as zero credit.'
)


def validate_data():
    if not isinstance(EVALUATION_CASE_COUNT, int) or EVALUATION_CASE_COUNT <= 0:
        raise SystemExit('\nEVALUATION_CASE_COUNT must be a positive integer.')
    if not ACCURACY_SOURCE:
        raise SystemExit('\nACCURACY_SOURCE is empty. Provide the retained behavioural-results source.')
    for row in DATA:
        value = row['accuracy_pct']
        if value is None or not math.isfinite(value) or not (0 <= value <= 100):
            raise SystemExit(f"\nInvalid accuracy value for {row['model']}: {value!r}")


def make_figure(width_mm: float, single: bool):
    # Keep physical font sizes and deliberately reserve space for the legend
    # and two-line y title; do not crop or rescale the exported canvas.
    height_mm = 84.0 if single else 90.0
    font_size = 8.0 if single else 9.0
    plt.rcParams.update({
        'font.family': 'serif', 'font.serif': ['DejaVu Serif'],
        'font.size': font_size, 'axes.labelsize': font_size,
        'xtick.labelsize': font_size, 'ytick.labelsize': font_size,
        'figure.facecolor': 'white', 'axes.facecolor': 'white',
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
    })
    fig, ax = plt.subplots(figsize=(width_mm / 25.4, height_mm / 25.4))
    fig.subplots_adjust(
        left=22.0 / width_mm, right=1.0 - 4.5 / width_mm,
        bottom=14.5 / height_mm, top=1.0 - 21.0 / height_mm,
    )
    # Put labels inside open grid cells, away from markers and plot edges.
    label_positions = (
        [(49.935, 76.7), (49.5, 85.7), (69.8, 77.0), (59.0075, 53.0)]
        if single else
        [(49.935, 75.8), (47.0, 85.5), (67.0, 77.0), (59.0075, 53.0)]
    )
    for row, position in zip(DATA, label_positions):
        ax.scatter(
            row['median_s'], row['accuracy_pct'], s=42 if single else 55,
            color=row['colour'], marker=row['marker'], edgecolors='black',
            linewidths=0.5, zorder=3, label=row['model'],
        )
        ax.annotate(
            f"{row['accuracy_pct']:.1f}%",
            (row['median_s'], row['accuracy_pct']), xytext=position,
            textcoords='data', ha='center', va='center',
            fontsize=font_size, color='#263B47', zorder=4,
        )

    ax.set_xlabel('Median runtime (s)', labelpad=6)
    ax.set_ylabel('Macro behavioural\naccuracy (%)', labelpad=7)
    ax.grid(True, linestyle='--', linewidth=0.6, alpha=0.4)
    ax.set_xlim(35, 75)
    ax.set_ylim(30, 100)
    ax.set_xticks(range(35, 76, 10))
    ax.set_yticks(range(30, 101, 10))
    ax.xaxis.set_major_formatter(FormatStrFormatter('%d'))
    ax.yaxis.set_major_formatter(FormatStrFormatter('%d'))
    ax.set_axisbelow(True)
    fig.legend(
        *ax.get_legend_handles_labels(), loc='upper center',
        bbox_to_anchor=(0.5, 1.0 - 3.0 / height_mm), ncol=2,
        frameon=False, fontsize=7.1 if single else 8.5,
        handlelength=1.1, handletextpad=0.45, columnspacing=1.1,
        labelspacing=0.65, borderaxespad=0,
    )
    return fig, ax


def save_outputs(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        'source': ACCURACY_SOURCE,
        'case_count': EVALUATION_CASE_COUNT,
        'sample': 'shared_50_requirement_full_repair',
        'data': DATA,
    }
    (output_dir / 'accuracy_runtime_data.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')

    with (output_dir / 'accuracy_runtime_data.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['model', 'median_s', 'accuracy_pct'])
        for row in DATA:
            writer.writerow([row['model'], row['median_s'], row['accuracy_pct']])

    caption = (
        'Behavioural accuracy versus median requirement-run time for the shared 50-requirement full-repair sample. '
        'Each point represents one model on the retained 373-case set. Accuracy is macro-averaged over requirement-level '
        'outcomes with missing outputs and execution failures scored as zero credit. Median runtime is the recorded '
        'requirement-run time in seconds.'
    )
    (output_dir / 'figure_caption.txt').write_text(caption + '\n', encoding='utf-8')

    latex = (
        '\\begin{figure}[t]\n'
        '\\centering\n'
        '\\includegraphics[width=\\linewidth]{Accuracy_vs_Median_Runtime.pdf}\n'
        '\\caption{Behavioural accuracy versus median requirement-run time for the shared 50-requirement full-repair sample. '
        'Accuracy is macro-averaged over requirement-level outcomes with missing outputs and execution failures scored as zero credit.}\\label{fig:accuracy_runtime}\n'
        '\\end{figure}\n'
    )
    (output_dir / 'figure_latex_snippet.tex').write_text(latex, encoding='utf-8')

    for name, width_mm, single in [('single_column', 78.0, True), ('full_width', 164.5, False)]:
        variant_dir = output_dir / name
        variant_dir.mkdir(parents=True, exist_ok=True)
        fig, _ = make_figure(width_mm, single)
        for ext in ('pdf', 'png', 'svg'):
            fig.savefig(variant_dir / f'Accuracy_vs_Median_Runtime.{ext}', dpi=300)
        plt.close(fig)

    print(f'Exported accuracy/runtime figures to: {output_dir}')
    print(f'Accuracy source: {ACCURACY_SOURCE}')
    print(f'Case count used: {EVALUATION_CASE_COUNT}')


def main():
    validate_data()
    out_dir = Path(__file__).resolve().parent / 'outputs' / ('accuracy_runtime_figure_' + __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    save_outputs(out_dir)


if __name__ == '__main__':
    main()
