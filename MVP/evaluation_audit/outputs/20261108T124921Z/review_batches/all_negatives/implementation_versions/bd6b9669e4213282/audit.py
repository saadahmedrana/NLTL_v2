#!/usr/bin/env python3
"""Offline, provenance-checked audit. No generation/client modules are imported."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import platform
import shutil
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile
import pyshacl
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef, BNode, XSD
from rdflib.collection import Collection
from rdflib.compare import to_isomorphic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PIPE = ROOT / 'SHACL_GENERATION_PIPELINE'
BENCH = PIPE / 'evaluation/BEHAVIORAL_RDF_R13'
R13 = ROOT / 'BENCHMARK_VOCABULARY/FINAL_LOCK_R13'
ONTOLOGY = R13 / 'ontology/nltl_benchmark_vocabulary.ttl'
S = Namespace('http://www.w3.org/ns/shacl#')
N = Namespace('https://w3id.org/nltl/vocab#')
Q = Namespace('http://qudt.org/schema/qudt/')
WORKFLOWS = {'NO_SEMANTIC': 'NLTL_v2', 'SINGLESHOT': 'Single-shot'}
OPTIONS = dict(inference='rdfs', advanced=True, meta_shacl=True, do_owl_imports=False,
               abort_on_first=False, allow_infos=False, allow_warnings=False)
EXCLUSIONS = {'TRF-002-F02': 'Source 1.2 permits the 2017 edition from 2017-12-01; fixture date 2018-06-01 is permitted. Frozen 2019-only oracle cannot justify FAIL. No label changed.'}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def dump(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')
def csvout(p, rows):
    rows=list(rows)
    with Path(p).open('w', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader(); w.writerows({k: json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
def resolve(p):
    p=Path(p)
    if p.is_absolute(): return p
    return ROOT / str(p).removeprefix('MVP/')
def truth(s): return True if s in ('True', True) else False if s in ('False',False) else None
def clone(g):
    h=Graph()
    for t in g: h.add(t)
    return h
def save_evaluated_shape(shape,original,source_path,destination):
    """Preserve historical bytes when unchanged, exact RDF terms for probes."""
    if to_isomorphic(shape)==to_isomorphic(original):shutil.copyfile(source_path,destination)
    else:shape.serialize(destination,format='nt',encoding='utf-8')
def triples(g): return sorted(' '.join(x.n3() for x in t) + ' .' for t in g)
def load_triples(lines):
    g=Graph()
    for line in lines: g.parse(data=line.rstrip(' .')+' .', format='nt')
    return set(g)
def expected_specs(path=None): return {s['case']: s for s in read(path or HERE/'reviewed_failure_specs.json') if s.get('review_status')=='REVIEWED'}

def logic_fingerprint(shape, source, component):
    """Fingerprint reviewed constraint structure, ignoring messages and blank-node IDs."""
    predicate=S.sparql if component=='SPARQLConstraintComponent' else S['or']
    roots=list(shape.objects(source,predicate))
    if not roots:return None
    if component=='SPARQLConstraintComponent' and len(roots)!=1:return None
    graph=Graph(); pending=list(roots);seen=set()
    for root in roots:graph.add((URIRef('urn:audit:root'),predicate,root))
    while pending:
        node=pending.pop()
        if node in seen:continue
        seen.add(node)
        for p,o in shape.predicate_objects(node):
            if p==S.message:continue
            graph.add((node,p,o))
            if isinstance(o,BNode) or (isinstance(o,URIRef) and any(shape.predicate_objects(o))):pending.append(o)
    return str(to_isomorphic(graph).graph_digest())

def inventory(out, archive):
    with ZipFile(archive) as z:
        member=z.read('NLTL_v2/case_outcomes.csv')
        rows=list(csv.DictReader(io.StringIO(member.decode())))
    (out/'retained_case_outcomes.csv').write_bytes(member)
    assert Counter(r['condition'] for r in rows)=={'NO_SEMANTIC':2160,'SINGLESHOT':2160}
    manifests={}
    for p in sorted((BENCH/'manifests').glob('*_batch_*_manifest.jsonl')):
        for line in p.read_text().splitlines():
            r=json.loads(line); assert r['case_id'] not in manifests
            manifests[r['case_id']]=dict(r,manifest_path=str(p))
    assert len(manifests)==2186
    sets=[{r['case_id'] for r in rows if r['condition']==w} for w in WORKFLOWS]
    assert sets[0]==sets[1] and len(sets[0])==2160
    assert len({r['requirement_id'] for r in rows})==268
    historical=PIPE/'evaluation/experiment_results'/rows[0]['run_id']
    raw={}
    for line in (historical/'raw_case_results.jsonl').read_text().splitlines():
        saved=json.loads(line)
        if saved['configuration'] in WORKFLOWS:raw[saved['configuration'],saved['case_id']]=saved
    for r in rows:
        saved=raw[r['condition'],r['case_id']]
        assert truth(r['actual_conforms']) is saved['actual_conforms']
        assert r['execution_status']==saved['execution_status']
        assert r['generated_shape_sha256']==(saved.get('generated_shape_sha256') or '')
    manifest=read(historical/'run_manifest.json')
    assert sha(ONTOLOGY)==manifest['ontology_sha256']
    assert manifest['pyshacl_options']==dict(OPTIONS,ontology_graph_usage=True)
    assert (platform.python_version(),rdflib.__version__,pyshacl.__version__)==(manifest['python_version'],manifest['rdflib_version'],manifest['pyshacl_version']), 'Use recorded Python/rdflib/pySHACL versions'
    sources={str(archive):sha(archive),str(ONTOLOGY):sha(ONTOLOGY),str(historical/'raw_case_results.jsonl'):sha(historical/'raw_case_results.jsonl'),str(historical/'run_manifest.json'):sha(historical/'run_manifest.json')}
    for name in ['requirement_term_index.json','registry/term_registry.json']:
        p=R13/name;sources[str(p)]=sha(p)
    sources[str(HERE/'reviewed_failure_specs.json')]=sha(HERE/'reviewed_failure_specs.json')
    ledger=[]; contexts={}; specs=expected_specs()
    generated={}
    for w,name in [('NO_SEMANTIC','no_semantic'),('SINGLESHOT','singleshot')]:
        p=PIPE/f'evaluation/generated_rule_manifests/RUN_01/{name}_generated_rules.jsonl'
        sources[str(p)]=sha(p)
        generated[w]={r['requirement_id']:r for r in [json.loads(x) for x in p.read_text().splitlines()]}
    for r in rows:
        a=manifests[r['case_id']]; fixture=BENCH/r['rdf_path']
        generation=generated[r['condition']][r['requirement_id']]
        assert generation['generation_status']==r['generation_status']
        assert (generation.get('generated_shacl_sha256') or '')==r['generated_shape_sha256']
        assert r['expected']==r['expected_outcome']==a['expected'] and r['rdf_path']==a['rdf_path']
        assert sha(fixture)==r['rdf_sha256'], f'Fixture changed: {fixture}'
        sources[str(fixture)]=sha(fixture); sources[a['manifest_path']]=sha(a['manifest_path'])
        sp=resolve(r['generated_shape_path']) if r['generated_shape_path'] else None
        if sp and sp.exists():
            assert sha(sp)==r['generated_shape_sha256']; sources[str(sp)]=sha(sp)
            cp=sp.parents[2]/'artifacts/context_pack_initial.json'
            if cp.exists(): contexts[r['requirement_id']]=str(cp); sources[str(cp)]=sha(cp)
        report=historical/r['report_graph_path'] if r['report_graph_path'] else None
        if report and report.exists(): sources[str(report)]=sha(report)
        r=dict(r,workflow=WORKFLOWS[r['condition']],fixture_path=str(fixture),shape_path=str(sp) if sp else '',
               original_report_path=str(report) if report else '',original_eligible=truth(r['actual_conforms']) is not None and r['execution_status']=='EXECUTED',
               review_status='INVALID_TEST_EXCLUDED' if r['case_id'] in EXCLUSIONS else ('REVIEWED' if r['case_id'] in specs else 'NOT_AUDITED'),
               exclusion_reason=EXCLUSIONS.get(r['case_id'],''), requirement_context_path=contexts.get(r['requirement_id'],''))
        r['generation_manifest_record']=generation
        ledger.append(r)
    # Contexts of unavailable outputs can still be located from saved run IDs, without inventing shape paths.
    for r in ledger:
        if not r['requirement_context_path']:
            exp='LUNA_NO_SEMANTIC_VALIDATOR' if r['condition']=='NO_SEMANTIC' else 'LUNA_CONTEXTUAL_SINGLESHOT'
            p=PIPE/f'experiments/{exp}/RUN_01/runs/{r["generation_run_id"]}/artifacts/context_pack_initial.json'
            if p.exists(): r['requirement_context_path']=str(p); sources[str(p)]=sha(p)
        context=read(r['requirement_context_path'])['requirement'] if r['requirement_context_path'] else {}
        r['frozen_requirement_text']=context.get('sourceText','')
        r['normalized_requirement']=context.get('normalizedRequirement','')
        r['ontology_path']=str(ONTOLOGY)
        r['missing_information']='Frozen requirement context unavailable' if not context else ''
    pilot=Path.home()/'Downloads/Intended_Failure_Feasibility_Pilot_2026-11-08'
    for name in ['full_case_preparation_ledger.csv','reviewed_mutation_specs.json','READ_ME_FIRST.md']:
        p=pilot/name
        if p.exists():sources[str(p)]=sha(p)
    for p in HERE.joinpath('source_review').iterdir():
        if p.is_file(): sources[str(p)]=sha(p)
    for name in ['TRAFICOM.pdf','ur-i2rev4.pdf','MSC.385(94).pdf']:
        p=ROOT/'RELEVANT FILES'/name; sources[str(p)]=sha(p)
    for exp in ['LUNA_NO_SEMANTIC_VALIDATOR','LUNA_CONTEXTUAL_SINGLESHOT']:
        for p in (PIPE/f'experiments/{exp}/PREPARATION').rglob('*'):
            if p.is_file(): sources[str(p)]=sha(p)
    dump(out/'retained_rows.json',ledger); csvout(out/'full_case_ledger.csv',ledger)
    dump(out/'environment.json',dict(python=platform.python_version(),rdflib=rdflib.__version__,pyshacl=pyshacl.__version__,options=OPTIONS,ontology_sha256=sha(ONTOLOGY)))
    dump(out/'inventory.json',dict(archive=str(archive),member='NLTL_v2/case_outcomes.csv',member_sha256=hashlib.sha256(member).hexdigest(),
        requirements=268,cases_per_workflow=2160,legacy_cases=2186,historical_run=str(historical),
        missing_information=['26 prior exclusions have no case-specific adjudication reasons in retained export.',
        'No explicit positive-parent pairing or reviewed repair specification for unaudited negatives.',
        'Source report_02(1).zip is unavailable; retained archive and local original reports are used.',
        'Strict pilot is purposive; no benchmark-wide strict accuracy can be inferred.']))
    csvout(out/'prior_cohort_exclusions.csv',[dict(requirement_id=manifests[c]['requirement_id'],case_id=c,reason='Absent from both retained exports; original adjudication rationale unavailable') for c in sorted(set(manifests)-sets[0])])
    dump(out/'source_hashes.json',sources)
    dump(out/'reviewed_failure_specs.json',list(specs.values()))
    print(f'Inventory: {len(ledger)} rows, 268 requirements, 2160 cases per workflow',flush=True)
    corrections(out,ledger)

def table_oracle(g,contract):
    """Independent schema-owner evaluator for frozen Table 8, no generated SHACL."""
    def vals(s,p): return list(g.objects(s,N[p]))
    ships=list(g.subjects(RDF.type,N.ship))
    if len(ships)!=1:return False
    ship=ships[0]; cases=vals(ship,'hasSteelGradeRequirementCase')
    if not cases:return True
    pcs=vals(ship,'polarClass')
    if len(pcs)!=1:return False
    pc=str(pcs[0]).split('#')[-1].replace('polarClassPc','PC')
    groups={'PC1-3':['PC1','PC2','PC3'],'PC1-5':['PC1','PC2','PC3','PC4','PC5'],'PC4-5':['PC4','PC5'],'PC6-7':['PC6','PC7']}
    table=contract['tableModel']
    for c in cases:
        fields={p:vals(c,p) for p in ['steelGradeRequirementCasePlating','asBuiltPlateThickness','steelMaterialClass','steelStrengthCategory','tableReference','actualHullStructuralSteelGrade','requiredHullStructuralSteelGrade']}
        if any(len(fields[p])!=1 for p in fields if p!='requiredHullStructuralSteelGrade'):return False
        if fields['tableReference']!=[N.iacsUrI2Table8]:return False
        q=fields['asBuiltPlateThickness'][0]; nums=list(g.objects(q,Q.numericValue));units=list(g.objects(q,Q.unit))
        if len(nums)!=1 or units!=[URIRef('http://qudt.org/vocab/unit/MilliM')]:return False
        t=float(nums[0]); mat=str(fields['steelMaterialClass'][0]).split('#')[-1]; fam=str(fields['steelStrengthCategory'][0]).split('#')[-1]
        selections=[s for row in table['rows'] if (row['thicknessBand']['lowerExclusiveMm'] is None or t>row['thicknessBand']['lowerExclusiveMm']) and t<=row['thicknessBand']['upperInclusiveMm'] for s in row['selections'] if s['steelMaterialClass']==mat and s['steelStrengthCategory']==fam and pc in groups[s['polarClassGroup']]]
        if len(selections)!=1:return False
        sel=selections[0]; req=fields['requiredHullStructuralSteelGrade']
        if not sel['applicable']:
            if req:return False
            continue
        if req!=[N[sel['requiredGrade']]]:return False
        ranks=table['gradeFamilies'][fam]; actual=str(fields['actualHullStructuralSteelGrade'][0]).split('#')[-1]
        if actual not in ranks or ranks[actual]<ranks[sel['requiredGrade']]:return False
    return True

def corrections(out,rows):
    ontology=Graph().parse(ONTOLOGY)
    assert (N.asBuiltPlateThickness,RDFS.domain,N.steelGradeRequirementCase) in ontology
    index=read(R13/'requirement_term_index.json'); assert index['termOwners']['I2-048']['asBuiltPlateThickness']=='steelGradeRequirementCase'
    transcription=read(HERE/'source_review/table8_transcription.json')
    table=index['dependencyContracts']['I2-048']['tableModel']
    codes={'B':'steelGradeB','D':'steelGradeD','E':'steelGradeE','AH':'steelGradeAh','DH':'steelGradeDh','EH':'steelGradeEh','FH':'steelGradeFh','NA':None}
    source_checks=[]
    for i,row in enumerate(table['rows']):
        assert row['thicknessBand']['upperInclusiveMm']==transcription['upper_inclusive_mm'][i]
        assert row['thicknessBand']['lowerExclusiveMm']==(transcription['upper_inclusive_mm'][i-1] if i else None)
        for j,col in enumerate(transcription['columns']):
            selection=[s for s in row['selections'] if all(s[k]==v for k,v in col.items())]
            assert len(selection)==1
            grade=codes[transcription['grades'][i][j]]
            assert selection[0].get('requiredGrade')==grade and selection[0]['applicable']==(grade is not None)
            source_checks.append(dict(thickness_upper_mm=transcription['upper_inclusive_mm'][i],**col,required_grade=grade,matches=True))
    csvout(out/'table8_source_cell_checks.csv',source_checks)
    log=[]; tablechecks=[]
    for r in rows:
        if r['condition']!='NO_SEMANTIC':continue
        src=Path(r['fixture_path']); dest=out/'corrected_benchmark'/r['rdf_path']; dest.parent.mkdir(parents=True,exist_ok=True)
        g=Graph().parse(src); original=set(g); evidence=''
        if r['requirement_id']=='I2-048':
            for c in g.subjects(RDF.type,N.steelGradeRequirementCase):
                plates=list(g.objects(c,N.steelGradeRequirementCasePlating))
                # Explicit builder evidence, not a name-based positive/negative pairing.
                if not plates and r['case_id']=='I2-048-H-F002':
                    plate=URIRef(str(c).rsplit('/',1)[0]+'/plating')
                    assert (plate,RDF.type,N.plating) in g
                    plates=[plate]
                for plate in plates:
                    for v in list(g.objects(plate,N.asBuiltPlateThickness)):
                        g.remove((plate,N.asBuiltPlateThickness,v));g.add((c,N.asBuiltPlateThickness,v))
            evidence='R13 rdfs:domain and termOwners; dependencyContracts I2-048 comparisonModel; IACS I2.12.4 Table 8; validate_i2_batch_h.py build_048 explicitly creates case/plating for missing-link F002.'
            actual=table_oracle(g,index['dependencyContracts']['I2-048'])
            tablechecks.append(dict(case_id=r['case_id'],expected=r['expected'],source_table_oracle=actual,matches=(actual==(r['expected']=='PASS'))))
        if r['requirement_id']=='TRF-001':
            ship=next(g.subjects(RDF.type,N.ship))
            for v in [N.iceClassSection1Point8Provision2021,N.iceClassDraughtChapter2Provision2021]:g.add((ship,N.applicableIceClassRegulatoryProvision,v))
            evidence='TRAFICOM.pdf p5 section 1.1; source_review/TRAFICOM_full.txt lines 213-225; R13 canonical provision individuals.'
        if set(g)!=original:
            g.serialize(dest,format='turtle')
            log.append(dict(requirement_id=r['requirement_id'],case_id=r['case_id'],expected=r['expected'],evidence=evidence,
                original_path=str(src),corrected_path=str(dest),original_sha256=sha(src),corrected_sha256=sha(dest),
                removed_triples=triples(original-set(g)),added_triples=triples(set(g)-original)))
        else:shutil.copyfile(src,dest)
    assert all(r['matches'] for r in tablechecks), 'Table 8 expectation discrepancy requires review'
    dump(out/'fixture_corrections.json',log);csvout(out/'fixture_corrections.csv',log);csvout(out/'table8_expectation_checks.csv',tablechecks)
    exclusions=[dict(workflow=w,case_id=c,requirement_id=c.rsplit('-',1)[0],reason=reason) for w in WORKFLOWS for c,reason in EXCLUSIONS.items()]
    assert {r['case_id'] for r in exclusions if r['workflow']=='NO_SEMANTIC'}=={r['case_id'] for r in exclusions if r['workflow']=='SINGLESHOT'}
    csvout(out/'exclusions.csv',exclusions)
    csvout(out/'exclusions_by_requirement.csv',[dict(requirement_id='TRF-002',case_ids=list(EXCLUSIONS),excluded_cases_per_workflow=1,remaining_cases_per_workflow=sum(r['requirement_id']=='TRF-002' and r['condition']=='NO_SEMANTIC' and r['case_id'] not in EXCLUSIONS for r in rows))])
    print(f'Corrections: {len(log)} fixtures; {len(tablechecks)} Table-8 labels verified',flush=True)

_ONTO=None

def validate(data, shape, folder, label):
    global _ONTO
    if _ONTO is None:
        _ONTO=Graph().parse(ONTOLOGY)
        sys.path.insert(0,str(PIPE/'src'))
        from nltl_pipeline.validation.sparql_extensions import register_math_functions
        register_math_functions()
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    c,rg,txt=pyshacl.validate(clone(data),shacl_graph=clone(shape),ont_graph=_ONTO,**OPTIONS)
    if not isinstance(rg,Graph):raise RuntimeError(str(txt))
    rg.serialize(folder/f'{label}_report.ttl',format='turtle');(folder/f'{label}_report.txt').write_text(str(txt))
    details=[]
    for v in rg.subjects(RDF.type,S.ValidationResult):
        detail={k:[str(x) for x in rg.objects(v,S[p])] for k,p in [('paths','resultPath'),('components','sourceConstraintComponent'),('focus','focusNode'),('shapes','sourceShape'),('messages','resultMessage')]}
        detail['nested_detail_count']=len(list(rg.objects(v,S.detail)))
        component=str(rg.value(v,S.sourceConstraintComponent)).removeprefix(str(S))
        if component in ['SPARQLConstraintComponent','OrConstraintComponent']:
            detail['logic_fingerprint']=logic_fingerprint(shape,rg.value(v,S.sourceShape),component)
        if component=='SPARQLConstraintComponent':
            constraint=rg.value(v,S.sourceConstraint)
            query=shape.value(constraint,S.select) if constraint is not None else None
            detail['query_sha256']=hashlib.sha256(str(query).encode()).hexdigest() if query is not None else None
        source=rg.value(v,S.sourceShape)
        detail['constraint_parameters']={str(p):[str(x) for x in shape.objects(source,p)] for p in [S.hasValue,S.minInclusive,S.maxInclusive,S['class']] if list(shape.objects(source,p))}
        details.append(detail)
    return dict(conforms=bool(c),violations=details,report_path=str(folder/f'{label}_report.ttl'))

def baseline_job(job):
    r,out=job; out=Path(out);folder=out/'baseline'/r['condition']/r['case_id']
    rec=dict(condition=r['condition'],case_id=r['case_id'],requirement_id=r['requirement_id'],expected=r['expected'],original_eligible=r['original_eligible'])
    if not r['original_eligible']:
        return dict(rec,original_conforms=None,corrected_conforms=None,baseline_matches=True,note='Original no verdict preserved; candidate not executed')
    try:
        assert sha(r['fixture_path'])==r['rdf_sha256'], 'Original fixture changed'
        assert sha(r['shape_path'])==r['generated_shape_sha256'], 'Original shape changed'
        shape=Graph().parse(r['shape_path']); result=validate(Graph().parse(r['fixture_path']),shape,folder,'original')
        rec.update(original_conforms=result['conforms'],original_report=result['report_path'],baseline_matches=result['conforms']==truth(r['actual_conforms']))
        corrected=out/'corrected_benchmark'/r['rdf_path']
        if sha(corrected)==r['rdf_sha256']: rec.update(corrected_conforms=result['conforms'],corrected_report=result['report_path'],corrected_reuses_identical_fixture=True)
        else:
            result=validate(Graph().parse(corrected),shape,folder,'corrected');rec.update(corrected_conforms=result['conforms'],corrected_report=result['report_path'])
    except Exception as e:rec.update(baseline_matches=False,error=f'{type(e).__name__}: {e}')
    return rec

def parallel(jobs,fn,workers):
    results=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(fn,j) for j in jobs]
        for f in as_completed(futures):
            results.append(f.result())
            if len(results)%100==0:print(f'Completed {len(results)}/{len(jobs)}',flush=True)
    return sorted(results,key=lambda r:(r['condition'],r['case_id'],r.get('arm','')))

def baseline(out,rows,workers):
    result=parallel([(r,str(out)) for r in rows],baseline_job,workers)
    dump(out/'baseline_results.json',result);csvout(out/'baseline_results.csv',result)
    differences=[r for r in result if not r['baseline_matches']]
    dump(out/'baseline_differences.json',differences)
    if differences:raise RuntimeError(f'{len(differences)} baseline differences; corrected aggregate results withheld. Inspect baseline_differences.json.')
    print('All original Boolean verdicts reproduced; original no-verdict cases preserved.',flush=True)

# Applicable-branch evaluation is an explanation probe, never the full verdict.
def branch_shape(g,data,w):
    h=clone(g);ship=next(h.subjects(S.targetClass,N.ship));head=h.value(ship,S['or'])
    if head is None:return h
    branches=list(Collection(h,head));category=data.value(next(data.subjects(RDF.type,N.ship)),N.shipCategory)
    if w=='NO_SEMANTIC':
        selected=[x for x in branches if ('CategoryABShape' in str(x))==(category in (N.polarShipCategoryA,N.polarShipCategoryB))]
    else:
        strengthened=data.value(next(data.subjects(RDF.type,N.ship)),N.shipIceStrengthened)
        selected=[x for x in branches if any((p,S.hasValue,category) in h for p in h.objects(x,S.property)) and (
            category!=N.polarShipCategoryC or any((p,S.hasValue,strengthened) in h for p in h.objects(x,S.property))) ]
    assert len(selected)==1, 'Applicable branch unresolved'
    h.remove((ship,S['or'],head));h.add((ship,S.node,selected[0]));return h

def diagnostic_shape(g):
    h=clone(g)
    for p in list(h.subjects(S.path,N.machineryComponentType)):
        h.remove((p,S.path,N.machineryComponentType));head=BNode();Collection(h,head,[N.hasComponent,N.machineryComponentType]);h.add((p,S.path,head))
    constants=set(h.objects(None,S.hasValue))
    for head in h.objects(None,S['in']):constants.update(Collection(h,head))
    repl={x:Literal(str(x),datatype=XSD.string) for x in constants if isinstance(x,Literal) and x.datatype is None and x.language is None}
    out=Graph()
    for t in h:out.add(tuple(repl.get(x,x) for x in t))
    return out

def classify(eligible,negative,repaired,intended,unexpected):
    if not eligible:return 'NO_VERDICT'
    if negative is None or repaired is None:return 'UNRESOLVED_REASON'
    if negative:return 'MISSED_INTENDED_DEFECT'
    if unexpected or not repaired:return 'MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE'
    if intended:return 'STRICT_INTENDED_MATCH'
    return 'UNRESOLVED_REASON'

def match_semantics(details,spec,w):
    intended=[];unexpected=[];wrappers=[]
    allowed=spec['admissible_semantics'][w]
    for v in details:
        component=[x.removeprefix(str(S)) for x in v['components']]
        if component==['NodeConstraintComponent'] and spec['requirement']=='IMO-049' and v.get('nested_detail_count',0)>0 and (not v['paths'] or set(v['paths'])<={str(N.hasComponent),str(N.hasApprovalRecord)}):
            wrappers.append(v);continue # branch report contains the nested property failures
        if component==['NodeConstraintComponent'] and v.get('nested_detail_count',0)>0 and any(set(v['paths'])==set(a['paths']) and set(v['focus'])==set(a['focus']) for a in spec.get('reviewed_wrappers',[])):
            wrappers.append(v);continue
        ok=any(set(v['paths'])==set(a['paths']) and set(component)==set(a['components']) and (not a.get('focus') or set(v['focus'])==set(a['focus'])) and (bool(a.get('logic_fingerprint') or a.get('query_sha256')) if not a['paths'] else True) and (a.get('logic_fingerprint') is None or v.get('logic_fingerprint')==a['logic_fingerprint']) and (a.get('query_sha256') is None or v.get('query_sha256')==a['query_sha256']) and all(v.get('constraint_parameters',{}).get(p)==values for p,values in a.get('expected_constraint_parameters',{}).items()) for a in allowed)
        (intended if ok else unexpected).append(v)
    return intended,unexpected,wrappers

def reviewed_fixture_oracle(g,requirement):
    """Bounded pilot source/representation check independent of generated SHACL."""
    from reviewed_oracles import SUPPORTED, inspect_fixture
    if requirement in SUPPORTED:return not inspect_fixture(g,requirement)['defects']
    ships=list(g.subjects(RDF.type,N.ship))
    if len(ships)!=1:return False
    ship=ships[0]
    def one(s,p):
        vs=list(g.objects(s,p));return vs[0] if len(vs)==1 else None
    if requirement=='I2-001':
        date=one(ship,N.constructionContractDate);value=one(ship,N.urI2RevisionApplicability)
        return date is not None and value is not None and value.toPython()==(str(date)>='2021-01-01')
    if requirement=='IMO-001':
        ice=one(ship,N.designIceCondition);category=list(g.objects(ship,N.shipCategory))
        return ice is not None and (ice!=N.mediumFirstYearIceWithPossibleOldIceInclusions or category==[N.polarShipCategoryA])
    if requirement=='TRF-001':
        date=one(ship,N.constructionContractDate);edition=one(ship,N.applicableIceClassRegulationEdition)
        provisions=set(g.objects(ship,N.applicableIceClassRegulatoryProvision))
        return date is not None and edition is not None and {N.iceClassSection1Point8Provision2021,N.iceClassDraughtChapter2Provision2021}<=provisions and (str(date)<'2021-07-05' or edition==N.iceClassRegulationEdition2021)
    if requirement=='IMO-049':
        category=one(ship,N.shipCategory);strengthened=one(ship,N.shipIceStrengthened)
        if category not in (N.polarShipCategoryA,N.polarShipCategoryB,N.polarShipCategoryC) or strengthened is None or strengthened.toPython() is not True:return False
        components=list(g.objects(ship,N.hasComponent))
        if not components:return False
        for c in components:
            if one(c,N.machineryComponentType) is None:return False
            records=list(g.objects(c,N.hasApprovalRecord))
            if not records:return False
            for record in records:
                if one(record,N.scantlingApprovalStatus)!=N.evidenceStateApproved:return False
                if str(one(record,N.approvingAuthority)) not in ['Administration','recognized organization accepted by the Administration']:return False
                standard=str(one(record,N.approvalStandard))
                if category in (N.polarShipCategoryA,N.polarShipCategoryB):
                    if standard not in ['standard acceptable to the Organization','another standard offering an equivalent level of safety']:return False
                else:
                    if standard!='acceptable standard adequate for operating ice type and concentration' or one(record,N.operatingIceType) is None:return False
                    concentration=one(record,N.operatingIceConcentration)
                    if concentration is None or one(concentration,Q.numericValue) is None or one(concentration,Q.unit)!=URIRef('http://qudt.org/vocab/unit/UNITLESS'):return False
        return True
    raise ValueError('No reviewed oracle for '+requirement)

def reviewed_job(job):
    r,spec,arm,out=job;out=Path(out);folder=out/'reviewed'/arm/r['condition']/r['case_id'];folder.mkdir(parents=True,exist_ok=True)
    result=dict(condition=r['condition'],workflow=r['workflow'],case_id=r['case_id'],requirement_id=r['requirement_id'],arm=arm,original_eligible=r['original_eligible'],specification=str(out/'reviewed_failure_specs.json'))
    try:
        bad=Graph().parse(Path(r['fixture_path']) if arm=='original' else r.get('audit_corrected_fixture_path',out/'corrected_benchmark'/r['rdf_path']))
        good=clone(bad);removed=load_triples(spec['removed_triples']);added=load_triples(spec['added_triples'])
        assert removed<=set(good), 'Repair precondition does not match fixture'
        assert not (added & set(good)), 'Repair adds an existing triple'
        for t in removed:good.remove(t)
        for t in added:good.add(t)
        assert set(bad)-set(good)==removed and set(good)-set(bad)==added
        result['fixture_oracle_negative']=reviewed_fixture_oracle(bad,r['requirement_id'])
        result['fixture_oracle_repaired']=reviewed_fixture_oracle(good,r['requirement_id'])
        if spec.get('fixture_oracle'):
            from reviewed_oracles import inspect_fixture
            result['independent_fixture_review']={label:inspect_fixture(g,r['requirement_id']) for label,g in [('negative',bad),('repaired',good)]}
            assert result['independent_fixture_review']['negative']['defects']==spec['fixture_oracle']['expected_negative_defects'], 'Unrelated or absent fixture defect'
            assert result['independent_fixture_review']['repaired']['defects']==[], 'Repaired fixture has an independent-oracle defect'
        if arm!='original':
            assert result['fixture_oracle_negative'] is False and result['fixture_oracle_repaired'] is True, 'Fixture fails source-backed repair review; do not judge shape'
        # N-Triples is a Turtle subset and preserves decimal lexical forms;
        # Turtle shorthand can silently serialize "7"^^xsd:decimal as 7.0.
        for label,g in [('negative',bad),('repaired',good)]:g.serialize(folder/f'{label}_fixture.ttl',format='nt',encoding='utf-8')
        shape_path=r['shape_path']
        if not shape_path or not Path(shape_path).is_file():
            shape_path=spec.get('diagnostic_candidate_paths',{}).get(r['condition'],'') if arm=='diagnostic_shape_repairs' else ''
            if shape_path:assert sha(shape_path)==spec['diagnostic_candidate_sha256']
        if not shape_path or (not r['original_eligible'] and arm!='diagnostic_shape_repairs'):
            result.update(status='NO_VERDICT',note='Original no verdict retained; fixture pair reviewed and saved, no eligible shape report')
            dump(folder/'record.json',result);return result
        assert sha(shape_path)==(r['generated_shape_sha256'] or spec.get('diagnostic_candidate_sha256')), 'Historical shape changed'
        shape=Graph().parse(shape_path);original_shape=clone(shape)
        if arm=='diagnostic_shape_repairs' and r['requirement_id']=='IMO-049':shape=diagnostic_shape(shape)
        if arm=='diagnostic_shape_repairs' and r['requirement_id']=='TRF-018':
            for node in list(shape.subjects(S.hasValue,Q.KiloW)):
                shape.remove((node,S.hasValue,Q.KiloW));shape.add((node,S.hasValue,URIRef('http://qudt.org/vocab/unit/KiloW')))
        if arm=='diagnostic_shape_repairs':dump(folder/'shape_transformations.json',dict(original_path=shape_path,original_sha256=sha(shape_path),removed_triples=triples(set(original_shape)-set(shape)),added_triples=triples(set(shape)-set(original_shape)),note='Only logged owner/string or power-unit namespace probes; regulatory formulas and cardinalities unchanged. Diagnostic only.'))
        result['input_shape_sha256']=sha(shape_path)
        save_evaluated_shape(shape,original_shape,shape_path,folder/'evaluated_shape.ttl')
        for label,g in [('negative',bad),('repaired',good)]:
            g.serialize(folder/f'{label}_fixture.ttl',format='nt',encoding='utf-8')
            result[label]=validate(g,shape,folder,label)
            if r['requirement_id']=='IMO-049':result[label+'_branch']=validate(g,branch_shape(shape,g,r['condition']),folder,label+'_applicable_branch')
        details=result.get('negative_branch',result['negative'])['violations']
        intended,unexpected,wrappers=match_semantics(details,spec,r['condition'])
        result.update(intended_violations=intended,unrelated_violations=unexpected,logical_wrappers=wrappers)
        result['status']=classify(r['original_eligible'],result['negative']['conforms'],result['repaired']['conforms'],bool(intended),bool(unexpected))
        result['diagnostic_observation']=classify(True,result['negative']['conforms'],result['repaired']['conforms'],bool(intended),bool(unexpected)) if arm=='diagnostic_shape_repairs' else None
    except Exception as e:result.update(status='NO_VERDICT' if not r['original_eligible'] else 'UNRESOLVED_REASON',error=f'{type(e).__name__}: {e}')
    dump(folder/'record.json',result);return result

def reviewed(out,rows,workers,specifications=None,base_run=None):
    specs=expected_specs(specifications)
    assert list(specs.values())==read(out/'reviewed_failure_specs.json'), 'Reviewed specifications changed; start a new audit run'
    jobs=[(dict(r,audit_corrected_fixture_path=str((base_run or out)/'corrected_benchmark'/r['rdf_path'])),specs[r['case_id']],a,str(out)) for r in rows if r['case_id'] in specs and r['case_id'] not in EXCLUSIONS for a in ['original','corrected_fixtures','diagnostic_shape_repairs']]
    results=parallel(jobs,reviewed_job,workers);dump(out/'strict_results.json',results)
    csvout(out/'strict_results.csv',[{k:v for k,v in r.items() if k not in ['negative','repaired','negative_branch','repaired_branch']} for r in results])
    csvout(out/'diagnostic_shape_repair_results.csv',[r for r in results if r['arm']=='diagnostic_shape_repairs'])
    bykey={(r['condition'],r['case_id']):r for r in results if r['arm']=='corrected_fixtures'}
    for r in rows:
        if r['case_id'] in EXCLUSIONS:r['review_status']='INVALID_TEST_EXCLUDED'
        elif (r['condition'],r['case_id']) in bykey:r['review_status']=bykey[r['condition'],r['case_id']]['status']
    csvout(out/'full_case_ledger.csv',rows)
    print(f'Reviewed {len(specs)} explicit negative specifications; {len(results)} workflow/arm records.',flush=True)

def unit_diagnostics(out,rows):
    """Explicit small I2-048 probe; no reviewed/strict claims for these cases."""
    selected={'I2-048-H-T001','I2-048-H-F011','I2-048-H-F012','I2-048-H-F013','I2-048-H-F014'}
    assert selected<={r['case_id'] for r in rows}, 'Diagnostic selection contains missing retained IDs'
    records=[]
    for r in rows:
        if r['case_id'] not in selected:continue
        folder=out/'unit_diagnostics'/r['condition']/r['case_id'];folder.mkdir(parents=True,exist_ok=True)
        shape=Graph().parse(r['shape_path']);fixed=clone(shape);edits=[]
        for node,query in list(fixed.subject_objects(S.select)):
            before=str(query)
            after=before.replace('qudt:unit nltl:iacsUrI2Table8','nltl:tableReference nltl:iacsUrI2Table8')
            if after!=before:
                fixed.remove((node,S.select,query));fixed.add((node,S.select,Literal(after)))
                edits.append(dict(old_query=before,new_query=after,reason='R13 tableReference belongs on steelGradeRequirementCase; qudt:unit belongs on a quantity and must be MilliM. No Table-8 logic changes.'))
        fixed.serialize(folder/'diagnostic_shape.ttl',format='turtle')
        fixture=out/'corrected_benchmark'/r['rdf_path'];data=Graph().parse(fixture)
        rec=dict(condition=r['condition'],case_id=r['case_id'],requirement_id=r['requirement_id'],expected=r['expected'],fixture=str(fixture),shape=r['shape_path'],original_shape_sha256=sha(r['shape_path']),transformations=edits,diagnostic_only=True,strict_status='NOT_AUDITED')
        for label,g in [('unchanged_shape',shape),('unit_predicate_probe',fixed)]:rec[label]=validate(data,g,folder,label)
        dump(folder/'record.json',rec);records.append(rec)
    dump(out/'unit_diagnostic_results.json',records);csvout(out/'unit_diagnostic_results.csv',records)

def metrics(rows,results,field,exclude):
    idx={(r['condition'],r['case_id']):r for r in results};summary=[];fig=[];per=[]
    for w in WORKFLOWS:
        selected=[r for r in rows if r['condition']==w and (not exclude or r['case_id'] not in EXCLUSIONS)]
        groups=defaultdict(list)
        for r in selected:groups[r['requirement_id']].append(r)
        for req,rs in groups.items():
            correct=sum(idx[w,r['case_id']].get(field)==(r['expected']=='PASS') for r in rs)
            per.append(dict(condition=w,requirement_id=req,cases=len(rs),correct=correct,accuracy=correct/len(rs)))
        macro=sum(r['accuracy'] for r in per if r['condition']==w)/len(groups)
        correct=sum(idx[w,r['case_id']].get(field)==(r['expected']=='PASS') for r in selected)
        summary.append(dict(workflow=WORKFLOWS[w],cases=len(selected),requirements=len(groups),correct=correct,pooled_accuracy=correct/len(selected),requirement_averaged_accuracy=macro,no_verdict=sum(idx[w,r['case_id']].get(field) is None for r in selected)))
        for exp in ['PASS','FAIL']:
            rs=[r for r in selected if r['expected']==exp];counts=Counter('NO_VERDICT' if idx[w,r['case_id']].get(field) is None else ('PASS' if idx[w,r['case_id']][field] else 'FAIL') for r in rs)
            for observed in ['PASS','FAIL','NO_VERDICT']:fig.append(dict(workflow=WORKFLOWS[w],expected=exp,observed=observed,count=counts[observed],denominator=len(rs),percentage=100*counts[observed]/len(rs) if rs else None))
    return summary,fig,per

def verify_results(out,rows,baseline_rows,strict):
    checks=dict(retained_rows=len(rows),original_boolean_verdicts_reproduced=sum(r['original_eligible'] for r in baseline_rows),original_no_verdict_count=sum(not r['original_eligible'] for r in baseline_rows))
    assert {(r['condition'],r['case_id']) for r in rows}=={(r['condition'],r['case_id']) for r in baseline_rows}
    assert all(r['original_conforms'] is None and r['corrected_conforms'] is None for r in baseline_rows if not r['original_eligible'])
    checks['no_verdict_preserved']=True
    with (out/'exclusions.csv').open() as f:ex=list(csv.DictReader(f))
    assert all({r['case_id'] for r in ex if r['workflow']==w}==set(EXCLUSIONS) for w in WORKFLOWS)
    checks['identical_exclusions_across_workflows']=True
    corrected_hashes={r['case_id']:r['corrected_sha256'] for r in read(out/'fixture_corrections.json')}
    for r in rows:
        if r['condition']=='NO_SEMANTIC':assert sha(out/'corrected_benchmark'/r['rdf_path'])==corrected_hashes.get(r['case_id'],r['rdf_sha256'])
    checks['corrected_fixture_hashes_verified']=True
    index={(r['condition'],r['case_id']):r for r in rows};specs=expected_specs()
    for r in strict:
        if not r['original_eligible']:assert r['status']=='NO_VERDICT'
        if 'negative' not in r:continue
        intended,unexpected,_=match_semantics(r.get('negative_branch',r['negative'])['violations'],specs[r['case_id']],r['condition'])
        assert r['status']==classify(r['original_eligible'],r['negative']['conforms'],r['repaired']['conforms'],bool(intended),bool(unexpected))
        if r['status']=='STRICT_INTENDED_MATCH':
            assert r['fixture_oracle_negative'] is False and r['fixture_oracle_repaired'] is True
        if r['arm']!='diagnostic_shape_repairs':
            evaluated=Graph().parse(out/'reviewed'/r['arm']/r['condition']/r['case_id']/'evaluated_shape.ttl')
            original=Graph().parse(index[r['condition'],r['case_id']]['shape_path'])
            assert to_isomorphic(evaluated)==to_isomorphic(original)
    checks.update(no_strict_credit_for_ineligible_candidates=True,strict_conditions_enforced=True,main_arm_shapes_unchanged=True,new_llm_calls=0)
    dump(out/'verification_checks.json',checks)

def report(out,rows):
    results=read(out/'baseline_results.json')
    assert len(results)==4320 and all(r['baseline_matches'] for r in results), 'Resolve baseline differences before aggregation'
    for path,h in read(out/'source_hashes.json').items():assert sha(path)==h,f'Original changed during audit: {path}'
    reports={}
    for arm,field,ex in [('original','original_conforms',False),('corrected_before_exclusions','corrected_conforms',False),('corrected_after_exclusions','corrected_conforms',True)]:
        summary,fig,per=metrics(rows,results,field,ex);reports[arm]=summary
        csvout(out/f'{arm}_ordinary_verdicts.csv',summary);csvout(out/f'{arm}_figure6.csv',fig);csvout(out/f'{arm}_per_requirement.csv',per)
    strict=read(out/'strict_results.json') if (out/'strict_results.json').exists() else []
    verify_results(out,rows,results,strict)
    strict_index={(r['condition'],r['case_id']):r for r in strict if r['arm']=='corrected_fixtures'}
    for r in rows:
        if r['case_id'] in EXCLUSIONS:r['review_status']='INVALID_TEST_EXCLUDED'
        elif (r['condition'],r['case_id']) in strict_index:r['review_status']=strict_index[r['condition'],r['case_id']]['status']
    csvout(out/'full_case_ledger.csv',rows)
    summaries=[]
    for arm in ['original','corrected_fixtures','diagnostic_shape_repairs']:
        for w in WORKFLOWS:
            rs=[r for r in strict if r['condition']==w and r['arm']==arm];c=Counter(r['status'] for r in rs)
            eligible=sum(r['original_eligible'] for r in rs)
            summaries.append(dict(workflow=WORKFLOWS[w],arm=arm,reviewed_negative_denominator=len(rs),eligible_denominator=eligible,strict_count=c['STRICT_INTENDED_MATCH'],strict_percentage=100*c['STRICT_INTENDED_MATCH']/len(rs) if rs else None,strict_percentage_of_eligible=100*c['STRICT_INTENDED_MATCH']/eligible if eligible else None,status_counts=dict(c)))
    csvout(out/'strict_summary.csv',summaries)
    strict_per=[]
    for arm in ['original','corrected_fixtures','diagnostic_shape_repairs']:
        for w in WORKFLOWS:
            reqs=sorted({r['requirement_id'] for r in strict if r['condition']==w and r['arm']==arm})
            for req in reqs:
                rs=[r for r in strict if r['condition']==w and r['arm']==arm and r['requirement_id']==req]
                credit=sum(r['status']=='STRICT_INTENDED_MATCH' for r in rs)
                strict_per.append(dict(workflow=WORKFLOWS[w],arm=arm,requirement_id=req,reviewed_negative_denominator=len(rs),strict_count=credit,strict_accuracy=credit/len(rs)))
    csvout(out/'strict_per_requirement.csv',strict_per)
    if strict_per:csvout(out/'strict_requirement_averages.csv',[dict(workflow=WORKFLOWS[w],arm=arm,reviewed_requirements=len([r for r in strict_per if r['workflow']==WORKFLOWS[w] and r['arm']==arm]),requirement_averaged_strict_accuracy=sum(r['strict_accuracy'] for r in strict_per if r['workflow']==WORKFLOWS[w] and r['arm']==arm)/len({r['requirement_id'] for r in strict_per if r['workflow']==WORKFLOWS[w] and r['arm']==arm})) for w in WORKFLOWS for arm in ['original','corrected_fixtures','diagnostic_shape_repairs']])
    audited={s['case'] for s in expected_specs().values()}
    unresolved=[dict(workflow=r['workflow'],requirement_id=r['requirement_id'],case_id=r['case_id'],status='INVALID_TEST_EXCLUDED' if r['case_id'] in EXCLUSIONS else 'NOT_AUDITED',reason=EXCLUSIONS.get(r['case_id'],'No reviewed failure specification; ordinary verdict only.')) for r in rows if r['case_id'] not in audited]
    unresolved.extend(dict(workflow=r['workflow'],requirement_id=r['requirement_id'],case_id=r['case_id'],status=r['status'],reason=r.get('error','Original no verdict preserved')) for r in strict if r['arm']=='corrected_fixtures' and r['status'] in ['NO_VERDICT','UNRESOLVED_REASON'])
    csvout(out/'unresolved_cases.csv',unresolved)
    unit=read(out/'unit_diagnostic_results.json') if (out/'unit_diagnostic_results.json').exists() else []
    unit_summary=[dict(condition=r['condition'],case_id=r['case_id'],expected=r['expected'],unchanged_conforms=r['unchanged_shape']['conforms'],diagnostic_conforms=r['unit_predicate_probe']['conforms'],transformations=len(r['transformations'])) for r in unit]
    dump(out/'report.json',dict(ordinary=reports,strict=summaries,diagnostic_unit_probe=unit_summary,exclusions=EXCLUSIONS,strict_scope='14 purposively reviewed negatives, not a whole-benchmark estimate',originals_verified_unchanged=True,llm_calls=0))
    lines=['# Evaluation audit results','', 'Ordinary verdict agreement and strict intended-failure credit are separate. Original no-verdict cases remain in accuracy denominators and receive zero credit.','']
    for arm,rs in reports.items():
        lines.append(arm)
        for r in rs:lines.append(f"- {r['workflow']}: {r['correct']}/{r['cases']} ordinary agreement; requirement mean {100*r['requirement_averaged_accuracy']:.4f}% across {r['requirements']} requirements; {r['no_verdict']} no verdict.")
        lines.append('')
    for r in summaries:lines.append(f"- {r['workflow']} / {r['arm']}: strict {r['strict_count']}/{r['reviewed_negative_denominator']} reviewed negatives ({r['eligible_denominator']} originally eligible). {r['status_counts']}")
    lines.extend(['','One new exclusion per workflow: TRF-002-F02. No expected labels changed.','Unaudited cases remain NOT_AUDITED. Figure 6 CSVs retain expected PASS/FAIL strata and give cell counts, percentages and denominators.','Diagnostic shape transformations never enter the main accuracy results.','Missing evidence and source provenance: inventory.json and source_hashes.json.'])
    if unit:
        lines.extend(['','I2-048 unit-predicate diagnostic:'])
        for r in unit_summary:lines.append(f"- {WORKFLOWS[r['condition']]} / {r['case_id']}: expected {r['expected']}; unchanged conforms={r['unchanged_conforms']}; diagnostic conforms={r['diagnostic_conforms']}; transformations={r['transformations']}.")
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=['inventory','baseline','pilot','reviewed','report'],required=True)
    p.add_argument('--archive',type=Path,default=Path.home()/'Downloads/NLTL_v2_manuscript_and_data.zip')
    p.add_argument('--run-dir',type=Path,help='Continue a timestamped audit directory; originals are never edited')
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--specifications',type=Path,help='Explicit reviewed specification file for a versioned extension batch')
    p.add_argument('--review-batch',help='Write reviewed/report outputs under the completed run/review_batches/NAME; reuse baseline without rerunning it')
    args=p.parse_args();out=args.run_dir.resolve() if args.run_dir else HERE/'outputs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if args.workers<1:p.error('--workers must be positive')
    out.mkdir(parents=True,exist_ok=True);print(f'Audit directory: {out}',flush=True)
    if not (out/'retained_rows.json').exists():inventory(out,args.archive)
    env=read(out/'environment.json')
    assert (platform.python_version(),rdflib.__version__,pyshacl.__version__)==(env['python'],env['rdflib'],env['pyshacl']), 'Environment changed'
    phase_stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    dump(out/'phase_receipts'/f'{args.phase}_{phase_stamp}.json',dict(command=[sys.executable,*sys.argv],audit_code_sha256=sha(__file__),specification_sha256=sha(args.specifications or HERE/'reviewed_failure_specs.json'),specification_path=str(args.specifications or HERE/'reviewed_failure_specs.json'),review_batch=args.review_batch,environment=env))
    rows=read(out/'retained_rows.json')
    if args.review_batch:
        if args.phase not in ['reviewed','report']:p.error('--review-batch supports reviewed/report only; baseline is reused')
        if not args.specifications:p.error('--review-batch requires --specifications')
        if Path(args.review_batch).name!=args.review_batch or args.review_batch in ['.','..']:p.error('Invalid batch name')
        batch=out/'review_batches'/args.review_batch;batch.mkdir(parents=True,exist_ok=True)
        snapshot=batch/'reviewed_failure_specs.json'
        if snapshot.exists():assert read(snapshot)==read(args.specifications), 'Batch specification snapshot changed; use a new batch name'
        else:dump(snapshot,read(args.specifications))
        if args.phase=='reviewed':reviewed(batch,rows,args.workers,args.specifications,out)
        else:
            from batch_report import build_report
            build_report(out,batch,args.specifications)
        return
    if args.phase=='inventory':return
    if args.phase=='baseline':baseline(out,rows,args.workers)
    if args.phase in ['pilot','reviewed']:reviewed(out,rows,args.workers)
    if args.phase=='pilot':unit_diagnostics(out,rows)
    if args.phase=='report':report(out,rows)
if __name__=='__main__':main()
