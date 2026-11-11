"""Independent, strictly post-generation evaluation of this TRF-010 pilot only."""
from pathlib import Path
import json,hashlib,shutil,collections,time
from rdflib import Graph,URIRef,Literal,RDF,RDFS,XSD
from rdflib.namespace import SH
from nltlv2.core import Project,write,load,digest,offline_network_guard
from nltlv2.schema import Schema,N
from nltlv2.evaluation import oracle,validate_pair_graph,strict_status
from nltlv2.study import budget_analysis
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');p=Project(ROOT);pilot=p.path('outputs/experiments/20261111T123517321850Z_TRF010_LIVE_DEV');assert (pilot/'execution_outcomes.json').is_file()
assert load(pilot/'nltl/run.json')['status']=='ACCEPTED' # generation complete, no future calls permitted here
out=pilot/'evaluation';out.mkdir(exist_ok=False);shutil.copyfile(__file__,out/'evaluate_pilot.py');schema=Schema(p);selection=load(p.path('evaluation/selections/regression_core.json'));cases=[c for c in selection['cases'] if c['requirement_id']=='TRF-010'];assert len(cases)==8
write(out/'reviewed_selection.json',dict(requirement='TRF-010',cases=cases,scope='Six positive, two negative; same cases for both workflows; no exclusions'))
inputs=out/'fixtures';inputs.mkdir()
for c in cases:
 for key in ['fixture','counterfactual']:
  if c.get(key):
   f=p.path(c[key]);assert hashlib.sha256(f.read_bytes()).hexdigest()==c[key+'_sha256'];shutil.copyfile(f,inputs/f.name)
