# Manuscript figures

Run from this folder with Python 3.9 or newer:

```bash
python -m pip install -r requirements.txt
python make_paper_figures.py --output-dir outputs/paper_figures
```

The script also works by itself; `python -m pip install matplotlib` installs its only external dependency.

## Outputs

- `01_main_results`: two panels of horizontal bars, accuracy and executable coverage.
- `01_main_results_table_alternative`: table alternative; pale green identifies the higher observed value, not statistical significance.
- `02_manual_review`: two pies comparing manual-review outcomes; labels give counts and percentages.
- `02_manual_bars_alternative`: solid-colour stacked bars, retained as an optional alternative.
- `03_model_accuracy_coverage`: directly labelled model scatter plot.
- `03_model_bars_alternative`: simpler grouped-bar alternative to the scatter plot.

Each design is exported as PDF, editable-text SVG, and 600-dpi PNG. Choose one alternative per comparison, rather than inserting both. Figure panels and axes have labels, but no paper captions are embedded. Solid blue/orange colours, marker shapes, direct labels and counts support accessibility. No stripes are used. Model-scatter coverage starts at 40%; bar-chart axes start at zero.

Fonts use Times New Roman when installed, otherwise Liberation Serif or DejaVu Serif. Text is set to 10 points. Full-width exports are 6.48 inches wide; the model scatter is 3.07 inches wide, matching the uploaded Elsevier 3p two-column manuscript (468-point text width, 24-point column gap). The export preserves these physical dimensions without tight cropping. Include the main and manual figures with `width=\\textwidth` inside `figure*`, and the model scatter with `width=\\columnwidth` inside `figure`. Enlarging or shrinking an image changes its effective font size. Use PDF in LaTeX for sharp text.

`main_results_table.tex` and `manual_review_table.tex` provide native LaTeX alternatives, without captions or outer table environments. Both need `booktabs`; green cell shading in the main table also needs `\\usepackage[table]{xcolor}` (replace an existing plain xcolor package line rather than loading it twice). Green marks the higher observed value, not statistical significance.

The script prints absolute output paths and produces a ZIP containing figures, plotted CSV data, a readable summary, and a run manifest. Share that output ZIP for review.

## Data and interpretation

Defaults are the agreed data snapshot embedded in the script. This script does not search for or extract data from an Excel workbook. Main accuracy uses the verified full-precision requirement-level summaries; model accuracy is the agreed two-decimal snapshot. Coverage is computed from executable requirement counts.

Main comparison: 268 requirements, 2,160 configurations. Modes: direct static (190 requirements), direct calculation (41), complex readiness (37).

Model comparison: single-pass outputs on the common sample of 50 requirements and 373 configurations. These are not final outputs of the current NLTL_v2 syntax-repair pipeline. The plot does not establish a scaling law. Keep its sample and stage explicit in the manuscript caption.

Accuracy averages each requirement's correct-case fraction and gives unsuccessful outputs no credit. Coverage measures the proportion of requirements with a completed PASS/FAIL verdict for every assigned case; it does not mean every verdict is correct. Manual review covers 70 requirements per condition.

## Change the inputs later

After the first run, copy the three CSVs in `outputs/paper_figures/plot_data` to a separate input folder, edit them, and run:

```bash
python make_paper_figures.py --data-dir edited_plot_data --output-dir outputs/paper_figures_v2
```

Use percentages from 0 to 100 for accuracy. Retain the count columns: the script recomputes coverage, checks denominators and totals, and requires a common model sample/stage. Exact filenames are `main_results.csv`, `manual_review.csv`, and `models.csv`.

Modify figure size, fonts, colours, hatch patterns, or export DPI in the script as needed. No pandas, seaborn, Excel reader, network access, or TeX installation is required.
