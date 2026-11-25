import pathlib,json,hashlib,os,sys,socket,ssl,time,importlib.util,concurrent.futures,multiprocessing,collections,re,datetime
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');P=R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL';B=R/'outputs/experiments/20261124_V0101_FRESH_FIVE_REQUIREMENT_PAIRED_01';E=B/'evaluation'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def deny(*a,**k):raise RuntimeError('EXTERNAL_EVALUATION_OFFLINE_NETWORK_BLOCKED')
def initialize():
 global S,EV,SCOPES,CACHE
 socket.create_connection=deny;socket.socket.connect=deny
 from nltlv2.core import Project
 from nltlv2.schema import Schema
 from nltlv2.admission import validate_declaration
 S=Schema(Project(R));spec=importlib.util.spec_from_file_location('external_independent',R/'evaluation/independent.py');EV=importlib.util.module_from_spec(spec);spec.loader.exec_module(EV)
 manifest=load(P/'pilot_manifest.json');SCOPES={}
 for rid,path in manifest['scope_files'].items():
  admission=validate_declaration(load(R/path),S,rid);assert admission['valid'];SCOPES[rid]=admission['context']
 CACHE={}
def evaluate_task(task):
 from rdflib import Graph,RDF,URIRef
 from rdflib.namespace import SH
 from nltlv2.core import Candidate
 from nltlv2.admission import target_findings
 from nltlv2.evidence import literal_identity
 d=E/task['workflow']/task['requirement_id']/('candidate_'+str(task['version']).zfill(2))/task['case_id']/task['kind'];d.mkdir(parents=True,exist_ok=True)
 row={k:task[k] for k in ['workflow','requirement_id','version','candidate_sha256','selected','label','case_id','kind','input_file','input_sha256']}
 assert sha(R/task['input_file'])==task['input_sha256'] and sha(R/task['shape'])==task['candidate_sha256']
 key=task['shape']
 if key not in CACHE:
  try:
   code=(R/key).read_text()
   with literal_identity():shape=Graph().parse(R/key)
   findings=target_findings(Candidate(task['version'],code,code),SCOPES[task['requirement_id']]);CACHE[key]=(shape,findings,None)
  except Exception as ex:CACHE[key]=(None,[],dict(type=type(ex).__name__,diagnostic=str(ex)))
 shape,scope_findings,error=CACHE[key]
 if error:verdict=dict(conforms=None,status='CANDIDATE_PARSE_ERROR',error=error);report=None
 elif scope_findings:verdict=dict(conforms=None,status='UNRESOLVED_SHAPE_SCOPE',findings=[f.asdict() for f in scope_findings]);report=None
 else:
  with literal_identity():data=Graph().parse(R/task['input_file'])
  verdict,report=EV.validate_pair_graph(data,shape,S);verdict['admission_scope_verification']='Approved scope and exact hash-bound RDFS population proof reused from frozen offline readiness; shape target boundary checked for this candidate.'
  if report is not None:report.serialize(d/'report.ttl',format='turtle')
 row['verdict']=verdict
 # Same conservative query-body attribution as the existing external evaluator.
 meanings=[]
 if shape is not None and not scope_findings:
  refs,semantics=EV.reference_shape(task['requirement_id']);known={str(refs.value(q,SH.select)):semantics[str(s)] for s,q in refs.subject_objects(SH.sparql)}
  for v in verdict.get('violations',[]):
   source=URIRef(v['source_shape']);qs=list(shape.objects(source,SH.sparql));found=[known.get(str(shape.value(q,SH.select))) for q in qs];meanings.append(found[0] if len(found)==1 else None)
 row['reviewed_query_body_meanings']=meanings;row['attribution_basis']='Existing exact source-authored query-body matching only; unknown SHACL wrappers/property constraints are not automatically credited as strictly attributed.'
 write(d/'result.json',row);return row

