"""Read-only recovery of saved evidence. Never imports or invokes an evaluator/client."""
import csv
import hashlib
import io
import json
import statistics as stats
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook
from pypdf import PdfReader

ROOT = Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP')
PROJECT = ROOT.parent
DOWNLOADS = Path('/Users/sadisfaction570/Downloads')
OUT = Path(__file__).resolve().parent
EXP = ROOT / 'SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50'
BENCH = ROOT / 'SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13'
SOURCES = {}
CHECKS = []

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def track(p):
    p = Path(p).resolve()
    SOURCES.setdefault(str(p), sha(p))
    return p

def readjson(p):
    return json.loads(track(p).read_text())

def lines(p):
    return [json.loads(s) for s in track(p).read_text().splitlines() if s.strip()]

def check(name, condition, detail=''):
    CHECKS.append(dict(check=name, passed=bool(condition), detail=detail))
    if not condition:
        raise AssertionError(f'{name}: {detail}')

def writecsv(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows({k:('NA' if v is None else v) for k,v in row.items()} for row in rows)

def correct(r):
    return r is not None and r['execution_status'] == 'EXECUTED' and (
        (r['expected_outcome'] == 'PASS' and r['actual_conforms'] is True) or
        (r['expected_outcome'] == 'FAIL' and r['actual_conforms'] is False))

sample_path = EXP / 'MANIFESTS/sample_50.json'
sample = readjson(sample_path)
requirements = set(sample['requirements'])
check('50 unique sample requirement IDs', len(requirements) == len(sample['requirements']) == 50)
lock = readjson(EXP / 'MANIFESTS/manifest_lock.json')
check('Frozen sample hash', sha(sample_path) == lock['files']['sample']['sha256'])

# The independent assignment manifests, not emitted evaluation rows, set denominators.
assigned = {}
all_assigned = {}
for p in sorted((BENCH / 'manifests').glob('*_batch_*_manifest.jsonl')):
    check(f'Manifest hash {p.name}', sha(p) == readjson(EXP / 'OUTPUTS/RDF_EVALUATION/SELF_REPAIR_FINAL/luna/run_manifest.json')['benchmark_manifest_hashes'][str(p.relative_to(PROJECT))])
    for r in lines(p):
        key = (r['requirement_id'], r['case_id'])
        check(f'Unique assigned case {r["case_id"]}', key not in all_assigned)
        all_assigned[key] = dict(r, manifest_source=str(p), rdf_sha256=sha(track(BENCH / r['rdf_path'])))
        if key[0] in requirements:
            assigned[key] = all_assigned[key]
check('Legacy assignments 381 / full benchmark 2186', len(assigned) == 381 and len(all_assigned) == 2186)
for r in sample['records']:
    check(f'Sample frozen count {r["requirement_id"]}', sum(k[0] == r['requirement_id'] for k in assigned) == r['frozen_case_count'])

archive = track(DOWNLOADS / 'NLTL_v2_manuscript_and_data.zip')
member = 'NLTL_v2/case_outcomes.csv'
with ZipFile(archive) as z:
    exported = list(csv.DictReader(io.StringIO(z.read(member).decode())))
    (OUT / 'manuscript_data_provenance.json').write_bytes(z.read('NLTL_v2/data_provenance.json'))
    exported_hash = hashlib.sha256(z.read(member)).hexdigest()
retained = {}
for r in exported:
    key = (r['requirement_id'], r['case_id'])
    check(f'Retained identity {key}', key in all_assigned)
    a = all_assigned[key]
    check(f'Retained label/path/hash {key}', r['expected_outcome'] == r['expected'] == a['expected'] and r['rdf_path'] == a['rdf_path'] and r['rdf_sha256'] == a['rdf_sha256'])
    if key in retained:
        check(f'Consistent cross-condition retained assignment {key}', retained[key]['rdf_sha256'] == r['rdf_sha256'] and retained[key]['expected'] == r['expected'])
    retained[key] = r
check('Retained 2160 IDs and two conditions', len(retained) == 2160 and Counter(r['condition'] for r in exported) == {'NO_SEMANTIC':2160, 'SINGLESHOT':2160})
current = {k:v for k,v in assigned.items() if k in retained}
check('Retained 373 cases and 50 requirements', len(current) == 373 and {k[0] for k in current} == requirements)
case_source_current = f'{archive}!{member} (member SHA256 {exported_hash}); membership only; original RDF/labels verified unchanged'
case_source_legacy = str(BENCH / 'manifests/*_batch_*_manifest.jsonl')
writecsv('assigned_case_manifest.csv', [dict(evaluation_version=v, requirement_id=k[0], case_id=k[1], expected=r['expected'], rdf_path=r['rdf_path'], rdf_sha256=r['rdf_sha256'], original_manifest_source=r['manifest_source'], retained_membership_source=case_source_current if v=='retained_373' else '') for v,a in [('legacy_381',assigned),('retained_373',current)] for k,r in sorted(a.items())])
writecsv('excluded_cases.csv', [dict(requirement_id=k[0], case_id=k[1], expected=r['expected'], original_manifest_source=r['manifest_source'], exclusion_evidence=case_source_current, reason='Absent from both retained manuscript condition exports; manuscript states benchmark-review exclusions; case-specific adjudication rationale unavailable') for k,r in sorted(assigned.items()) if k not in current])

runtime_book = track(ROOT / 'ocean_reporting/NLTL_Runtime_and_Iterations.xlsx')
w = load_workbook(runtime_book, read_only=True, data_only=True)
it = iter(w['Requirement_Runs'].values)
for header in it:
    if 'Run ID' in header and 'Elapsed (s)' in header:
        break
runtime_rows = [dict(zip(header,r)) for r in it if any(v is not None for v in r)]
w.close()
runtime_index = {r['Run ID']:r for r in runtime_rows}
check('Runtime workbook unique run IDs', len(runtime_index) == len(runtime_rows))

labels = dict(luna='GPT-5.6 Luna', sol='GPT-5.6 Sol', gemini='Gemini 3.5 Flash', gpt_oss='GPT-OSS 120B')
expected_runtime = dict(luna=(71.61006,55.45656,49.935,43),sol=(76.30978,115.24606,43.898,47),gemini=(114.50898,141.30442,64.560,46),gpt_oss=(59.80680,38.39266,59.0075,28))
paper_macro = dict(luna=72.03,sol=82.19,gemini=73.54,gpt_oss=47.04)
summary_rows, per_req, first_rows, pairing_rows, report_rows = [], [], [], [], []
for model,label in labels.items():
    stage_maps = {}
    generated_maps = {}
    for stage in ['SELF_REPAIR_FINAL','FIRST_GENERATION']:
        directory = EXP / f'OUTPUTS/RDF_EVALUATION/{stage}/{model}'
        ledger_path = directory / 'raw_case_results.jsonl'
        ledger = lines(ledger_path)
        result_map = {(r['requirement_id'],r['case_id']):r for r in ledger}
        check(f'{model} {stage} complete unique assigned identities', len(ledger) == len(result_map) == 381 and set(result_map) == set(assigned))
        saved = readjson(directory / 'summary.json')
        manifest_path = PROJECT / saved['generated_manifest_path']
        check(f'{model} {stage} generated manifest hash', sha(track(manifest_path)) == saved['generated_manifest_sha256'])
        generated = lines(manifest_path)
        gm = {r['requirement_id']:r for r in generated}
        check(f'{model} {stage} generated cohort', len(generated) == len(gm) == 50 and set(gm) == requirements)
        generated_maps[stage] = gm
        stage_maps[stage] = result_map
        for key,r in result_map.items():
            a = assigned[key]
            g = gm[key[0]]
            check(f'{model}/{stage}/{key} identity and output pairing', r['expected_outcome'] == a['expected'] and r['rdf_path'] == a['rdf_path'] and r['rdf_sha256'] == a['rdf_sha256'] and r['generation_run_id'] == g['run_id'] and r['generated_shape_sha256'] == g.get('generated_shacl_sha256'))
            check(f'{model}/{stage}/{key} verdict flag', bool(r.get('behavioral_match')) == correct(r))
        check(f'{model} {stage} reported correct/executed totals', saved['correct_cases'] == sum(correct(r) for r in ledger) and saved['executable_cases'] == sum(r['execution_status']=='EXECUTED' for r in ledger))
    final = generated_maps['SELF_REPAIR_FINAL']
    runtimes = {}
    accepted = 0
    for req in sorted(requirements):
        g = final[req]
        if g.get('run_metadata_path'):
            run_dir = (PROJECT / g['run_metadata_path']).parent.parent
            pairing_method = 'explicit generated-manifest run ID'
        else:
            control = lines(EXP / f'OUTPUTS/FINAL/{model}/scaling_control/requirement_results.jsonl')
            cr = [r for r in control if r['requirement_id']==req]
            candidates = list((EXP / f'OUTPUTS/FINAL/{model}/runs').glob(f'RUN-{req}-*'))
            check(f'{model}/{req} recover exception source', len(cr)==1 and cr[0]['result_kind']=='RUNNER_EXCEPTION' and len(candidates)==1 and cr[0]['final_feedback']==g['failure_detail'])
            run_dir = candidates[0]
            pairing_method = 'unique final-scope requirement run plus identical control-ledger exception; evaluation run ID is missing'
        events_path = run_dir / 'events.jsonl'
        events = lines(events_path)
        starts = [e for e in events if e['event_type']=='run_started']
        finishes = [e for e in events if e['event_type']=='run_finished']
        check(f'{model}/{req} one completed generation run', len(starts)==len(finishes)==1)
        start,end = starts[0],finishes[0]
        runtime = (datetime.fromisoformat(end['timestamp_utc'].replace('Z','+00:00'))-datetime.fromisoformat(start['timestamp_utc'].replace('Z','+00:00'))).total_seconds()
        run_id = start['run_id']
        check(f'{model}/{req} run IDs and nonnegative timing', runtime>=0 and start['run_id']==end['run_id'] and (g['run_id'] is None or run_id==g['run_id']) and start['requirement_id']==req)
        check(f'{model}/{req} first/final same run', generated_maps['FIRST_GENERATION'][req]['run_id']==g['run_id'])
        workbook_row = runtime_index[run_id]
        check(f'{model}/{req} runtime workbook pairing', workbook_row['Requirement ID']==req and workbook_row['Completed'] is True and abs(workbook_row['Elapsed (s)']-runtime)<1e-9)
        is_accepted = end.get('accepted') is True and end['status']=='GENERATION_ACCEPTED'
        check(f'{model}/{req} accepted artifact consistency', is_accepted == (g['generation_status']=='GENERATED'))
        if g.get('generated_shacl_path'):
            check(f'{model}/{req} final artifact hash', sha(track(PROJECT / g['generated_shacl_path']))==g['generated_shacl_sha256'])
        accepted += is_accepted
        runtimes[req] = (runtime,run_id,str(events_path))
        pairing_rows.append(dict(model=label, requirement_id=req, generation_run_id=run_id, evaluation_generation_run_id=g['run_id'], pairing_method=pairing_method, generation_source=str(events_path), generated_manifest=str(PROJECT / readjson(EXP/f'OUTPUTS/RDF_EVALUATION/SELF_REPAIR_FINAL/{model}/summary.json')['generated_manifest_path']), final_shape_path=g.get('generated_shacl_path'), final_shape_sha256=g.get('generated_shacl_sha256'), accepted=is_accepted, runtime_s=runtime, attempts=end.get('attempts'), status=end['status']))
    times = [v[0] for v in runtimes.values()]
    measured = (stats.mean(times),stats.stdev(times),stats.median(times),accepted)
    check(f'{model} supplied runtime summary', all(abs(a-b)<0.000006 for a,b in zip(measured[:3],expected_runtime[model][:3])) and accepted==expected_runtime[model][3], str(measured))
    for version,a in [('legacy_381',assigned),('retained_373',current)]:
        for stage in ['SELF_REPAIR_FINAL','FIRST_GENERATION']:
            results = stage_maps[stage]
            req_rows = []
            for req in sorted(requirements):
                keys = [k for k in a if k[0]==req]
                rows = [results.get(k) for k in keys]
                ncorrect = sum(correct(r) for r in rows)
                executed = sum(r is not None and r['execution_status']=='EXECUTED' and isinstance(r['actual_conforms'],bool) for r in rows)
                rt,run_id,event_path = runtimes[req]
                req_rows.append(dict(model=label,evaluation_version=version,stage=stage,requirement_id=req,assigned_cases=len(keys),correct_cases=ncorrect,executed_cases=executed,requirement_accuracy=ncorrect/len(keys),runtime_s=rt if stage=='SELF_REPAIR_FINAL' else None,generation_run_id=run_id,evaluation_generation_run_id=generated_maps[stage][req]['run_id'],generation_source=event_path,evaluation_source=str(EXP/f'OUTPUTS/RDF_EVALUATION/{stage}/{model}/raw_case_results.jsonl'),case_manifest_source=case_source_current if version=='retained_373' else case_source_legacy,assigned_case_ids=';'.join(sorted(k[1] for k in keys)),missing_case_ids=';'.join(k[1] for k in keys if k not in results)))
            macro = 100*stats.mean(r['requirement_accuracy'] for r in req_rows)
            limitations = ('One generation run per requirement; SD is across requirements. Retained case set reconstructed from manuscript export; exclusion adjudication not recovered.' if version=='retained_373' else 'Original 381-case version; not the retained 373-case denominator.')
            if model=='gpt_oss':
                limitations += ' IMO-112 and TRF-059 evaluation run IDs are NA; timing linked via unique final-scope runs and matching exceptions.'
            rec = dict(model=label,stage=stage,evaluation_version=version,requirement_count=50,assigned_case_count=len(a),macro_accuracy_pct=macro,correct_case_count=sum(r['correct_cases'] for r in req_rows),executed_case_count=sum(r['executed_cases'] for r in req_rows),mean_runtime_s=measured[0] if stage=='SELF_REPAIR_FINAL' else None,sd_runtime_s=measured[1] if stage=='SELF_REPAIR_FINAL' else None,median_runtime_s=measured[2] if stage=='SELF_REPAIR_FINAL' else None,runtime_count=50 if stage=='SELF_REPAIR_FINAL' else None,accepted_count=accepted if stage=='SELF_REPAIR_FINAL' else None,generation_source=str(ROOT/'SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/RUN_01') if model=='luna' else str(EXP/f'OUTPUTS/FINAL/{model}'),evaluation_source=str(EXP/f'OUTPUTS/RDF_EVALUATION/{stage}/{model}/raw_case_results.jsonl'),case_manifest_source=case_source_current if version=='retained_373' else case_source_legacy,limitations=limitations)
            rec['pooled_case_accuracy_pct'] = 100*rec['correct_case_count']/len(a)
            rec['executable_requirement_count'] = sum(r['executed_cases']==r['assigned_cases'] for r in req_rows)
            if stage=='SELF_REPAIR_FINAL':
                summary_rows.append(rec)
                per_req.extend(req_rows)
                if version=='retained_373':
                    check(f'{model} retained macro matches model-inclusive PDF', round(macro,2)==paper_macro[model])
            else:
                first_rows.append(rec)
            report_rows.append(dict(model=label,evaluation_version=version,stage=stage,macro_accuracy_pct=macro,pooled_case_accuracy_pct=rec['pooled_case_accuracy_pct'],correct=rec['correct_case_count'],executed=rec['executed_case_count'],strict_requirement_coverage=rec['executable_requirement_count']))
writecsv('model_comparison_summary.csv',summary_rows)
writecsv('model_comparison_per_requirement.csv',per_req)
writecsv('first_generation_separate_summary.csv',first_rows)
writecsv('output_runtime_pairing.csv',pairing_rows)
writecsv('report_reconciliation.csv',report_rows)

inventory = []
for p in sorted(DOWNLOADS.glob('Ocean_Eng_Journal*.pdf')):
    reader = PdfReader(track(p))
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    inventory.append(dict(path=str(p),pages=len(reader.pages),text_sha256=hashlib.sha256(text.encode()).hexdigest(),mentions_373='373' in text,mentions_381='381' in text,contains_model_comparison='82.19%' in text,scope='model-inclusive retained-case manuscript' if '82.19%' in text else 'main-study manuscript; model results omitted'))
for p in [DOWNLOADS/'NLTL_v2_Paper_LaTeX.zip',DOWNLOADS/'Ocean_Engineering_Completion_Checklist.md',DOWNLOADS/'Ocean_Engineering_Completion_Checklist (1).md',DOWNLOADS/'NLTL_v2_Paper_Handover.md',ROOT/'ocean_reporting/inputs/NLTL_v2_Paper_Tables.xlsx',ROOT/'SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/NLTL_Manual_Audit_with_Model_Scaling_FINAL.xlsx',DOWNLOADS/'R13_Behavioral_Evaluation_Mapping_v3.xlsx',DOWNLOADS/'R13_Behavioral_Evaluation_Mapping_v3 (1).xlsx']:
    track(p)
for p in [EXP/'scripts/rdf_evaluation_common.py',EXP/'scripts/run_rdf_evaluation.py',EXP/'scripts/freeze_samples.py',ROOT/'SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/analysis.py',ROOT/'SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/execution.py',ROOT/'SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/core.py',ROOT/'SHACL_GENERATION_PIPELINE/src/nltl_pipeline/orchestration/runner.py']:
    track(p)
writecsv('manuscript_version_inventory.csv',inventory)
for p,digest in SOURCES.items():
    check(f'Source unchanged {p}',sha(p)==digest)
writecsv('source_sha256.csv',[dict(path=p,sha256=h) for p,h in sorted(SOURCES.items())])
(OUT/'verification_checks.json').write_text(json.dumps(CHECKS,indent=2)+'\n')
print(json.dumps(dict(output=str(OUT),checks_passed=len(CHECKS),sources=len(SOURCES),summary=summary_rows),indent=2))
