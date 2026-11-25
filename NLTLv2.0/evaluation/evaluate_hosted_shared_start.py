"""Independent post-closure evaluation. Never imported by production dispatch."""
import argparse,json,pathlib,hashlib,time,collections,importlib.util,sys,types
from rdflib import Graph,URIRef
from rdflib.namespace import SH
from nltlv2.core import Project,load,write,offline_network_guard,Candidate
from nltlv2.schema import Schema
from nltlv2.admission import validate_declaration,validate_data_scope,target_findings,definition_hash
from nltlv2.evidence import literal_identity

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def execute_unchanged(data,shape,schema,evaluator,scope_findings=(),parse_error=None):
 """Same execution for both arms. Scope violations block admitted credit, not diagnostics."""
 if shape is None:behavior=dict(conforms=None,status='CANDIDATE_PARSE_ERROR',error=parse_error);report=None
 else:
  # pySHACL can add ontology axioms to an in-memory shapes graph despite inplace=False.
  # Execute disposable exact graph copies so cached source/input graphs remain identical.
  def clone(graph):
   out=Graph()
   for triple in graph:out.add(triple)
   for prefix,namespace in graph.namespaces():out.bind(prefix,namespace)
   return out
  behavior,report=evaluator.validate_pair_graph(clone(data),clone(shape),types.SimpleNamespace(graph=clone(schema.graph)))
 findings=[f.asdict() if hasattr(f,'asdict') else f for f in scope_findings]
 admitted=dict(conforms=None,status='UNRESOLVED_SHAPE_SCOPE',findings=findings) if findings else dict(behavior)
 return dict(behavior=behavior,admitted=admitted,scope_findings=findings,scope_qualified=shape is not None and not findings),report

def requirement_summary(rows,coverage_limits=()):
 correct=sum(r['ordinary_agreement'] is True for r in rows);wrong=sum(r['ordinary_agreement'] is False for r in rows);delivered=correct+wrong
 return dict(cases=len(rows),correct=correct,wrong=wrong,delivered=delivered,no_verdict=sum(r['conforms'] is None and r.get('execution_status')!='NOT_RUN' for r in rows),not_run=sum(r.get('execution_status')=='NOT_RUN' for r in rows),ordinary_accuracy=None if not rows else correct/len(rows),ordinary_accuracy_basis='Planned-case correct-delivery fraction; includes coverage denominator. NOT_RUN is separately reported, not an observed model error.',delivered_accuracy=None if not delivered else correct/delivered,coverage_limits=list(coverage_limits))

