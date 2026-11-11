"""Source-only assessment of the fixed reviewed-requirement universe.

No generated SHACL, saved validation report, workflow verdict or performance
metric is read to decide case or requirement retention. No existing artifact is
changed. Authoring oracles are screening evidence, never automatic certification.
"""
import sys,json,hashlib,csv,copy,inspect,importlib.util
from pathlib import Path
from collections import Counter,defaultdict
from datetime import date
from decimal import Decimal
from rdflib import Graph,URIRef,Literal,RDF,RDFS,XSD,Namespace
ROOT=Path(__file__).resolve().parents[3];HERE=ROOT/'evaluation_audit';sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'full_audit'))
import audit
from evidence import load_script,oracle_for
import prepare
D=Path(__file__).resolve().parent;A=audit.read(D/'authority_snapshot.json') if (D/'authority_snapshot.json').exists() else audit.read(HERE/'authoritative_run.json');BASE=Path(A['run_dir']);RECON=Path(A['latest_ownership_reconciliation']);ROWS=audit.read(BASE/'retained_rows.json');RAW=audit.read(A['current_case_records']);INDEX=audit.read(audit.R13/'requirement_term_index.json');REG=prepare.REG;ONTO=prepare.ONTO;N,Q=audit.N,audit.Q;U=Namespace('http://qudt.org/vocab/unit/')
# Project out all workflow results before the decision code receives records.
RECS={cid:{k:v for k,v in r.items() if k!='workflows'} for cid,r in RAW.items()}
COMPLETE={'COMPLETED','COMPLETED_PRIOR50'}
SNAPSHOT=sorted(c for c,r in RECS.items() if r['state'] in COMPLETE)
REQS=sorted({RECS[c]['requirement_id'] for c in SNAPSHOT})
CORE={'I2-004','I2-005','I2-042','IMO-001','TRF-010','TRF-035'}
MANUAL=CORE|{'TRF-001','TRF-050','TRF-058'}
MANIFEST=prepare.MANIFEST
CORRECTIONS={r['case_id']:r for r in audit.read(RECON/'fixture_corrections.json')}

def read(p):return audit.read(p)
def sha(p):return audit.sha(p)
def save(name,x):audit.dump(D/name,x)
def csvout(name,x):audit.csvout(D/name,x)
def source_row(cid):return next(r for r in ROWS if r['condition']=='NO_SEMANTIC' and r['case_id']==cid)
def fixture(row):return Path(A['current_fixture_revision'])/row['rdf_path']
def export(g,path):path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(audit.triples(g))+'\n');return str(path)
def types(g,node):
 seen=set(g.objects(node,RDF.type))|set(ONTO.objects(node,RDF.type));todo=list(seen)
 while todo:
  t=todo.pop()
  for p in ONTO.objects(t,RDFS.subClassOf):
   if isinstance(p,URIRef) and p not in seen:seen.add(p);todo.append(p)
 return seen

def properties(req):
 return sorted(p for p in INDEX['requirements'][req] if REG.get(p,{}).get('kind') in ['QuantityProperty','DatatypeProperty','ObjectProperty'])

def schema_inventory(g,req):
 owners=INDEX['termOwners'].get(req,{});indexed=properties(req);contract=INDEX['dependencyContracts'][req]
 declared=set()
 for key in ['operandTerms','resultTerms','relationshipTerms','applicabilityTerms','evidenceTerms','timeTerms','comparisonTerms','directConstraintTerms']:
  declared.update(p for p in contract.get(key,[]) if isinstance(p,str) and p in indexed)
 present={str(p).removeprefix(str(N)) for s,p,o in g if str(p).startswith(str(N))}
 required=sorted(set(indexed)&(declared|present|set(owners)))
 missing=[p for p in required if not owners.get(p)]
 inactive_unbound=sorted(set(indexed)-set(required)-set(owners))
 # Only explicit termOwners govern placement. Domain is never an exclusive
 # owner constraint and fallback requiredOwner is never consulted.
 issues=[]
 for s,p,o in g:
  name=str(p).removeprefix(str(N))
  if not str(p).startswith(str(N)) or name not in required:continue
  t=REG[name];owner=owners.get(name)
  if owner and N[owner] not in types(g,s):issues.append(dict(code='EXPLICIT_OWNER_BINDING_REQUIRES_REVIEW',subject=str(s),property=name,expected_owner=owner,asserted_types=sorted(map(str,types(g,s)))))
  if t['kind']=='QuantityProperty':
   expected=t.get('unitIri');numbers=list(g.objects(o,Q.numericValue));units=list(g.objects(o,Q.unit))
   if len(numbers)!=1 or not isinstance(numbers[0],Literal) or numbers[0].datatype!=XSD.decimal:issues.append(dict(code='QUANTITY_NUMBER',property=name,subject=str(s),value=str(o)))
   if expected and units!=[URIRef(expected)]:issues.append(dict(code='CANONICAL_UNIT',property=name,subject=str(s),value=str(o),expected=expected,actual=list(map(str,units))))
  if t['kind']=='DatatypeProperty':
   dt={'xsd:boolean':XSD.boolean,'xsd:date':XSD.date,'xsd:string':XSD.string,'xsd:integer':XSD.integer,'xsd:decimal':XSD.decimal}.get(t.get('datatype'))
   if dt and (not isinstance(o,Literal) or (o.datatype or XSD.string)!=dt):issues.append(dict(code='CANONICAL_DATATYPE',property=name,subject=str(s),expected=str(dt),actual=o.n3()))
  if t['kind']=='ObjectProperty' and isinstance(o,Literal):issues.append(dict(code='OBJECT_LITERAL',property=name,subject=str(s),actual=o.n3()))
 return dict(required_properties=required,indexed_properties=indexed,declared_model_properties=sorted(declared),inactive_indexed_properties_with_unresolved_owner=inactive_unbound,explicit_owners={p:owners[p] for p in required if owners.get(p)},unresolved_binding_properties=missing,issues=issues,domain_is_not_exclusive_placement=True,scope='Declared model properties, represented indexed properties, and explicitly owned indexed properties. Unused legacy concepts remain unbound outside the represented model; no owner is invented.')

