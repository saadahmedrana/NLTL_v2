"""Independent evaluation, only after live dispatch is irreversibly closed."""
from pathlib import Path
import json,hashlib,importlib.util,shutil,sys,time
sys.path.insert(0,str(Path(json.loads(Path('/private/tmp/v0101_authorized_continuation_state.json').read_text())['group'])/'runtime'))
from rdflib import Graph,RDF,URIRef
from rdflib.namespace import SH
from nltlv2.core import Project,load,write
from nltlv2.schema import Schema
from nltlv2.admission import validate_declaration,validate_data_scope,target_findings
from nltlv2.core import Candidate
STATE=Path('/private/tmp/v0101_authorized_continuation_state.json');ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');state=load(STATE);GROUP=Path(state['group']);assert state['status']=='DISPATCH_CLOSED' and (GROUP/'dispatch_closed.json').is_file(),'Dispatch must close before loading evaluation resources'
closure=load(GROUP/'dispatch_closed.json');assert closure['dispatch_closed'] and closure['model_transport_closed'];assert closure['run_manifest_sha256']==hashlib.sha256((GROUP/'I2-004/nltl/run.json').read_bytes()).hexdigest()
for name,h in closure['candidate_sha256'].items():assert hashlib.sha256((GROUP/'I2-004/nltl'/str(name+'.ttl')).read_bytes()).hexdigest()==h
OUT=GROUP/'evaluation';OUT.mkdir(exist_ok=False);shutil.copyfile(__file__,OUT/'independent_evaluation_driver.py')
evaluation_started=time.monotonic()
from nltlv2.core import offline_network_guard
network_guard=offline_network_guard();network_guard.__enter__()
spec=importlib.util.spec_from_file_location('independent_evaluation',ROOT/'evaluation/independent.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
selected=load(ROOT/'evaluation/selections/regression_core.json');cases=[c for c in selected['cases'] if c['requirement_id']=='I2-004'];assert len(cases)==6 and sum(bool(c.get('counterfactual')) for c in cases)==3
mapping=load(ROOT/'evaluation/selections/i2_004_research_scope_admission.proposed.json');scope=load(ROOT/'data/admissions/i2_004_research_scope.approved.json');schema=Schema(Project(ROOT));admission=validate_declaration(scope,schema,'I2-004');assert admission['valid'];write(OUT/'selected_cases.json',cases);write(OUT/'approved_scope.json',scope);shutil.copyfile(ROOT/'evaluation/provenance/v091/i2_004_scope_review.json',OUT/'construction_provenance.json');write(OUT/'evaluation_boundary.json',dict(dispatch_closed_first=True,dispatch_closed_sha256=hashlib.sha256((GROUP/'dispatch_closed.json').read_bytes()).hexdigest(),evaluation_inputs_never_sent_to_repair=True,same_reviewed_cases=True,labels_exclusions_and_original_fixtures_unchanged=True))
inputs={};input_summary=[]
for c in cases:
 for kind,key in [('fixture','fixture'),('counterfactual','counterfactual')]:
  if not c.get(key):continue
  source=ROOT/c[key];sha=hashlib.sha256(source.read_bytes()).hexdigest();binding=load(ROOT/mapping['admissions'][c['case_id']][kind]);assert binding['input_sha256']==sha
  dest=OUT/'inputs'/source.name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(source,dest);write(dest.with_suffix('.admission.json'),binding);data=Graph().parse(dest)
  print('ADMISSION '+c['case_id']+' '+kind,flush=True);start=time.monotonic();guard=validate_data_scope(data,schema.graph,admission['context'],binding,sha);assert guard['valid'],guard
  oracle=module.oracle(data,'I2-004');row=dict(case_id=c['case_id'],kind=kind,path=str(dest.relative_to(GROUP)),sha256=sha,scope=guard,independent_source_oracle=oracle,scope_guard_seconds=time.monotonic()-start);input_summary.append(row);write(OUT/'input_admission_results.json',input_summary);inputs[(c['case_id'],kind)]=(data,row)
run=load(GROUP/'I2-004/nltl/run.json');versions=sorted(int(p.stem.split('_')[-1]) for p in (GROUP/'I2-004/nltl').glob('candidate_*.ttl'));all_results=[]
for version in versions:
 path=GROUP/f'I2-004/nltl/candidate_{version:02d}.ttl';shape=Graph().parse(path);code=path.read_text();target=target_findings(Candidate(version,code,code),admission['context']);results=[];dest=OUT/f'candidate_{version:02d}';dest.mkdir();write(dest/'scope_target_findings.json',[f.asdict() for f in target]);print('EVALUATE_CANDIDATE '+str(version),flush=True)
 for c in cases:
  row=dict(case_id=c['case_id'],expected=c['expected'],requirement_id='I2-004',version=version,candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),diagnostic_only=version!=run['accepted_version'])
  for kind in ['fixture','counterfactual']:
   if (c['case_id'],kind) not in inputs:continue
   data,input_record=inputs[(c['case_id'],kind)];print('VALIDATE '+c['case_id']+' '+kind,flush=True)
   if target:verdict,report=dict(conforms=None,status='UNRESOLVED_SHAPE_SCOPE'),None
   else:verdict,report=module.validate_pair_graph(data,shape,schema)
   row[kind]=dict(verdict=verdict,input_sha256=input_record['sha256'],independent_source_oracle=input_record['independent_source_oracle'])
   if report is not None:report.serialize(dest/(c['case_id']+'.'+kind+'.report.ttl'),format='turtle')
  row['ordinary_agreement']=None if row['fixture']['verdict']['conforms'] is None else row['fixture']['verdict']['conforms']==(c['expected']=='PASS')
  row['strict']='PENDING_VIOLATION_MEANING_REVIEW' if c['expected']=='FAIL' and row['fixture']['verdict']['conforms'] is False and row['counterfactual']['verdict']['conforms'] is True else 'MISSED_INTENDED_DEFECT' if c['expected']=='FAIL' and row['fixture']['verdict']['conforms'] is True else 'NO_VERDICT' if c['expected']=='FAIL' and (row['fixture']['verdict']['conforms'] is None or row['counterfactual']['verdict']['conforms'] is None) else 'UNRELATED_OR_ADDITIONAL_FAILURE' if c['expected']=='FAIL' else None
  results.append(row);write(dest/'results_raw.json',results)
 all_results.extend(results)
write(OUT/'all_candidates_raw.json',all_results);write(OUT/'evaluation_complete.json',dict(status='RAW_EVALUATION_COMPLETE_AWAITING_MEANING_REVIEW',candidate_versions=versions,original_case_denominator=6,positive_denominator=3,negative_denominator=3,counterpart_denominator=3,accepted_version=run['accepted_version'],workflow_status='NO_VERDICT' if run['accepted_version'] is None else 'FIRST_INTERNAL_ACCEPTANCE_ONLY',all_inputs_admitted=True,model_calls=0));write(OUT/'evaluation_timing.json',dict(elapsed_seconds=time.monotonic()-evaluation_started,network='BLOCKED',provider_calls=0));print('RAW_EVALUATION_COMPLETE',flush=True)
