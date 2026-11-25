from pathlib import Path
import json,sys,hashlib,collections,importlib.util
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');M=R.parent/'MVP';A=R/'outputs/audits/20261125_TWENTY_REQUIREMENT_APPROVAL_PREPARATION';sys.path.insert(0,str(R/'src'))
from rdflib import Graph,RDF,URIRef,Literal
from nltlv2.schema import N,Q,Schema
from nltlv2.core import Project,offline_network_guard,write
from nltlv2.evidence import literal_identity
spec=importlib.util.spec_from_file_location('twenty_independent',R/'evaluation/independent.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();save=lambda n,x:write(A/n,x)
selected=['TRF-010','TRF-003','TRF-001','I2-005','TRF-035','TRF-018','TRF-032','TRF-128','I2-021','I2-066','I2-046','IMO-078','IMO-083','TRF-015','I2-019','I2-041','TRF-036','TRF-050','I2-004','I2-048']
old=load(M/'evaluation_audit/reduced_benchmark_assessments/20261111T091619777906Z/reviewed_cases.json');oldplans=load(M/'evaluation_audit/reduced_benchmark_assessments/20261111T091619777906Z/reviewed_branch_specifications.json');rows=[];selected_cases=[];schema=Schema(Project(R))
# Reuse pre-existing independently prepared counterparts absent from the reduced row metadata.
additional=[]
for c in old:
 if c['requirement_id'] in ['TRF-015','I2-046'] and c['expected']=='FAIL':
  existing=M/'evaluation_audit/outputs/20261108T124921Z/review_batches/all_negatives/cases'/c['case_id']/'repaired_fixture.ttl'
  if existing.exists():c['repair']=dict(path=str(existing),sha256=sha(existing));additional.append(dict(case_id=c['case_id'],original_counterpart=str(existing),sha256=sha(existing),selection='Existing independently authored original counterpart; revalidated against source here, no model scores read.'))
save('additional_pair_provenance.json',additional)
def readgraph(path):
 with literal_identity():return Graph().parse(path)
def roots(bad,good):
 changed=set(bad)^set(good);oldnodes=set(bad.all_nodes());out=set()
 for s,p,o in changed:
  if s not in oldnodes:continue
  if p in [Q.numericValue,Q.unit] or p==RDF.type:
   incoming={(owner,prop) for g in [bad,good] for owner,prop in g.subject_predicates(s) if str(prop).startswith(str(N))};out|=incoming or ({(s,p)} if p==RDF.type else set())
  elif str(p).startswith(str(N)):out.add((s,p))
  else:out.add((s,p))
 return sorted(out,key=lambda x:tuple(map(str,x)))
with offline_network_guard():
 for rid in selected:
  for case in [x for x in old if x['requirement_id']==rid]:
   row=dict(case_id=case['case_id'],requirement_id=rid,expected=case['expected'],original_fixture=case['fixture'],original_sha256=case['fixture_sha256'],reasons=[])
   path=Path(case['fixture']);assert sha(path)==case['fixture_sha256'];g=readgraph(path);source=case['source_evidence'];assert sha(Path(source['source_path']))==source['source_sha256']
   if case.get('source_evidence_blocker'):row['reasons'].append(case['source_evidence_blocker'])
   if case.get('source_scope_issues'):row['reasons'].extend(case['source_scope_issues'])
   unresolved=case.get('schema',{}).get('unresolved_binding_properties',[])
   if rid=='I2-046' and unresolved==['polarClass']:
    row['scope_dependency']='PROPOSED_EXTERNAL_POLAR_CLASS_POPULATION: no declared polarClass owner is invented. This eligibility fact must be explicitly approved externally; the uniform represented internal-structure obligation needs no class-valued selector. Legacy extra-selector/evidence negatives are excluded. Without approval this subset is not dispatch-ready.'
   elif unresolved:row['reasons'].append('UNRESOLVED_ACTIVE_SCHEMA_BINDING')
   oracle=ev.oracle(g,rid);row['independent_source_oracle']=oracle
   if oracle['conforms'] is None:row['reasons'].append('UNRESOLVED_SOURCE_ORACLE')
   elif oracle['conforms']!=(case['expected']=='PASS'):row['reasons'].append('SOURCE_EXPECTATION_DISAGREEMENT')
   if case['expected']=='FAIL':
    repair=case.get('repair',{});p=repair.get('path')
    if not p:row['reasons'].append('NO_EXISTING_INTENDED_ONLY_COUNTERPART')
    else:
     p=Path(p);assert sha(p)==repair['sha256'];good=readgraph(p);ro=ev.oracle(good,rid);rs=roots(g,good);properties={str(prop).removeprefix(str(N)) for owner,prop in rs};defects=set(oracle['issues']);row.update(counterpart=str(p),counterpart_sha256=sha(p),counterpart_oracle=ro,semantic_roots=[[str(x),str(y)] for x,y in rs]);
     if ro['conforms'] is not True:row['reasons'].append('COUNTERPART_NOT_SOURCE_CONFORMING')
     if len(properties)!=1 or not defects or not defects<=properties:row['reasons'].append('INTENDED_ONLY_CORRESPONDENCE_NOT_ESTABLISHED')
     # Preserve the previous strict coupled-value/unit restriction.
     coupled=[str(node) for node in set(g.all_nodes()) if list(g.objects(node,Q.numericValue)) and list(good.objects(node,Q.numericValue)) and any(s==node and pred==Q.numericValue for s,pred,o in set(g)^set(good)) and any(s==node and pred==Q.unit for s,pred,o in set(g)^set(good))]
     if coupled:row['reasons'].append('COUPLED_VALUE_AND_UNIT_CHANGE')
   row['usable']=not row['reasons'];rows.append(row)
   if row['usable']:selected_cases.append(dict(case,row_review=row))
  current=[x for x in rows if x['requirement_id']==rid];print(rid,'usable',sum(x['usable'] for x in current),'positive',sum(x['usable'] and x['expected']=='PASS' for x in current),'pairs',sum(x['usable'] and x['expected']=='FAIL' for x in current),'rejected',[(x['case_id'],x['reasons']) for x in current if not x['usable']],flush=True)
save('independent_original_case_review.json',rows);save('usable_original_cases.evaluation_only.json',dict(label='EVALUATION_ONLY_SOURCE_REVIEW_NO_WORKFLOW_PERFORMANCE',selection=selected,case_records=selected_cases));save('case_review_counts.json',[dict(requirement_id=rid,total=sum(x['requirement_id']==rid for x in rows),usable=sum(x['requirement_id']==rid and x['usable'] for x in rows),positive=sum(x['requirement_id']==rid and x['usable'] and x['expected']=='PASS' for x in rows),negative_counterpart_pairs=sum(x['requirement_id']==rid and x['usable'] and x['expected']=='FAIL' for x in rows)) for rid in selected])
print('CASE_REVIEW_COMPLETE model_calls=0 generated_shapes_consulted=0')