def legacy_view(g,cid):
 h=audit.clone(g)
 for m in CORRECTIONS.get(cid,{}).get('moves',[]):
  old=next(iter(audit.load_triples([' '.join(m['old'])+' .'])));new=next(iter(audit.load_triples([' '.join(m['new'])+' .'])))
  assert new in g
  if not m['canonical_existed']:h.remove(new)
  h.add(old)
 return h

def authoring_script(row):
 old=RECS.get(row['case_id'],{})
 if old.get('preparation_script'):return Path(old['preparation_script'])
 m=MANIFEST[row['case_id']];stem=Path(m['manifest_path']).name.removesuffix('_manifest.jsonl')
 return audit.BENCH/'scripts'/('validate_'+stem+'.py')

def counterfactual(row):
 old=RECS.get(row['case_id'],{})
 if old.get('repaired_fixture'):return old['repaired_fixture'],'EXISTING_VERSIONED_COUNTERFACTUAL'
 specfile=old.get('specification')
 if not specfile:return None,'NO_EXISTING_REVIEWED_REPAIR'
 spec=next((s for s in read(specfile) if s.get('case')==row['case_id']),None)
 if spec is None:return None,'SPECIFICATION_CASE_NOT_FOUND'
 g=Graph().parse(fixture(row))
 for t in audit.load_triples(spec['removed_triples']):
  if t not in g:return None,'EXISTING_REPAIR_PRECONDITION_MISMATCH'
  g.remove(t)
 for t in audit.load_triples(spec['added_triples']):g.add(t)
 return export(g,D/'counterfactual_copies'/row['case_id']/'repaired_fixture.ttl'),'COPY_OF_EXISTING_REVIEWED_OPERATION'

def source_issues(row):
 req=row['requirement_id'];notes=[]
 if req=='TRF-017':notes.append(dict(code='SOURCE_CONTRACT_OPERAND_GAP',detail='Full source includes additional propulsion power, but normalized requirement/comparison model and scoped vocabulary omit it; requirement-specific additional-power ownership is not explicit.'))
 if req=='I2-024':notes.append(dict(code='DECLARED_INPUT_SCOPE_UNRESOLVED',detail='Endpoint representation and listed longitudinal/transverse thickness operands require reconciliation; presence or absence cannot be judged from a generated shape.'))
 if req=='TRF-030':notes.append(dict(code='MULTIPLE_CASE_READINESS_SCOPE_REVIEW',detail='Explicit contract requires several directAnalysisCase nodes and coupled load-length/ca evidence; legacy oracle coverage of population and selectors is not a full certificate.'))
 if req=='TRF-130':notes.append(dict(code='WITHDRAWN_REPAIR_AND_MCR_BINDING_UNRESOLVED',detail='Latest reconciliation withdrew repair validity; missing MCR/aggregate relation is unresolved.'))
 return notes

