RESULTS FIGURE LAYOUT VARIANTS

full_width/: two-column artwork for figure* with width=\textwidth.
single_column/: vertically stacked panels for figure with width=\columnwidth.
single_panels/: separate one-column panels; combine with subfigure if desired.
Layout_Comparison.pdf: three pages comparing artwork at actual intended widths.
View or print the comparison at 100%. PNG previews are not submission artwork.

Current widths: column 78.0 mm; text 164.5 mm.
Do not shrink full_width files into a column; choose the single_column design.
PDF chart files contain vector artwork and embedded fonts; SVG files contain editable text.
Automated metrics retain the original table snapshot. Manual counts use the updated review supplied on 15 October 2026. Zero-count manual categories are omitted from the chart legend but retained in data exports. Criterion scores were not recomputed.
The source snapshots, CSVs and provenance are included.

Run: python3 make_results_figure_variants.py
Dependencies: python3 -m pip install matplotlib numpy
A new timestamped outputs/results_layout_variants_* subfolder is created beside the script.
