#!/usr/bin/env python3
"""Generate publication-sized layout alternatives from the current manuscript tables.

Run: python3 make_results_figure_variants.py
Requires: matplotlib numpy
Default widths match the supplied elsarticle 3p PDF: 78 mm column, 164.5 mm text.
Data are reported table values, not a recomputation of raw SHACL results.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'nltl-results-mpl'))
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    import numpy as np
except ImportError as exc:
    raise SystemExit('Missing plotting dependency. Run: python -m pip install matplotlib numpy') from exc

SCRIPT_DIR = Path(__file__).resolve().parent
WORKFLOWS = ['Single-shot', 'NLTL_v2']
# Consistent semantic colours across all results figures. Green matches
# the manuscript pipeline's PASS block. Counts and fixed segment order also
# identify categories without relying on colour alone.
TEAL = '#087C82'
GREEN = '#208262'
OCHRE = '#E2B85B'
VERMILION = '#BE4C44'
GREY = '#D5DBDF'
WORKFLOW_COLORS = [VERMILION, TEAL]
OUTCOME_COLORS = [GREEN, VERMILION, GREY]
MANUAL_COLORS = [GREEN, OCHRE, VERMILION, GREY]
MANUAL_CATEGORIES = ['Correct', 'Minor defect', 'Major defect', 'Unassessable']
MANUAL_SAMPLE_SIZE = 70

# Current manuscript Tables 4 and 7. Accuracy is a macro average over
# requirements, with no-verdict cases receiving zero credit.
MAIN = [
    {'group': 'Overall', 'requirements': 268, 'cases': 2160, 'accuracy': [68.47, 76.11], 'coverage': [82.46, 91.79]},
    {'group': 'Direct static', 'requirements': 190, 'cases': 1516, 'accuracy': [70.07, 76.38], 'coverage': [83.68, 92.63]},
    {'group': 'Direct calculation', 'requirements': 41, 'cases': 337, 'accuracy': [62.64, 79.83], 'coverage': [75.61, 92.68]},
    {'group': 'Complex readiness', 'requirements': 37, 'cases': 307, 'accuracy': [66.70, 70.61], 'coverage': [83.78, 86.49]},
]
# Table 6: columns are observed PASS, observed FAIL, no verdict.
EXPECTED_OBSERVED = {
    'PASS': {'cases': 955, 'counts': [[425, 344, 186], [488, 377, 90]]},
    'FAIL': {'cases': 1205, 'counts': [[77, 913, 215], [80, 1013, 112]]},
}
# Updated joint manual review supplied by the author on 15 October 2026.
# Order: correct, minor defect, major defect, unassessable.
# The three supplied categories sum to 70 for each workflow; consequently
# no cases remain in the unassessable category. Do not infer new rubric scores.
MANUAL = [[22, 8, 40, 0], [42, 15, 13, 0]]
SOURCE = {
    'workbook': 'NLTL_v2_Paper_Tables(4).xlsx',
    'workbook_sha256': '4e36da99020d379bee764f4d72e6aeb2a59248fc89d4b2bea43c0b51d125bf1f',
    'tables': {'main': [4, 7], 'expected_observed': [6]},
    'data_kind': 'Automated metrics: original reported-table snapshot; no raw evaluation recomputed',
    'manual_review': {
        'source': 'Updated review with Haitham, counts supplied by author on 2026-10-15',
        'counts_from_original_workbook': False,
        'sample_size_per_workflow': MANUAL_SAMPLE_SIZE,
        'note': 'Criterion-level scores and agreement statistics were not supplied or recomputed.',
    },
}



def validate_data():
    if sum(r['requirements'] for r in MAIN[1:]) != 268:
        raise ValueError('Verification-mode requirement totals differ from 268')
    if sum(r['cases'] for r in MAIN[1:]) != 2160:
        raise ValueError('Verification-mode case totals differ from 2160')
    for expected, entry in EXPECTED_OBSERVED.items():
        for row in entry['counts']:
            if sum(row) != entry['cases']:
                raise ValueError(f'Expected-{expected} class totals do not reconcile')
    for row in MANUAL:
        if len(row) != len(MANUAL_CATEGORIES) or any(not isinstance(n, int) or n < 0 for n in row):
            raise ValueError('Manual counts must be non-negative integers in the declared category order')
        if sum(row) != MANUAL_SAMPLE_SIZE:
            raise ValueError('Manual-review sample is not 70')
    for i, target in enumerate([[1338, 77, 344, 401], [1501, 80, 377, 202]]):
        p, f = EXPECTED_OBSERVED['PASS']['counts'][i], EXPECTED_OBSERVED['FAIL']['counts'][i]
        if [p[0] + f[1], f[0], p[1], p[2] + f[2]] != target:
            raise ValueError('Case outcomes differ from manuscript Table 5')

def configure():
    plt.rcParams.update({
        'font.family': 'serif', 'font.serif': ['DejaVu Serif'],
        'font.size': 9, 'axes.labelsize': 9, 'axes.titlesize': 10,
        'xtick.labelsize': 8.5, 'ytick.labelsize': 9,
        'legend.fontsize': 9, 'pdf.fonttype': 42, 'ps.fonttype': 42,
        'svg.fonttype': 'none', 'figure.facecolor': 'white',
        'axes.facecolor': 'white', 'text.color': '#222222',
        'axes.labelcolor': '#222222', 'xtick.color': '#222222',
        'ytick.color': '#222222',
    })

def percent_axis(ax, maximum=100):
    ax.set_xlim(0, maximum)
    ax.set_xticks(np.arange(0, 101, 20), [f'{n}%' for n in range(0, 101, 20)])
    ax.grid(axis='x', color='#E4E9EC', lw=.65)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.spines['bottom'].set_color('#93A0A9')
    ax.tick_params(axis='y', length=0)

def save_figure(fig, output, stem):
    # Preserve a fixed print width and verify labels before saving.
    # Some Matplotlib axis labels can sit a few pixels outside the canvas due to
    # font metrics and antialiasing; treat that as acceptable while still failing
    # for genuinely clipped text.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    tolerance = 12
    for artist in fig.findobj(matplotlib.text.Text):
        if not artist.get_visible() or not artist.get_text().strip():
            continue
        box = artist.get_window_extent(renderer)
        if box.x0 < canvas.x0 - tolerance or box.y0 < canvas.y0 - tolerance or box.x1 > canvas.x1 + tolerance or box.y1 > canvas.y1 + tolerance:
            raise ValueError(f'Text outside figure canvas by more than {tolerance}px: {artist.get_text()}')
    paths = []
    for ext in ('pdf', 'png', 'svg'):
        path = output / f'{stem}.{ext}'
        fig.savefig(path, dpi=300)
        paths.append(path)
    plt.close(fig)
    return paths

def segment_label(ax, centre, y, count, width_percent, colour, fontsize):
    """Keep counts centred inside bars at a consistent font size."""
    ax.text(
        centre, y, str(count),
        ha='center',
        va='center',
        fontsize=fontsize,
        color=colour,
        fontweight='bold'
    )


def write_data(output):
    snapshot = {'source': SOURCE, 'main_results': MAIN, 'expected_observed': EXPECTED_OBSERVED, 'manual_review': {'categories': MANUAL_CATEGORIES, 'workflows': WORKFLOWS, 'counts': MANUAL}}
    (output / 'figure_data.json').write_text(json.dumps(snapshot, indent=2) + '\n', encoding='utf-8')
    with (output / 'main_results.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Requirement group', 'Requirements', 'Cases', 'Condition', 'Requirement-level accuracy (%)', 'Executable coverage (%)'])
        for r in MAIN:
            for i, workflow in enumerate(WORKFLOWS):
                writer.writerow([r['group'], r['requirements'], r['cases'], workflow, r['accuracy'][i], r['coverage'][i]])
    with (output / 'expected_observed.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Condition', 'Expected', 'Cases', 'Observed PASS', 'Observed FAIL', 'No verdict'])
        for expected, entry in EXPECTED_OBSERVED.items():
            for workflow, counts in zip(WORKFLOWS, entry['counts']):
                writer.writerow([workflow, expected, entry['cases'], *counts])
    with (output / 'manual_review.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Condition', 'Correct', 'Minor defect', 'Major defect', 'Unassessable'])
        for workflow, counts in zip(WORKFLOWS, MANUAL):
            writer.writerow([workflow, *counts])

def figure_style(single):
    configure()
    plt.rcParams.update({'font.size': 7.8 if single else 8.5, 'axes.labelsize': 7.8 if single else 8.5, 'axes.titlesize': 8.3 if single else 9.2, 'xtick.labelsize': 7.4 if single else 8.0, 'ytick.labelsize': 7.8 if single else 8.5, 'legend.fontsize': 7.8 if single else 8.5})


def main_variant(output, width, single=False, selected=None):
    figure_style(single)
    metrics = [selected] if selected else ['accuracy', 'coverage']
    height = (64 if selected else 116) if single else 90
    fig, axes = plt.subplots(len(metrics) if single else 1, 1 if single else len(metrics), figsize=(width/25.4, height/25.4), squeeze=False)
    fig.subplots_adjust(left=.39 if single else .25, right=.965, bottom=.14 if selected else (.11 if single else .16), top=.82 if selected else (.89 if single else .80), wspace=.23, hspace=.62)
    y = np.array([3.45, 2.25, 1.15, .05])
    for panel, (ax, metric) in enumerate(zip(axes.flat, metrics)):
        for workflow, offset, color in zip(range(2), [.17, -.17], WORKFLOW_COLORS):
            values = [r[metric][workflow] for r in MAIN]
            bars = ax.barh(y + offset, values, height=.30, color=color)
            for bar, value in zip(bars, values):
                ax.text(value-1.2, bar.get_y()+bar.get_height()/2, f'{value:.2f}', ha='right', va='center', fontsize=7.1 if single else 7.7, color='white')
        percent_axis(ax, 103)
        ax.set_ylim(-.5, 4)
        ax.axhline(2.86, color='#CCD4D9', lw=.65)
        title = 'Accuracy' if metric == 'accuracy' else 'Executable coverage'
        prefix = '' if selected else f'({chr(97+panel)}) '
        ax.set_title(prefix+title, loc='left', pad=8)
        ax.set_xlabel('Accuracy (%)' if metric == 'accuracy' else 'Coverage (%)', labelpad=5)
        if single or panel == 0:
            ax.set_yticks(y, [f"{r['group']}\n(n = {r['requirements']})" for r in MAIN])
        else:
            ax.set_yticks(y, ['']*4)
    fig.legend(handles=[Patch(facecolor=c,label=l) for c,l in zip(WORKFLOW_COLORS,WORKFLOWS)], loc='upper center', bbox_to_anchor=(.53 if single else .58,.99), ncol=2, frameon=False, handlelength=1.2, columnspacing=1.2)
    suffix = ('_Accuracy' if selected == 'accuracy' else '_Coverage') if selected else ''
    return save_figure(fig, output, 'Figure_5_Main_Results'+suffix)


def outcomes_variant(output, width, single=False, selected=None):
    figure_style(single)
    expected_classes = [selected] if selected else ['PASS','FAIL']
    height = (54 if selected else 99) if single else 74
    fig, axes = plt.subplots(len(expected_classes) if single else 1, 1 if single else len(expected_classes), figsize=(width/25.4,height/25.4), squeeze=False)
    fig.subplots_adjust(left=.26 if single else .14, right=.955, bottom=.16 if selected else (.09 if single else .20), top=.70 if selected else (.81 if single else .70), wspace=.24, hspace=.77)
    for panel,(ax,expected) in enumerate(zip(axes.flat,expected_classes)):
        entry=EXPECTED_OBSERVED[expected]
        counts=np.array(entry['counts'])[:,[0,1,2] if expected=='PASS' else [1,0,2]]
        widths=counts/entry['cases']*100
        for row in range(2):
            left=0
            for k in range(3):
                w=widths[row,k]
                ax.barh(1-row,w,left=left,height=.35,color=OUTCOME_COLORS[k],edgecolor='white',lw=.5)
                segment_label(
                    ax, left+w/2, 1-row, counts[row,k], w,
                    'white' if k < 2 else '#222222', 6.2 if single else 6.9
                )
                left+=w
        percent_axis(ax,104)
        ax.set_ylim(-.5,1.5)
        prefix='' if selected else f'({chr(97+panel)}) '
        ax.set_title(f'{prefix}Expected {expected} (n = {entry["cases"]:,})',loc='left',pad=18,fontsize=8.1 if single else 9)
        ax.text(0,1.08,'Incorrect = false rejection' if expected=='PASS' else 'Incorrect = false acceptance',transform=ax.transAxes,fontsize=7.2 if single else 7.8,color='#576773')
        ax.set_xlabel('Share of expected-class cases (%)',labelpad=5,fontsize=7.2 if single else 8)
        ax.set_yticks([1,0],WORKFLOWS if single or panel==0 else ['', ''])
    labels=['Correct','Incorrect','No verdict'] if single else ['Correct verdict','Incorrect verdict','No verdict']
    fig.legend(handles=[Patch(facecolor=c,label=l) for c,l in zip(OUTCOME_COLORS,labels)],loc='upper center',bbox_to_anchor=(.51,.985),ncol=3,frameon=False,fontsize=7.4 if single else 8.2,handlelength=1,columnspacing=.9)
    suffix=('_Expected_'+selected) if selected else ''
    return save_figure(fig,output,'Figure_6_Expected_Observed'+suffix)


def manual_variant(output,width,single=False):
    figure_style(single)
    height=55 if single else 54
    fig,ax=plt.subplots(figsize=(width/25.4,height/25.4))
    fig.subplots_adjust(left=.26 if single else .17,right=.955,bottom=.22,top=.74 if single else .75)
    for row,counts in enumerate(MANUAL):
        left=0
        for k,count in enumerate(counts):
            if count == 0:
                continue
            w=count/MANUAL_SAMPLE_SIZE*100
            ax.barh(1-row,w,left=left,height=.36,color=MANUAL_COLORS[k],edgecolor='white',lw=.5)
            segment_label(ax, left+w/2, 1-row, count, w,
                          'white' if k in (0, 2) else '#222222', 7.7 if single else 8.5)
            left+=w
    percent_axis(ax,104)
    ax.set_ylim(-.5,1.5)
    ax.set_yticks([1,0],[f'{w}\n(n = {MANUAL_SAMPLE_SIZE})' for w in WORKFLOWS])
    ax.set_xlabel('Share of reviewed requirements (%)',labelpad=5,fontsize=7.4 if single else 8.2)
    # Hide categories that have zero counts in both workflows. Keep all four
    # categories in the CSV/JSON so omitted categories are explicit.
    active = [k for k in range(len(MANUAL_CATEGORIES))
              if any(row[k] > 0 for row in MANUAL)]
    # Two-column layout reads across rows: Correct / Minor, then Major.
    order = active[::2] + active[1::2] if single else active
    handles=[Patch(facecolor=MANUAL_COLORS[k],label=MANUAL_CATEGORIES[k]) for k in order]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.54 if single else .56,.985),ncol=2 if single else len(active),frameon=False,fontsize=7.8 if single else 8.2,handlelength=1.1,columnspacing=1.1)
    return save_figure(fig,output,'Figure_7_Manual_Review')


def image_at(fig,path,x_mm,top_mm,width_mm):
    pixels=plt.imread(path)
    height_mm=width_mm*pixels.shape[0]/pixels.shape[1]
    ax=fig.add_axes([x_mm/210,(297-top_mm-height_mm)/297,width_mm/210,height_mm/297])
    ax.imshow(pixels)
    ax.axis('off')
    return height_mm


def make_comparison(output,column_width,text_width):
    from matplotlib.backends.backend_pdf import PdfPages
    path=output/'Layout_Comparison.pdf'
    items=[('Figure_5_Main_Results','Accuracy and executable coverage',90,116),('Figure_6_Expected_Observed','Expected versus observed outcomes',74,99),('Figure_7_Manual_Review','Manual-review verdicts',54,55)]
    with PdfPages(path) as pdf:
        for stem,title,hfull,hsingle in items:
            fig=plt.figure(figsize=(210/25.4,297/25.4))
            fig.text(.09,.96,title,fontsize=11,fontweight='bold')
            fig.text(.09,.938,'Comparison at intended print size. View or print at 100%.',fontsize=8)
            left_mm=(210-text_width)/2
            fig.text(.10,1-26/297,f'Full width: {text_width:g} mm',fontsize=8.5,fontweight='bold',zorder=1000)
            image_at(fig,output/'full_width'/(stem+'.png'),left_mm,30,text_width)
            start=30+hfull+12
            fig.text(.10,1-start/297,f'Single column: {column_width:g} mm',fontsize=8.5,fontweight='bold')
            image_at(fig,output/'single_column'/(stem+'.png'),left_mm,start+4,column_width)
            x=(left_mm+column_width+9)/210
            y=1-(start+10)/297
            details=(f'Full-width height: {hfull} mm\nSingle-column height: {hsingle} mm\n\nFigure area, before captions:\nFull width: {text_width*hfull/100:.1f} cm²\nSingle column: {column_width*hsingle/100:.1f} cm²\n\nThese widths match the current\nmanuscript layout. Float placement\nand caption length also affect\nactual page use.\n\nPDF artwork remains vector.\nThis comparison uses PNG previews.')
            fig.text(x,y,details,va='top',fontsize=8,linespacing=1.65)
            pdf.savefig(fig)
            plt.close(fig)
    return path


def main():
    parser=argparse.ArgumentParser(description='Generate full-width, single-column stacked, and separate-panel variants of the three manuscript results figures.')
    parser.add_argument('--output-dir',type=Path,help='Optional empty output directory')
    parser.add_argument('--column-width-mm',type=float,default=78.0,help='Current elsarticle 3p column width (default: 78 mm)')
    parser.add_argument('--text-width-mm',type=float,default=164.5,help='Current full text width (default: 164.5 mm)')
    args=parser.parse_args()
    if not 70 <= args.column_width_mm <= 95 or not 150 <= args.text_width_mm <= 190:
        parser.error('Supported proof widths: column 70-95 mm; text width 150-190 mm.')
    validate_data()
    output=args.output_dir.expanduser().resolve() if args.output_dir else SCRIPT_DIR/'outputs'/('results_layout_variants_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise SystemExit(f'Output path is not empty: {output}\nUse a new folder or omit --output-dir.')
    output.mkdir(parents=True,exist_ok=True)
    paths=[]
    for single,folder,width in [(False,'full_width',args.text_width_mm),(True,'single_column',args.column_width_mm)]:
        target=output/folder;target.mkdir()
        paths+=main_variant(target,width,single)
        paths+=outcomes_variant(target,width,single)
        paths+=manual_variant(target,width,single)
    panels=output/'single_panels';panels.mkdir()
    for metric in ['accuracy','coverage']:
        paths+=main_variant(panels,args.column_width_mm,True,metric)
    for expected in ['PASS','FAIL']:
        paths+=outcomes_variant(panels,args.column_width_mm,True,expected)
    comparison=make_comparison(output,args.column_width_mm,args.text_width_mm)
    write_data(output)
    data={'generator':Path(__file__).name,'created_local':datetime.now().astimezone().isoformat(),'source':SOURCE,'colours':{'workflows':dict(zip(WORKFLOWS,WORKFLOW_COLORS)),'manual_categories':dict(zip(MANUAL_CATEGORIES,MANUAL_COLORS))},'column_width_mm':args.column_width_mm,'text_width_mm':args.text_width_mm,'metric_definition':'Requirement-level accuracy includes no-verdict cases as zero credit. Figure 6 and Figure 7 segment labels show counts, with percentage axes.','files':[{'path':str(p.relative_to(output)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths+[comparison]]}
    (output/'provenance.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    (output/'README.txt').write_text('RESULTS FIGURE LAYOUT VARIANTS\n\nfull_width/: two-column artwork for figure* with width=\\textwidth.\nsingle_column/: vertically stacked panels for figure with width=\\columnwidth.\nsingle_panels/: separate one-column panels; combine with subfigure if desired.\nLayout_Comparison.pdf: three pages comparing artwork at actual intended widths.\nView or print the comparison at 100%. PNG previews are not submission artwork.\n\nCurrent widths: column '+str(args.column_width_mm)+' mm; text '+str(args.text_width_mm)+' mm.\nDo not shrink full_width files into a column; choose the single_column design.\nPDF chart files contain vector artwork and embedded fonts; SVG files contain editable text.\nAutomated metrics retain the original table snapshot. Manual counts use the updated review supplied on 15 October 2026. Zero-count manual categories are omitted from the chart legend but retained in data exports. Criterion scores were not recomputed.\nThe source snapshots, CSVs and provenance are included.\n\nRun: python3 make_results_figure_variants.py\nDependencies: python3 -m pip install matplotlib numpy\nA new timestamped outputs/results_layout_variants_* subfolder is created beside the script.\n',encoding='utf-8')
    print(f'\nOUTPUT SUBFOLDER:\n  {output}\n\nOPEN THIS COMPARISON FIRST:\n  {comparison}\n')
    for folder in ['full_width','single_column','single_panels']:
        print(folder.upper()+':')
        for p in sorted((output/folder).glob('*.pdf')):print('  '+str(p))
    print('\nUpload only the chosen PDF variants to Overleaf. Data and previews are in the same output folder.')


if __name__=='__main__':
    main()