def main():
 start=time.monotonic();socket.create_connection=deny;socket.socket.connect=deny
 assert (B/'dispatch_closed.json').exists(),'DISPATCH_NOT_CLOSED';closure=load(B/'dispatch_closed.json');assert closure['dispatch_closed'] is True and closure['outstanding_provider_processes']==0
 assert sha(B/'selected_outputs.json')==closure['selection_manifest_sha256'];assert sha(B/'candidate_inventory.json')==closure['all_candidate_inventory_sha256'];assert not E.exists();E.mkdir()
 for f,h in load(P/'frozen_resource_hashes.json').items():assert sha(R/f)==h,'FROZEN_RESOURCE_CHANGED '+f
 for f,h in load(P/'evaluation_resources.lock.json').items():assert sha(R/f)==h,'EVALUATION_RESOURCE_CHANGED '+f
 inventory=load(B/'candidate_inventory.json');selected=load(B/'selected_outputs.json');manifest=load(P/'pilot_manifest.json');cases=[c for c in load(R/'evaluation/selections/regression_core.json')['cases'] if c['requirement_id'] in manifest['requirements']];assert len(cases)==30
 for c in inventory:assert sha(R/c['shape'])==c['sha256']==closure['all_candidate_sha256'][c['shape']]
 from nltlv2.core import Project
 from nltlv2.admission import definition_hash
 from nltlv2.evidence import literal_identity
 from rdflib import Graph
 spec=importlib.util.spec_from_file_location('external_independent_main',R/'evaluation/independent.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev);ev.require_dispatch_closure(Project(R),str((B/'selected_outputs.json').relative_to(R)))
 inputs={};oracles=[]
 for c in cases:
  for kind in ['fixture','counterfactual']:
   if not c.get(kind):continue
   f=R/c[kind];binding=load(R/manifest['evaluation']['bindings'][c['case_id']][kind]);decl=load(R/manifest['scope_files'][c['requirement_id']]);assert binding['input_sha256']==sha(f) and binding['scope_definition_sha256']==definition_hash(decl) and decl['approval']['status']=='APPROVED'
   with literal_identity():g=Graph().parse(f)
   oracle=ev.oracle(g,c['requirement_id']);expected=(c['expected']=='PASS') if kind=='fixture' else True
   oracles.append(dict(case_id=c['case_id'],requirement_id=c['requirement_id'],kind=kind,input_sha256=sha(f),expected=expected,independent_oracle=oracle,agreement=oracle['conforms']==expected));inputs[(c['case_id'],kind)]=dict(file=c[kind],sha256=sha(f))
 write(E/'independent_input_oracle_checks.json',oracles)
 tasks=[]
 for cand in inventory:
  for case in cases:
   if case['requirement_id']!=cand['requirement_id']:continue
   for kind in ['fixture','counterfactual']:
    if not case.get(kind):continue
    inp=inputs[(case['case_id'],kind)];tasks.append(dict(workflow=cand['workflow'],requirement_id=cand['requirement_id'],version=cand['version'],candidate_sha256=cand['sha256'],shape=cand['shape'],selected=cand['selected'],label=cand['label'],case_id=case['case_id'],kind=kind,input_file=inp['file'],input_sha256=inp['sha256']))
 write(E/'evaluation_start.json',dict(dispatch_closed_sha256=sha(B/'dispatch_closed.json'),selected_manifest_sha256=sha(B/'selected_outputs.json'),tasks=len(tasks),candidates=len(inventory),original_cases=30,counterparts=16,parallel_workers=4,model_calls=0,admission_proof_reuse='Unchanged46 inputs/ontology/approved definitions, verified in final preparation; every candidate target checked anew.',attribution_policy='Existing conservative exact-query-body policy; unresolved attribution remains unresolved.'))
 rows=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn'),initializer=initialize) as executor:
  futures=[executor.submit(evaluate_task,t) for t in tasks]
  for future in concurrent.futures.as_completed(futures):
   rows.append(future.result())
   if len(rows)%10==0 or len(rows)==len(tasks):print('EVALUATED '+str(len(rows))+'/'+str(len(tasks)),flush=True);write(E/'evaluation_progress.json',dict(done=len(rows),total=len(tasks),elapsed_seconds=time.monotonic()-start))
 rows.sort(key=lambda x:(x['workflow'],x['requirement_id'],x['version'],x['case_id'],x['kind']));write(E/'all_candidate_verdicts.json',rows)
 by={(x['workflow'],x['requirement_id'],x['version'],x['case_id'],x['kind']):x for x in rows};per_candidate=[]
 for cand in inventory:
  cs=[c for c in cases if c['requirement_id']==cand['requirement_id']];results=[]
  for case in cs:
   orig=by[(cand['workflow'],cand['requirement_id'],cand['version'],case['case_id'],'fixture')];negative=orig['verdict']['conforms'];row=dict(case_id=case['case_id'],expected=case['expected'],conforms=negative,ordinary_agreement=None if negative is None else negative==(case['expected']=='PASS'))
   if case['counterfactual']:
    counterpart=by[(cand['workflow'],cand['requirement_id'],cand['version'],case['case_id'],'counterfactual')];repaired=counterpart['verdict']['conforms'];oracle=next(o for o in oracles if o['case_id']==case['case_id'] and o['kind']=='fixture')['independent_oracle'];meanings=orig['reviewed_query_body_meanings'];resolved=all(x is not None for x in meanings);strict=ev.strict_status(negative,repaired,bool(meanings),any(x not in oracle['issues'] for x in meanings if x is not None),certified=all(o['agreement'] for o in oracles if o['case_id']==case['case_id']),attribution_resolved=resolved)
    row.update(counterpart_conforms=repaired,paired_rejection_and_counterpart_acceptance=negative is False and repaired is True,strict_status=strict)
   results.append(row)
  summary=dict(requirement_id=cand['requirement_id'],workflow=cand['workflow'],version=cand['version'],sha256=cand['sha256'],selected=cand['selected'],label=cand['label'],candidate_status=cand['candidate_status'],run_terminal_reason=cand['run_terminal_reason'],ordinary_correct=sum(x['ordinary_agreement'] is True for x in results),original_cases=len(results),no_verdict=sum(x['conforms'] is None for x in results),positive_accepted=sum(x['expected']=='PASS' and x['conforms'] is True for x in results),negative_rejected=sum(x['expected']=='FAIL' and x['conforms'] is False for x in results),counterparts_accepted=sum(x.get('counterpart_conforms') is True for x in results),pair_observation_count=sum(x.get('paired_rejection_and_counterpart_acceptance') is True for x in results),strict_statuses=dict(collections.Counter(x['strict_status'] for x in results if 'strict_status' in x)),cases=results);per_candidate.append(summary)
 write(E/'candidate_diagnostics.json',per_candidate)
 selected_rows=[];selected_summaries={}
 for wf in ['Single-shot','NLTL']:
  for case in cases:
   entry=selected['workflows'][wf][case['requirement_id']];summ=next((x for x in per_candidate if x['workflow']==wf and x['requirement_id']==case['requirement_id'] and x['selected']),None)
   row=dict(workflow=wf,requirement_id=case['requirement_id'],case_id=case['case_id'],expected=case['expected'],selection_basis=entry['selection_basis'],terminal_reason=entry['terminal_reason'])
   row.update(next(x for x in summ['cases'] if x['case_id']==case['case_id']) if summ else dict(conforms=None,ordinary_agreement=None,strict_status='NO_VERDICT' if case['expected']=='FAIL' else None));selected_rows.append(row)
  rs=[x for x in selected_rows if x['workflow']==wf];selected_summaries[wf]=dict(original_cases=len(rs),ordinary_correct=sum(x['ordinary_agreement'] is True for x in rs),no_verdict=sum(x['conforms'] is None for x in rs),positive_accepted=sum(x['expected']=='PASS' and x['conforms'] is True for x in rs),positive_denominator=sum(x['expected']=='PASS' for x in rs),negative_rejected=sum(x['expected']=='FAIL' and x['conforms'] is False for x in rs),negative_denominator=sum(x['expected']=='FAIL' for x in rs),counterparts_accepted=sum(x.get('counterpart_conforms') is True for x in rs),counterpart_denominator=16,strict_statuses=dict(collections.Counter(x.get('strict_status') for x in rs if x['expected']=='FAIL')))
 write(E/'selected_output_results.json',dict(scope='Known development cases, not held out or proof of superiority',summaries=selected_summaries,rows=selected_rows,selected_by_internal_acceptance_before_evaluation=True,rejected_diagnostics_separate=True))
 write(E/'evaluation_complete.json',dict(status='COMPLETE',elapsed_seconds=time.monotonic()-start,tasks=len(tasks),model_calls=0,oracle_disagreements=[x for x in oracles if not x['agreement']],selected_summaries=selected_summaries))
 print('EVALUATION_COMPLETE '+json.dumps(dict(output=str(E),elapsed_seconds=time.monotonic()-start,selected_summaries=selected_summaries)),flush=True)
if __name__=='__main__':main()
