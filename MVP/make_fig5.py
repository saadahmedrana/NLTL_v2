#!/usr/bin/env python3
"""Generate full-width and single-column Figure 5 alternatives.

Run:
    python make_figure5_accuracy_layouts.py
    python make_figure5_accuracy_layouts.py --layout singlecolumn
    python make_figure5_accuracy_layouts.py --outdir PATH

Requires matplotlib.
Reported accuracy values are reproduced, not recalculated.
"""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA = [
    ("Overall", 268, 68.47, 76.11),
    ("Direct static", 190, 70.07, 76.38),
    ("Direct calculation", 41, 62.64, 79.83),
    ("Complex readiness", 37, 66.70, 70.61),
]

WORKFLOWS = [
    ("Single-shot", "#BE4C44", "///"),
    ("NLTL_v2", "#087C82", ""),
]


def make_figure(layout):
    single = layout == "singlecolumn"
    font_size = 7.5 if single else 8.5
    width_mm = 78 if single else 164.5
    height_mm = 96 if single else 88

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["DejaVu Serif"],
        "font.size": font_size,
        "axes.labelsize": font_size,
        "legend.fontsize": font_size,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    })

    fig, ax = plt.subplots(
        figsize=(width_mm / 25.4, height_mm / 25.4)
    )
    fig.subplots_adjust(
        left=0.36 if single else 0.285,
        right=0.94 if single else 0.975,
        bottom=0.14 if single else 0.16,
        top=0.82 if single else 0.84,
    )

    for i, (_, _, baseline, workflow) in enumerate(DATA):
        for j, value in enumerate((baseline, workflow)):
            label, color, hatch = WORKFLOWS[j]
            y = i + (-0.18 if j == 0 else 0.18)

            ax.barh(
                y,
                value,
                height=0.29,
                color=color,
                edgecolor="white",
                linewidth=0.45,
                hatch=hatch,
                label=label if i == 0 else None,
                zorder=3,
            )
            ax.text(
                value + 1.3,
                y,
                f"{value:.2f}",
                va="center",
                fontsize=font_size,
            )

    if single:
        labels = [
            f"{name}\n($n={n}$)"
            for name, n, *_ in DATA
        ]
    else:
        labels = [
            f"{name} ($n={n}$)"
            for name, n, *_ in DATA
        ]

    ax.set_yticks(range(len(DATA)), labels)
    ax.set_ylim(3.55, -0.55)
    ax.set_xlim(0, 100)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("Accuracy (%)", labelpad=6)

    ax.grid(
        axis="x",
        color="#E1E4E6",
        linewidth=0.6,
        zorder=0,
    )
    ax.axhline(
        0.5,
        color="#C6CCD0",
        linewidth=0.65,
        zorder=1,
    )

    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#9AA2A7")
    ax.tick_params(
        axis="y",
        length=0,
        pad=5 if single else 8,
    )
    ax.tick_params(axis="x", length=3, color="#9AA2A7")

    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.40 if single else 0.46, 1.04),
        ncol=1 if single else 2,
        frameon=False,
        handlelength=2,
    )

    # Check labels at the actual output dimensions.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    for text in fig.findobj(matplotlib.text.Text):
        if not text.get_visible() or not text.get_text():
            continue

        box = text.get_window_extent(renderer)
        if (
            box.x0 < -2
            or box.y0 < -2
            or box.x1 > fig.bbox.width + 2
            or box.y1 > fig.bbox.height + 2
        ):
            raise ValueError(
                f"Clipped text in {layout}: {text.get_text()}"
            )

    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--layout",
        choices=("both", "fullwidth", "singlecolumn"),
        default="both",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=(
            Path(__file__).resolve().parent
            / "figure5_accuracy_layouts"
        ),
    )
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    assert sum(row[1] for row in DATA[1:]) == DATA[0][1]
    assert all(
        0 <= value <= 100
        for row in DATA
        for value in row[2:]
    )

    layouts = (
        ("fullwidth", "singlecolumn")
        if args.layout == "both"
        else (args.layout,)
    )

    for layout in layouts:
        fig = make_figure(layout)
        stem = f"Figure_5_Accuracy_{layout}"

        for extension in ("pdf", "svg", "png"):
            output = args.outdir / f"{stem}.{extension}"
            fig.savefig(output, dpi=300, facecolor="white")
            print(output)

        plt.close(fig)

    with (args.outdir / "accuracy_values.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "Group",
            "Requirements",
            "Single-shot accuracy (%)",
            "NLTL_v2 accuracy (%)",
        ])
        writer.writerows(DATA)


if __name__ == "__main__":
    main()