"""Independent offline TRF-010 evaluation; run only after an arm has finished.
No model transport or generation/repair orchestration is imported here.
"""
from pathlib import Path
import argparse,collections,json,shutil,time,hashlib
from rdflib import Graph,URIRef,Literal,RDF
from rdflib.namespace import SH
from nltlv2.core import Project,load,write,offline_network_guard,digest
from nltlv2.schema import Schema,N
from nltlv2.evaluation import oracle,validate_pair_graph,strict_status
from nltlv2.enumerations import rdf_list
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');STATE=Path('/private/tmp/nltlv2_bounded_state_20261113.json')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def summarize(rows):
 positives=[r for r in rows if r['expected']=='PASS'];negatives=[r for r in rows if r['expected']=='FAIL'];counts=dict(collections.Counter(r['strict_status'] for r in negatives))
 return dict(positive_acceptance=sum(r['verdict']['conforms'] is True for r in positives),positive_denominator=len(positives),strict_intended_detection=counts.get('VERIFIED_INTENDED_DETECTION',0),negative_denominator=len(negatives),strict_classifications=counts,unrelated_rejection=counts.get('UNRELATED_OR_ADDITIONAL_FAILURE',0),missed_defects=counts.get('MISSED_INTENDED_DEFECT',0),unresolved_attribution=counts.get('UNRESOLVED_ATTRIBUTION',0),no_verdict=sum(r['verdict']['conforms'] is None for r in rows),ordinary_agreement=sum(r['ordinary_agreement'] is True for r in rows),ordinary_denominator=len(rows),repaired_acceptance=sum(r.get('repaired_verdict',{}).get('conforms') is True for r in negatives),repaired_denominator=len(negatives))