def inventory():
 assert len(SNAPSHOT)==553 and len(REQS)==157
 current=[r for r in ROWS if r['condition']=='NO_SEMANTIC' and r['requirement_id'] in REQS]
 supplement=[r for r in ROWS if r['condition']=='NO_SEMANTIC' and r['requirement_id']=='TRF-130']
 assert len(current)==1290 and len(supplement)==12
 # Workflow-neutral identity/label equality; no outcome is inspected.
 for r in current+supplement:
  other=next(x for x in ROWS if x['condition']=='SINGLESHOT' and x['case_id']==r['case_id'])
  assert (r['requirement_id'],r['expected'],r['rdf_path'])==(other['requirement_id'],other['expected'],other['rdf_path'])
 save('authority_snapshot.json',A);save('snapshot_553_case_ids.json',SNAPSHOT);save('snapshot_requirement_ids.json',REQS)
 save('scope_reconciliation.json',dict(prose_claimed_requirements=158,actual_requirements=157,classified_negative_cases=553,actual_cases=len(current),actual_positive_cases=606,actual_negative_cases=684,source= str(RECON/'summary.json')+'#/strict_summary/after/requirements',historical_supplement_requirement='TRF-130',supplement_scope='NOT_IN_CURRENT_553; separately inventoried, never silently restored',supplement_positive_cases=2,supplement_negative_cases=10,with_supplement_cases=1302,with_supplement_positive_cases=608,with_supplement_negative_cases=694))
 protected=[HERE/'authoritative_run.json',Path(A['current_case_records']),Path(A['current_ordinary_results']),BASE/'retained_rows.json',RECON/'summary.json',RECON/'common_subset_case_ids.json',audit.ONTOLOGY,audit.R13/'requirement_term_index.json',audit.R13/'registry/term_registry.json']
 save('protected_inputs.json',{str(p):sha(p) for p in protected})
 out=[]
 for r in current+supplement:
  cid=r['case_id'];rec=RECS.get(cid,{});m=MANIFEST.get(cid,{});p=fixture(r)
  out.append(dict(case_id=cid,requirement_id=r['requirement_id'],scope='CURRENT_157' if r['requirement_id'] in REQS else 'HISTORICAL_SUPPLEMENT_TRF130',expected=r['expected'],source_clause=r['source_clause'],source_id=r['source_id'],source_text=r['frozen_requirement_text'],rationale=r['source_oracle_rationale'],fixture=str(p),fixture_sha256=sha(p),manifest=m.get('manifest_path'),historical_strict_snapshot_member=cid in SNAPSHOT,historical_case_state=rec.get('state','POSITIVE_NOT_AUDITED_IN_NEGATIVE_SNAPSHOT'),existing_blockers=rec.get('blockers',[]),existing_repair_validity=rec.get('independent_repaired_valid','NOT_RECORDED'),preparation_script=str(authoring_script(r)),workflow_outcomes_used=False))
 save('case_inventory.json',out);csvout('case_inventory.csv',out)
 print('Inventoried',len(current),'current cases +',len(supplement),'separate supplement cases',flush=True)


def screen():
 inv=read(D/'case_inventory.json');out=[]
 for i,c in enumerate(inv,1):
  cid=c['case_id'];r=source_row(cid);cached=D/'screens'/f'{cid}.json'
  if cached.exists():out.append(read(cached));continue
  g=Graph().parse(c['fixture']);record=copy.deepcopy(c);script=Path(c['preparation_script']);schema=schema_inventory(g,c['requirement_id']);proof,source_block=prepare.source_evidence(r)
  record.update(source_evidence=proof,source_evidence_blocker=source_block,schema=schema,source_scope_issues=source_issues(r),review_status='SCREENED_ONLY_NOT_CERTIFIED',screened_against_generated_shapes=False)
  try:
   if c['requirement_id']=='I2-048':
    result=audit.table_oracle(g,INDEX['dependencyContracts']['I2-048']);description='Existing source-transcribed Table-8 oracle on canonical owner graph'
   elif c['requirement_id'] in {'I2-001','IMO-001','TRF-001'}:
    result=audit.reviewed_fixture_oracle(g,c['requirement_id']);description='Previously source-reviewed independent pilot oracle'
   else:
    loaded=load_script(script);fn=oracle_for(loaded,c['requirement_id'])
    if fn is None:raise ValueError('No retained independent authoring oracle')
    result=bool(fn(legacy_view(g,cid)));description='Source-authored oracle with exact documented legacy-owner view only where correction ledger supplies substitutions'
   record['authoring_oracle']=dict(conforms=bool(result),expected_agreement=bool(result)==(c['expected']=='PASS'),description=description,script=str(script),script_sha256=sha(script),layout_adapter=cid in CORRECTIONS,scope_note='Screening only; legacy oracle acceptance never certifies source completeness or ownership.')
  except Exception as e:record['authoring_oracle']=dict(conforms=None,error=f'{type(e).__name__}: {e}',script=str(script),script_sha256=sha(script) if script.exists() else None)
  if c['expected']=='FAIL':
   rp,method=counterfactual(r);record['repair']=dict(path=rp,method=method,sha256=sha(rp) if rp else None,historical_validity=c['existing_repair_validity'])
  save('screens/'+cid+'.json',record);out.append(record)
  if i%100==0:print('Source/oracle checkpoint',i,'/',len(inv),flush=True)
 save('screened_cases.json',out)
 print('Source screens completed',len(out),'oracle agreements',Counter((c['expected'],c['authoring_oracle'].get('expected_agreement')) for c in out),flush=True)

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['inventory','screen'],required=True);a=p.parse_args()
 inventory() if a.phase=='inventory' else screen()