def main():
 p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--run-id',required=True);a=p.parse_args();project=Project(a.project);R=project.root;B=project.path('outputs/experiments/'+a.run_id);E=B/'evaluation';start=time.monotonic()
 receipt=load(B/'dispatch_closed.json')
 if receipt.get('dispatch_closed') is not True or receipt.get('outstanding_provider_processes')!=0:raise ValueError('DISPATCH_CLOSURE_REQUIRED')
 if sha(B/'selected_outputs.json')!=receipt['selection_manifest_sha256'] or sha(B/'candidate_inventory.json')!=receipt['all_candidate_inventory_sha256']:raise ValueError('DISPATCH_CLOSURE_INTEGRITY_FAILURE')
 if receipt.get('errors') and any('INTEGRITY' in e.get('diagnostic','') for e in receipt['errors']):raise ValueError('INTEGRITY_FAILURE_EVALUATION_BLOCKED')
 E.mkdir(exist_ok=False)
 with offline_network_guard():
  m=load(B/'manifest.frozen.json');selected=load(B/'selected_outputs.json');inventory=load(B/'candidate_inventory.json');s=Schema(project)
  lock=load(project.path(m['evaluation_lock']))
  for name,h in lock['files'].items():
   if sha(R/name)!=h:raise ValueError('EVALUATION_INPUT_INTEGRITY_FAILURE '+name)
  spec=importlib.util.spec_from_file_location('external_independent',R/'evaluation/independent.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
  # This manifest supplies unchanged input-construction bindings only; no old output is used.
  if m.get('evaluation_bindings'):
   external_bindings=load(project.path(m['evaluation_bindings']));scopes=external_bindings['bindings'];proofs=external_bindings['construction_proofs']
  else:
   scopes=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/pilot_manifest.json')['evaluation']['bindings']
   proofs=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/evaluation_binding_validation.json')['approved_scope_bindings']
  for name,h in load(B/'freeze_lock.json')['files'].items():assert sha(R/name)==h,'FROZEN_SOURCE_CHANGED '+name
  selection=load(project.path(m.get('evaluation_selection','evaluation/selections/regression_core.json')))
  cases=[c for c in selection['cases'] if c['requirement_id'] in m['requirements']]
  if set(c['requirement_id'] for c in cases)!=set(m['requirements']):raise ValueError('MISSING_FROZEN_EVALUATION_REQUIREMENT')
  declarations={rid:validate_declaration(load(R/m['scope_files'][rid]),s,rid) for rid in m['requirements']}
  inputs={}
  for c in cases:
   for kind in ['fixture','counterfactual']:
    if not c.get(kind):continue
    with literal_identity():g=Graph().parse(R/c[kind])
    binding=load(R/scopes[c['case_id']][kind]);decl=declarations[c['requirement_id']]
    assert decl['valid'];proof=next(p for p in proofs if p['file']==c[kind] and p['binding_file']==scopes[c['case_id']][kind])
    assert (proof.get('scope_definition_matches') and proof.get('complete_rdfs_population_proof')) if m.get('evaluation_bindings') else proof['approved_scope_matches'] and proof['prior_complete_rdfs_population_proof_reused']
    assert sha(R/c[kind])==binding['input_sha256']==proof['sha256']
    assert binding['scope_definition_sha256']==proof['scope_definition_sha256']==definition_hash(load(R/m['scope_files'][c['requirement_id']]))
    if m.get('evaluation_bindings'):
     boundary=validate_data_scope(g,s.graph,decl['context'],binding,sha(R/c[kind]));assert boundary['valid'],boundary
    oracle=ev.oracle(g,c['requirement_id']);expected=c['expected']=='PASS' if kind=='fixture' else True
    assert oracle['conforms']==expected,(c['case_id'],kind,oracle)
    inputs[(c['case_id'],kind)]=(g,oracle)
  rows=[]
  for item in inventory:
   f=R/item['shape'];assert sha(f)==item['sha256']==receipt['all_candidate_sha256'][item['shape']]
   try:
    with literal_identity():shape=Graph().parse(f)
    boundary=target_findings(Candidate(item['version'],f.read_text(),f.read_text()),declarations[item['requirement_id']]['context']);parse_error=None
   except Exception as e:shape=None;boundary=[];parse_error=type(e).__name__+': '+str(e)
   refs,semantics=ev.reference_shape(item['requirement_id']);known={str(refs.value(q,SH.select)):semantics[str(node)] for node,q in refs.subject_objects(SH.sparql)}
   for c in cases:
    if c['requirement_id']!=item['requirement_id']:continue
    row=dict(**item,case_id=c['case_id'],expected=c['expected'],candidate_label='DELIVERED' if item['selected'] else 'UNSELECTED_CANDIDATE_DIAGNOSTIC')
    verdicts={};admitted_verdicts={};meanings=[]
    for kind in ['fixture','counterfactual']:
     if not c.get(kind):continue
     execution,report=execute_unchanged(inputs[(c['case_id'],kind)][0],shape,s,ev,boundary,parse_error)
     verdict=execution['behavior'];verdicts[kind]=verdict;admitted_verdicts[kind]=execution['admitted']
     if report is not None:
      d=E/item['workflow']/item['requirement_id']/('candidate_'+str(item['version']).zfill(2))/c['case_id'];d.mkdir(parents=True,exist_ok=True);report.serialize(d/(kind+'_report.ttl'),format='turtle')
     if kind=='fixture' and shape is not None:
      for v in verdict.get('violations',[]):
       qs=list(shape.objects(URIRef(v['source_shape']),SH.sparql));found=[known.get(str(shape.value(q,SH.select))) for q in qs];meanings.append(found[0] if len(found)==1 else None)
    neg=verdicts['fixture']['conforms'];row.update(scope_findings=[f.asdict() for f in boundary],scope_qualified=shape is not None and not boundary,verdicts=verdicts,admitted_verdicts=admitted_verdicts,admitted_conforms=admitted_verdicts['fixture']['conforms'],conforms=neg,ordinary_agreement=None if neg is None else neg==(c['expected']=='PASS'))
    if c.get('counterfactual'):
     rep=verdicts['counterfactual']['conforms'];oracle=inputs[(c['case_id'],'fixture')][1];row.update(counterpart_conforms=rep,paired_observation=neg is False and rep is True,strict_status=ev.strict_status(neg,rep,bool(meanings),any(x not in oracle['issues'] for x in meanings if x is not None),attribution_resolved=all(x is not None for x in meanings)),attribution='Conservative unchanged exact-query matching; unmatched constraints remain unresolved, not credited')
    if c.get('counterfactual'):row['admitted_strict_status']='INADMISSIBLE_SCOPE' if boundary else row['strict_status']
    rows.append(row)
  write(E/'all_candidate_diagnostics.json',rows)
  selected_rows=[];summary={}
  for wf in ['Single-shot','NLTL']:
   for c in cases:
    entry=selected['workflows'][wf][c['requirement_id']]
    found=next((r for r in rows if r['workflow']==wf and r['case_id']==c['case_id'] and r['version']==entry.get('version')),None)
    row=dict(found) if found else dict(workflow=wf,requirement_id=c['requirement_id'],case_id=c['case_id'],expected=c['expected'],conforms=None,ordinary_agreement=None,strict_status='NO_VERDICT' if c['expected']=='FAIL' else None)
    row['delivery_status']=entry['status'];row['final_review']=entry.get('final_review');row['execution_status']='NOT_RUN' if entry['terminal_reason']=='NOT_RUN' else 'NO_VERDICT' if row['conforms'] is None else 'EVALUATED_UNCHANGED';selected_rows.append(row)
   rs=[r for r in selected_rows if r['workflow']==wf];summary[wf]=dict(cases=len(rs),correct=sum(r['ordinary_agreement'] is True for r in rs),wrong=sum(r['ordinary_agreement'] is False for r in rs),no_verdict=sum(r['conforms'] is None and r['execution_status']!='NOT_RUN' for r in rs),not_run=sum(r['execution_status']=='NOT_RUN' for r in rs),scope_violation_cases=sum(bool(r.get('scope_findings')) for r in rs),admitted_correct=sum(r.get('admitted_conforms') is not None and r['ordinary_agreement'] is True for r in rs),admitted_no_verdict=sum(r.get('admitted_conforms') is None and r['execution_status']!='NOT_RUN' for r in rs),admitted_strict_statuses=dict(collections.Counter(r.get('admitted_strict_status') for r in rs if r['expected']=='FAIL')),delivered=sum(r['conforms'] is not None for r in rs),negative_denominator=sum(r['expected']=='FAIL' for r in rs),strict_statuses=dict(collections.Counter(r.get('strict_status') for r in rs if r['expected']=='FAIL')),counterpart_denominator=sum(bool(c.get('counterfactual')) for c in cases),counterparts_accepted=sum(r.get('counterpart_conforms') is True for r in rs),approval_by_requirement={rid:selected['workflows'][wf][rid] for rid in m['requirements']})
  for wf in summary:
   summary[wf]['positive_denominator']=sum(c['expected']=='PASS' for c in cases)
   summary[wf]['positive_accepted']=sum(r['expected']=='PASS' and r['conforms'] is True for r in selected_rows if r['workflow']==wf)
   per={}
   for rid in m['requirements']:
    rs=[r for r in selected_rows if r['workflow']==wf and r['requirement_id']==rid];per[rid]=requirement_summary(rs,selection.get('coverage_limitations',{}).get(rid,[]))
   conditional=[p['delivered_accuracy'] for p in per.values() if p['delivered_accuracy'] is not None];summary[wf]['macro_delivered_accuracy']=sum(conditional)/len(conditional) if conditional else None
   summary[wf]['per_requirement']=per;accuracies=[p['ordinary_accuracy'] for p in per.values() if p['ordinary_accuracy'] is not None];summary[wf]['macro_requirement_agreement']=sum(accuracies)/len(accuracies) if accuracies else None
  changes=[]
  for rid in m['requirements']:
   initial={r['case_id']:r for r in rows if r['workflow']=='NLTL' and r['requirement_id']==rid and r['version']==1}
   for r in rows:
    if r['workflow']!='NLTL' or r['requirement_id']!=rid or r['version']==1:continue
    prev=initial[r['case_id']];changes.append(dict(requirement_id=rid,version=r['version'],case_id=r['case_id'],before=prev['conforms'],after=r['conforms'],scope_before=prev['scope_qualified'],scope_after=r['scope_qualified'],admitted_before=prev['admitted_conforms'],admitted_after=r['admitted_conforms'],change='RECOVERY' if prev['ordinary_agreement'] is False and r['ordinary_agreement'] is True else 'REGRESSION' if prev['ordinary_agreement'] is True and r['ordinary_agreement'] is False else 'UNCHANGED' if prev['conforms']==r['conforms'] else 'UNRESOLVED'))
  write(E/'selected_results.json',dict(summary=summary,rows=selected_rows));write(E/'recoveries_regressions.json',changes);write(E/'evaluation_complete.json',dict(status='COMPLETE',elapsed_seconds=time.monotonic()-start,model_calls=0,summary=summary,held_out=False,evaluation_policy='Identical unchanged-shape execution for both arms; raw behavior and scope-qualified credit reported separately; NOT_RUN is not a model failure',dispatch_closed_sha256=sha(B/'dispatch_closed.json')))
 print(json.dumps(dict(output=str(E),elapsed_seconds=time.monotonic()-start,summary=summary)),flush=True)
if __name__=='__main__':main()
