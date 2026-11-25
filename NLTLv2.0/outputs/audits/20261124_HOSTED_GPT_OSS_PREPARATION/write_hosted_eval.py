from pathlib import Path
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0')
(R/'evaluation/evaluate_hosted_shared_start.py').write_text('''"""Independent post-closure evaluation. Never imported by production dispatch."""
import argparse,json,pathlib,hashlib,time,collections,importlib.util,sys
from rdflib import Graph,URIRef
from rdflib.namespace import SH
from nltlv2.core import Project,load,write,offline_network_guard,Candidate
from nltlv2.schema import Schema
from nltlv2.admission import validate_declaration,validate_data_scope,target_findings
from nltlv2.evidence import literal_identity

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
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
  scopes=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/pilot_manifest.json')['evaluation']['bindings']
  cases=[c for c in load(R/'evaluation/selections/regression_core.json')['cases'] if c['requirement_id'] in m['requirements']]
  declarations={rid:validate_declaration(load(R/m['scope_files'][rid]),s,rid) for rid in m['requirements']}
  inputs={}
  for c in cases:
   for kind in ['fixture','counterfactual']:
    if not c.get(kind):continue
    with literal_identity():g=Graph().parse(R/c[kind])
    binding=load(R/scopes[c['case_id']][kind]);decl=declarations[c['requirement_id']]
    assert decl['valid'];admitted=validate_data_scope(g,s.graph,decl['context'],binding,sha(R/c[kind]));assert admitted['valid'],admitted
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
    verdicts={};meanings=[]
    for kind in ['fixture','counterfactual']:
     if not c.get(kind):continue
     verdict=dict(conforms=None,error=parse_error or 'UNRESOLVED_SHAPE_SCOPE') if shape is None or boundary else ev.validate_pair_graph(inputs[(c['case_id'],kind)][0],shape,s)[0]
     verdicts[kind]=verdict
     if kind=='fixture' and shape is not None:
      for v in verdict.get('violations',[]):
       qs=list(shape.objects(URIRef(v['source_shape']),SH.sparql));found=[known.get(str(shape.value(q,SH.select))) for q in qs];meanings.append(found[0] if len(found)==1 else None)
    neg=verdicts['fixture']['conforms'];row.update(verdicts=verdicts,conforms=neg,ordinary_agreement=None if neg is None else neg==(c['expected']=='PASS'))
    if c.get('counterfactual'):
     rep=verdicts['counterfactual']['conforms'];oracle=inputs[(c['case_id'],'fixture')][1];row.update(counterpart_conforms=rep,paired_observation=neg is False and rep is True,strict_status=ev.strict_status(neg,rep,bool(meanings),any(x not in oracle['issues'] for x in meanings if x is not None),attribution_resolved=all(x is not None for x in meanings)),attribution='Conservative unchanged exact-query matching; unmatched constraints remain unresolved, not credited')
    rows.append(row)
  write(E/'all_candidate_diagnostics.json',rows)
  selected_rows=[];summary={}
  for wf in ['Single-shot','NLTL']:
   for c in cases:
    entry=selected['workflows'][wf][c['requirement_id']]
    found=next((r for r in rows if r['workflow']==wf and r['case_id']==c['case_id'] and r['version']==entry.get('version')),None)
    row=dict(found) if found else dict(workflow=wf,requirement_id=c['requirement_id'],case_id=c['case_id'],expected=c['expected'],conforms=None,ordinary_agreement=None,strict_status='NO_VERDICT' if c['expected']=='FAIL' else None)
    row['delivery_status']=entry['status'];row['final_review']=entry.get('final_review');selected_rows.append(row)
   rs=[r for r in selected_rows if r['workflow']==wf];summary[wf]=dict(cases=len(rs),correct=sum(r['ordinary_agreement'] is True for r in rs),wrong=sum(r['ordinary_agreement'] is False for r in rs),no_verdict=sum(r['conforms'] is None for r in rs),delivered=sum(r['conforms'] is not None for r in rs),negative_denominator=sum(r['expected']=='FAIL' for r in rs),strict_statuses=dict(collections.Counter(r.get('strict_status') for r in rs if r['expected']=='FAIL')),counterpart_denominator=sum(bool(c.get('counterfactual')) for c in cases),counterparts_accepted=sum(r.get('counterpart_conforms') is True for r in rs),approval_by_requirement={rid:selected['workflows'][wf][rid] for rid in m['requirements']})
  changes=[]
  for rid in m['requirements']:
   initial={r['case_id']:r for r in rows if r['workflow']=='NLTL' and r['requirement_id']==rid and r['version']==1}
   for r in rows:
    if r['workflow']!='NLTL' or r['requirement_id']!=rid or r['version']==1:continue
    prev=initial[r['case_id']];changes.append(dict(requirement_id=rid,version=r['version'],case_id=r['case_id'],before=prev['conforms'],after=r['conforms'],change='RECOVERY' if prev['ordinary_agreement'] is False and r['ordinary_agreement'] is True else 'REGRESSION' if prev['ordinary_agreement'] is True and r['ordinary_agreement'] is False else 'UNCHANGED' if prev['conforms']==r['conforms'] else 'UNRESOLVED'))
  write(E/'selected_results.json',dict(summary=summary,rows=selected_rows));write(E/'recoveries_regressions.json',changes);write(E/'evaluation_complete.json',dict(status='COMPLETE',elapsed_seconds=time.monotonic()-start,model_calls=0,summary=summary,held_out=False,dispatch_closed_sha256=sha(B/'dispatch_closed.json')))
 print(json.dumps(dict(output=str(E),elapsed_seconds=time.monotonic()-start,summary=summary)),flush=True)
if __name__=='__main__':main()
''')
print('Independent post-closure evaluator prepared; no evaluation executed.')