def evaluate(phase):
 state=load(STATE);group=Path(state['group']);arm=Path(state['arm_'+phase]);out=arm/'evaluation';out.mkdir(exist_ok=False);shutil.copyfile(__file__,out/'independent_evaluation.py')
 if phase=='A':assert (arm/'run.json').is_file();folders=[('TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC',arm)]
 else:
  assert (arm/'execution_outcomes.json').is_file();folders=[(m,arm/f) for m,f in [('Single-shot','single_shot'),('NLTL','nltl')] if (arm/f).is_dir()]
 p=Project(group/'snapshot');schema=Schema(p);expected={URIRef(x['iri']) for x in schema.enumeration_obligations['TRF-010'][0]['members']}
 cases=[c for c in load(ROOT/'evaluation/selections/regression_core.json')['cases'] if c['requirement_id']=='TRF-010'];assert len(cases)==8
 write(out/'reviewed_selection.json',dict(case_ids=[c['case_id'] for c in cases],cases=cases,exclusions=[],positive_denominator=6,negative_denominator=2,scope='Only TRF-010; no six-requirement run'))
 inputs=out/'inputs';inputs.mkdir()
 for c in cases:
  for key in ['fixture','counterfactual']:
   if c.get(key):
    assert sha(ROOT/c[key])==c[key+'_sha256'];shutil.copyfile(ROOT/c[key],inputs/Path(c[key]).name)
 write(out/'validation_options.json',dict(inference='rdfs',advanced=True,abort_on_first=False,allow_infos=False,allow_warnings=False,meta_shacl=False,inplace=False,ontology_sha256=sha(group/'snapshot/schema/Schema_for_NLTL.ttl'),frozen_schema=True,transformed_shape_arm=False))
 rows=[];candidates=[];started=time.monotonic()
 with offline_network_guard():
  for method,folder in folders:
   for file in sorted(folder.glob('candidate_*.ttl')):
    version=int(file.stem.split('_')[-1]);metadata=load(file.with_suffix('.json'));code=file.read_text();assert digest(code)==metadata['sha256'];dest=out/('targeted' if phase=='A' else method.replace('-','_'))/file.stem;dest.mkdir(parents=True)
    graphs=None;parse_error=None
    wrapper_failed=(metadata.get('normalization') is None and metadata.get('origin')!='Historical byte-identical seed; not a new generation')
    try:graphs=Graph().parse(data=code,format='turtle')
    except Exception as e:parse_error=type(e).__name__+': '+str(e)
    eligible=not wrapper_failed and not parse_error
    if not eligible:write(dest/'no_verdict_reason.json',dict(wrapper_failed=wrapper_failed,parse_error=parse_error,raw_offline_parse_cannot_create_workflow_credit=True))
    for c in cases:
     cid=c['case_id'];d=dest/cid;d.mkdir();fixture=Graph().parse(inputs/Path(c['fixture']).name);source_oracle=oracle(fixture,'TRF-010');assert source_oracle['conforms']==(c['expected']=='PASS')
     verdict,report=validate_pair_graph(fixture,graphs,schema) if eligible else (dict(conforms=None,error='No eligible extracted executable candidate'),None)
     if report is not None:report.serialize(d/'report.ttl',format='turtle')
     row=dict(arm=phase,label='TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC' if phase=='A' else 'FRESH_PAIRED_DEVELOPMENT_PILOT',method=method,candidate_version=version,candidate_sha256=digest(code),case_id=cid,expected=c['expected'],source_oracle=source_oracle,verdict=verdict,ordinary_agreement=None if verdict['conforms'] is None else verdict['conforms']==(c['expected']=='PASS'),candidate_level_diagnostic=True)
     if c['expected']=='FAIL':
      repaired=Graph().parse(inputs/Path(c['counterfactual']).name);repaired_oracle=oracle(repaired,'TRF-010');assert repaired_oracle['conforms'] is True
      repaired_verdict,repaired_report=validate_pair_graph(repaired,graphs,schema) if eligible else (dict(conforms=None,error='No eligible extracted executable candidate'),None)
      if repaired_report is not None:repaired_report.serialize(d/'repaired_report.ttl',format='turtle')
      meanings=[]
      if report is not None:
       for result in report.subjects(RDF.type,SH.ValidationResult):
        focus=report.value(result,SH.focusNode);path=report.value(result,SH.resultPath);component=report.value(result,SH.sourceConstraintComponent);source=report.value(result,SH.sourceShape);meaning='UNRESOLVED';parameters={}
        if path==N.iceClass and (focus,RDF.type,N.ship) in fixture:
         if component==SH.MinCountConstraintComponent:
          param=graphs.value(source,SH.minCount);parameters['minCount']=param.n3() if param is not None else None
          if cid=='TRF-010-F02' and param==Literal(1) and not list(fixture.objects(focus,N.iceClass)):meaning='INTENDED_MISSING_ASSIGNMENT'
         elif component==SH.InConstraintComponent:
          heads=list(graphs.objects(source,SH['in']));members=set(rdf_list(graphs,heads[0])) if len(heads)==1 else set();parameters['allowed_IRIs']=sorted(map(str,members))
          value=report.value(result,SH.value)
          if cid=='TRF-010-F01' and members==expected and value in fixture.objects(focus,N.iceClass) and value not in expected:meaning='INTENDED_UNLISTED_VALUE'
        meanings.append(dict(meaning=meaning,focus=str(focus),path=str(path),component=str(component),parameters=parameters,evidence_basis='Source-backed SHACL constraint semantics, required owner/path, actual value/missing assignment and intended-only repaired report; not message text or blank-node spelling.'))
      resolved=bool(meanings) and all(m['meaning'].startswith('INTENDED_') for m in meanings)
      status=strict_status(verdict['conforms'],repaired_verdict['conforms'],resolved,False,certified=True,attribution_resolved=resolved)
      row.update(strict_status=status,repaired_source_oracle=repaired_oracle,repaired_verdict=repaired_verdict,violation_semantics=meanings,attribution_review='Post-generation constraint adjudication v1, independently checked against certified intent and full counterfactual result')
     rows.append(row);write(d/'result.json',row)
    selected=[r for r in rows if r['method']==method and r['candidate_version']==version];candidates.append(dict(method=method,candidate_version=version,candidate_sha256=digest(code),metrics=summarize(selected)))
  # Workflow credit uses production acceptance/original extraction, never offline scores.
  workflows=[]
  for method,folder in folders:
   run=load(folder/'run.json') if (folder/'run.json').is_file() else {}
   selected_version=run.get('accepted_version') if method!='Single-shot' else run.get('evaluation_candidate')
   selected=[r for r in rows if r['method']==method and r['candidate_version']==selected_version]
   if selected:metrics=summarize(selected)
   else:metrics=dict(positive_acceptance=0,positive_denominator=6,strict_intended_detection=0,negative_denominator=2,no_verdict=8,ordinary_agreement=0,ordinary_denominator=8,workflow_status='NO_ACCEPTED_EXECUTABLE_VERDICT; rejected candidates remain diagnostic only')
   workflows.append(dict(method=method,production_status=run.get('status','OPERATIONAL_FAILURE'),selected_version=selected_version,metrics=metrics,scope='Targeted diagnostic only, not fresh pipeline performance' if phase=='A' else 'Fresh paired pilot; first internal acceptance/original Single-shot output only'))
  result=dict(arm=phase,label='TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC' if phase=='A' else 'FRESH_PAIRED_DEVELOPMENT_PILOT',requirement_id='TRF-010',candidates=candidates,workflows=workflows,rows=rows,exclusions=[],positive_cases=6,negative_cases=2,elapsed_seconds=time.monotonic()-started,evaluation_after_arm_completion=True,evaluation_network_blocked=True,feedback_to_repair=False,shape_transformations=[])
  write(out/'independent_results.json',result)
 print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('arm',choices=['A','B']);evaluate(parser.parse_args().arm)