write(out/'validation_options.json',dict(inference='rdfs',advanced=True,abort_on_first=False,allow_infos=False,allow_warnings=False,meta_shacl=False,inplace=False,ontology='schema/Schema_for_NLTL.ttl',scope='Only TRF-010; unchanged generated candidates, no transformed-shape arm'))
rows=[];start=time.monotonic()
with offline_network_guard():
 for method,folder in [('Single-shot','single_shot'),('NLTL','nltl')]:
  for candidate in sorted((pilot/folder).glob('candidate_*.ttl')):
   version=int(candidate.stem.split('_')[-1]);dest=out/folder/candidate.stem;dest.mkdir(parents=True);shapes=Graph().parse(candidate);code=candidate.read_text();assert digest(code)==load(candidate.with_suffix('.json'))['sha256']
   for c in cases:
    cid=c['case_id'];d=dest/cid;d.mkdir();g=Graph().parse(inputs/Path(c['fixture']).name);oc=oracle(g,'TRF-010');assert oc['conforms']==(c['expected']=='PASS');verdict,report=validate_pair_graph(g,shapes,schema)
    if report is not None:report.serialize(d/'report.ttl',format='turtle')
    row=dict(method=method,candidate_version=version,candidate_sha256=digest(code),case_id=cid,expected=c['expected'],fixture=c['fixture'],source_oracle=oc,verdict=verdict,ordinary_agreement=None if verdict['conforms'] is None else verdict['conforms']==(c['expected']=='PASS'))
    if c['expected']=='FAIL':
     repaired=Graph().parse(inputs/Path(c['counterfactual']).name);ro=oracle(repaired,'TRF-010');assert ro['conforms'] is True;rv,rr=validate_pair_graph(repaired,shapes,schema)
     if rr is not None:rr.serialize(d/'repaired_report.ttl',format='turtle')
     if verdict['conforms'] is None or rv['conforms'] is None:status='NO_VERDICT';evidence=dict(reason='Execution failure; no offline credit')
     elif verdict['conforms'] is True:status='MISSED_INTENDED_DEFECT';evidence=dict(reason='Negative accepted by full unchanged shape despite independent source-oracle failure',source_defect=oc['issues'],negative_conforms=True,repaired_conforms=rv['conforms'])
     else:
      # Source-backed reviewed missing-value negative: interpret exact SHACL constraint semantics, not message or bnode text.
      results=list(report.subjects(RDF.type,SH.ValidationResult));cert=[]
      for result in results:
       source=report.value(result,SH.sourceShape);param=shapes.value(source,SH.minCount);path=report.value(result,SH.resultPath);component=report.value(result,SH.sourceConstraintComponent);focus=report.value(result,SH.focusNode)
       match=(cid=='TRF-010-F02' and path==N.iceClass and component==SH.MinCountConstraintComponent and param==Literal(1) and (focus,RDF.type,N.ship) in g and not list(g.objects(focus,N.iceClass)))
       cert.append(dict(intended_match=bool(match),focus=str(focus),path=str(path),component=str(component),source_path=str(shapes.value(source,SH.path)),min_count=param.n3() if param is not None else None,semantic_evidence='SHACL minCount=1 on ship/iceClass detects the certified missing assignment; repaired fixture changes only this property.'))
      resolved=bool(cert) and all(x['intended_match'] for x in cert);status=strict_status(verdict['conforms'],rv['conforms'],resolved,False,certified=True,attribution_resolved=resolved);evidence=dict(review='Post-generation source/contract/constraint adjudication v1; separate from conservative automatic query recognizer',constraints=cert,repaired_full_shape_conforms=rv['conforms'],source_clause='1.8',specification='evaluation/specifications/intended_negative_cases.json#/TRF-010-F02',not_based_on_message_text_or_bnode_ids=True)
     row.update(repaired_source_oracle=ro,repaired_verdict=rv,strict_status=status,attribution_evidence=evidence)
    rows.append(row);write(d/'case_result.json',row)
 summaries=[]
 for method in ['Single-shot','NLTL']:
  versions=sorted({x['candidate_version'] for x in rows if x['method']==method})
  for version in versions:
   rs=[x for x in rows if x['method']==method and x['candidate_version']==version];ps=[x for x in rs if x['expected']=='PASS'];ns=[x for x in rs if x['expected']=='FAIL'];counts=dict(collections.Counter(x['strict_status'] for x in ns));summaries.append(dict(method=method,candidate_version=version,positive_acceptance=sum(x['verdict']['conforms'] is True for x in ps),positive_denominator=len(ps),strict_intended_detection=counts.get('VERIFIED_INTENDED_DETECTION',0),negative_denominator=len(ns),negative_classifications=counts,ordinary_agreement=sum(x['ordinary_agreement'] is True for x in rs),ordinary_denominator=len(rs),no_verdict=sum(x['verdict']['conforms'] is None for x in rs),unresolved=counts.get('UNRESOLVED_ATTRIBUTION',0),unrelated_rejection=counts.get('UNRELATED_OR_ADDITIONAL_FAILURE',0),repaired_acceptance=sum(x['repaired_verdict']['conforms'] is True for x in ns),repaired_denominator=len(ns)))
 result=dict(scope='One development requirement only; no population/advantage inference',requirement_id='TRF-010',case_ids=[c['case_id'] for c in cases],exclusions=[],common_positive_denominator=6,common_negative_denominator=2,summaries=summaries,rows=rows,elapsed_seconds=time.monotonic()-start,evaluation_started_after_generation=True,no_feedback_to_runner=True,no_shape_changes=True)
 write(out/'independent_results.json',result)
 history=load(pilot/'nltl/run.json');budgets=budget_analysis([history]);byversion={s['candidate_version']:s for s in summaries if s['method']=='NLTL'}
 for b in budgets:
  b['external_evaluation']=byversion.get(b['selected_version']);b['policy']='First internally accepted candidate in saved prefix; no extra generation or evaluation-based selection'
 write(out/'budget_results_2_to_6.json',budgets)
 print(json.dumps(dict(summaries=summaries,budgets=[dict(budget=b['budget'],selected_version=b['selected_version'],status=b['status']) for b in budgets],elapsed_seconds=result['elapsed_seconds']),indent=2))
