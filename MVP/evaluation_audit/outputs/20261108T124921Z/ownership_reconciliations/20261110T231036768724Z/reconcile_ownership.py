#!/usr/bin/env python3
"""Versioned source/contract reconciliation; original shapes/fixtures stay frozen."""
import argparse,copy,csv,json,hashlib,shutil,sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
from datetime import datetime,timezone,date
from unittest.mock import patch
from rdflib import Graph,URIRef,Literal,RDF,RDFS,XSD
from rdflib.collection import Collection
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP')
sys.path.insert(0,str(ROOT/'evaluation_audit/full_audit'))
sys.path.insert(0,str(ROOT/'evaluation_audit'))
from common import audit,BASE,OUT as CURRENT,OLD,atomic
from evidence import load_script,oracle_for
from prepare import REG,ONTO,semantic_roots
import evaluate as reason_matcher
import semantic_review as semantic
DEST=Path(__file__).resolve().parent
OWN=BASE/'ownership_audits/20261110T224006505789Z'
INDEX=audit.read(audit.R13/'requirement_term_index.json')
ROWS=audit.read(BASE/'retained_rows.json');ROW={(r['condition'],r['case_id']):r for r in ROWS}
FIX_REQ={'TRF-014','TRF-030','TRF-036','TRF-130'}
N,Q,S=audit.N,audit.Q,audit.S

def read(p):return audit.read(p)
def save(p,data):atomic(DEST/p,data)
def sha(p):return audit.sha(p)
def triples(g):return audit.triples(g)
def clone(g):return audit.clone(g)
def graph(path):return Graph().parse(path)
def export(g,path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(triples(g))+'\n');return str(path)
def csvout(name,rows):audit.csvout(DEST/name,rows)
def local(p):return str(p).split('#')[-1]
def old_records():return {p.stem:read(p) for p in sorted((CURRENT/'records').glob('*.json'))}
def type_closure(g,n):
 result=set(g.objects(n,RDF.type))|set(ONTO.objects(n,RDF.type));pending=list(result)
 while pending:
  for parent in ONTO.objects(pending.pop(),RDFS.subClassOf):
   if isinstance(parent,URIRef) and parent not in result:result.add(parent);pending.append(parent)
 return result

def project(g,req):
 """Only explicit termOwners=ship is used. No unknown owner or value is filled.

 Quantity nodes, numeric lexical forms, units, labels and individuals are kept.
 Multiple canonical values are preserved; no new maxCount or deduplication.
 """
 h=clone(g);ships=list(g.subjects(RDF.type,N.ship));moves=[]
 if len(ships)!=1:return h,moves,['Expected exactly one explicitly represented ship']
 ship=ships[0];owners=INDEX['termOwners'][req]
 for s,p,o in list(g):
  if owners.get(local(p))=='ship' and str(p).startswith(str(N)) and s!=ship:
   original=(s,p,o);canonical=(ship,p,o);existed=canonical in g
   h.remove(original);h.add(canonical)
   moves.append(dict(old=[x.n3() for x in original],new=[x.n3() for x in canonical],canonical_existed=existed,property=str(p),old_owner=str(s),new_owner=str(ship),object=o.n3(),evidence=str(audit.R13/'requirement_term_index.json')+f'#/termOwners/{req}/{local(p)}'))
 return h,moves,[]

def legacy_logic_view(g,moves):
 """Read-only view for the retained source-authored oracle, not an evaluated fixture.

 The old oracle expects its old authoring node layout. Apply the exact inverse
 owner substitutions from the correction ledger only. Values and all other
 assertions remain untouched. This cannot certify ownership; owner_checks below
 separately enforces the agreed canonical contract on the actual graph.
 """
 h=clone(g)
 for m in moves:
  before=next(iter(audit.load_triples([' '.join(m['old'])+' .'])))
  after=next(iter(audit.load_triples([' '.join(m['new'])+' .'])))
  if after not in g:raise ValueError('Canonical owner precondition lost in oracle view')
  if not m['canonical_existed']:h.remove(after)
  h.add(before)
 return h

def owner_checks(g,req):
 issues=[];owners=INDEX['termOwners'][req];ships=list(g.subjects(RDF.type,N.ship))
 for s,p,o in g:
  if not str(p).startswith(str(N)):continue
  owner=owners.get(local(p))
  if owner:
   valid=(s in ships) if owner=='ship' else N[owner] in type_closure(g,s)
   if not valid:issues.append(dict(kind='EXPLICIT_CONTRACT_OWNER',subject=str(s),property=str(p),expected_owner=owner))
  term=REG.get(local(p),{})
  if term.get('kind')=='QuantityProperty':
   nums=list(g.objects(o,Q.numericValue));units=list(g.objects(o,Q.unit))
   if (o,RDF.type,Q.QuantityValue) not in g or len(nums)!=1 or not isinstance(nums[0],Literal) or nums[0].datatype!=XSD.decimal:issues.append(dict(kind='QUANTITY_REPRESENTATION',property=str(p),value=str(o)))
   if term.get('unitIri') and units!=[URIRef(term['unitIri'])]:issues.append(dict(kind='CANONICAL_UNIT',property=str(p),value=str(o),expected=term['unitIri'],actual=list(map(str,units))))
  if term.get('kind')=='DatatypeProperty':
   expected={'xsd:boolean':XSD.boolean,'xsd:decimal':XSD.decimal,'xsd:integer':XSD.integer,'xsd:string':XSD.string,'xsd:date':XSD.date}.get(term.get('datatype'))
   if expected and (not isinstance(o,Literal) or (o.datatype or XSD.string)!=expected):issues.append(dict(kind='CANONICAL_DATATYPE',property=str(p),value=o.n3(),expected=str(expected)))
 return issues

def source_oracle(record):return oracle_for(load_script(record['preparation_script']),record['requirement_id'])
def independent(g,moves,record):
 original_logic=source_oracle(record)
 value=bool(original_logic(legacy_logic_view(g,moves)))
 issues=owner_checks(g,record['requirement_id'])
 scope_gaps=[]
 if record['requirement_id']=='TRF-130' and not list(g.triples((None,N.maximumContinuousRatingPower,None))):scope_gaps=[dict(code='DECLARED_INPUT_COMPLETENESS_UNRESOLVED',property=str(N.maximumContinuousRatingPower),detail='The locked operandTerms lists this ship-owned input, but it is absent, the stored aggregate totalRelevantEnginePower includes auxiliary output, and no binding/value or cardinality rule establishes whether MCR is independently mandatory or redundant. The old logic oracle does not check it. Do not invent MCR=aggregate power or label its SHACL rejection unrelated before scope is reviewed.')]
 return dict(valid=None if scope_gaps else value and not issues,open_declared_input_scope=scope_gaps,retained_source_logic_on_documented_view=value,canonical_contract_issues=issues,domain_is_not_exclusive_placement=True,oracle_script=record['preparation_script'],oracle_script_sha256=sha(record['preparation_script']),owner_index_sha256=sha(audit.R13/'requirement_term_index.json'))

def prepare():
 if (DEST/'plan.json').exists():print('Preparation already checkpointed; using saved plan.');return
 before=old_records();assert sum(r['state'] in ['COMPLETED','COMPLETED_PRIOR50'] for r in before.values())==611
 save('records_before.json',before);save('authority_before.json',read(audit.HERE/'authoritative_run.json'))
 protected={str(p):sha(p) for p in BASE.rglob('*') if p.is_file() and not p.is_relative_to(DEST)};save('protected_before.json',protected)
 shutil.copytree(BASE/'corrected_benchmark',DEST/'benchmark',dirs_exist_ok=True)
 findings=read(OWN/'findings.json');confirmed=[r for r in findings if r['primary_finding']=='FIXTURE_VIOLATES_CLEAR_SCHEMA'];ids={r['case_id'] for r in confirmed};unknown={r['case_id'] for r in findings if r['primary_finding']=='SCHEMA_UNDERSPECIFIED'}
 assert len(ids)==29 and len(unknown)==52
 corrections=[];ordinary_jobs=[]
 for row in ROWS:
  if row['condition']!='NO_SEMANTIC' or row['requirement_id'] not in FIX_REQ:continue
  old=BASE/'corrected_benchmark'/row['rdf_path'];g=graph(old);h,moves,errors=project(g,row['requirement_id']);assert not errors,errors
  if set(g)==set(h):continue
  target=DEST/'benchmark'/row['rdf_path'];export(h,target)
  corrections.append(dict(case_id=row['case_id'],requirement_id=row['requirement_id'],expected=row['expected'],before=str(old),after=str(target),before_sha256=sha(old),after_sha256=sha(target),moves=moves,removed_triples=triples(set(g)-set(h)),added_triples=triples(set(h)-set(g))))
  for w in audit.WORKFLOWS:
   r=ROW[w,row['case_id']]
   if r['original_eligible']:ordinary_jobs.append(dict(key=f'ordinary/{w}/{row["case_id"]}',data=str(target),shape=r['shape_path'],shape_sha256=r['generated_shape_sha256'],condition=w,case_id=row['case_id'],kind='ordinary'))
 save('fixture_corrections.json',corrections);csvout('fixture_corrections.csv',corrections)
 plan=[]
 for cid in sorted(ids):
  rec=before[cid];req=rec['requirement_id'];related=[r for r in confirmed if r['case_id']==cid]
  if cid=='TRF-050-F05':
   plan.append(dict(case_id=cid,requirement_id=req,kind='INTENTIONAL_NEGATIVE_OWNERSHIP_MUTATION',unintended_original_fixture_defect=False,old_repair_invalid=False,ownership_flags=related,revalidate=False));continue
  bad=graph(rec['negative_fixture']);good=graph(rec['repaired_fixture']);b,bmoves,errors=project(bad,req);g,gmoves,gerrors=project(good,req);assert not errors+gerrors
  assert set(legacy_logic_view(b,bmoves))==set(bad) and set(legacy_logic_view(g,gmoves))==set(good),'Oracle adapter must round-trip the original authored graph exactly'
  folder=DEST/'pairs'/cid;folder.mkdir(parents=True,exist_ok=True)
  # The same projected negative is used by ordinary and strict evaluation.
  bench=DEST/'benchmark'/ROW['NO_SEMANTIC',cid]['rdf_path'];assert set(graph(bench))==set(b)
  bp=str(bench);gp=export(g,folder/'repaired_fixture.ttl')
  bcheck=independent(b,bmoves,rec);gcheck=independent(g,gmoves,rec)
  roots=semantic_roots(b,g);blockers=[]
  if bcheck['valid']:blockers.append(dict(code='CORRECTED_NEGATIVE_NO_LONGER_HAS_REVIEWED_DEFECT',detail='The canonical independent oracle accepts the negative; expected label is not changed.'))
  if not gcheck['valid']:blockers.append(dict(code='CORRECTED_REPAIR_NOT_INDEPENDENTLY_VALID',detail='Correcting the recorded owner does not establish all source/contract obligations.',oracle=gcheck))
  if len({p for s,p in roots})!=1:blockers.append(dict(code='INTENDED_ONLY_CANONICAL_REPAIR_NOT_ESTABLISHED',detail='After relocating shared ship-owned facts, the supplied counterfactual changes more than the intended semantic field. No values, cardinalities, aliases or applicability facts are invented to force a pass.',roots=[[str(s),str(p)] for s,p in roots]))
  if any(p==RDF.type and s in set(b.all_nodes()) and not list(g.objects(s,RDF.type)) for s,p,o in set(b)-set(g)):blockers.append(dict(code='COUNTERFACTUAL_REMOVES_EXISTING_POPULATION',detail='Counterfactual removes an existing owner population rather than supplying its intended missing field.'))
  entry=dict(case_id=cid,requirement_id=req,kind='FIXTURE_AND_COUNTERFACTUAL_REPRESENTATION_RECONCILIATION',ownership_flags=[{k:v for k,v in r.items() if k in ['workflow','case_id','disputed_property','adjudicated_fixture_arm']} for r in related],unintended_original_fixture_defect=bool(bmoves),old_repair_invalid=True,old_repair_path=rec['repaired_fixture'],old_repair_sha256=sha(rec['repaired_fixture']),old_repair_validity='WITHDRAWN_INVALID_EXPLICIT_OWNERSHIP',negative_fixture=bp,repaired_fixture=gp,negative_sha256=sha(bp),repaired_sha256=sha(gp),negative_corrections=bmoves,repair_corrections=gmoves,negative_oracle=bcheck,repaired_oracle=gcheck,removed_triples=triples(set(b)-set(g)),added_triples=triples(set(g)-set(b)),semantic_roots=[[str(s),str(p)] for s,p in roots],blockers=blockers)
  plan.append(entry);save('pair_reviews/'+cid+'.json',entry)
  if not blockers:
   for w in audit.WORKFLOWS:
    row=ROW[w,cid]
    if not row['original_eligible']:continue
    ordinary_key=f'ordinary/{w}/{cid}'
    if not any(job['key']==ordinary_key for job in ordinary_jobs):
     # Unchanged input: reuse the existing saved negative report.
     pass
    ordinary_jobs.append(dict(key=f'repaired/{w}/{cid}',data=gp,shape=row['shape_path'],shape_sha256=row['generated_shape_sha256'],condition=w,case_id=cid,kind='repaired'))
 save('plan.json',dict(entries=plan,underspecified_cases=sorted(unknown),known_population_counterfactuals=['IMO-072-F01','IMO-073-F02'],validation_jobs=ordinary_jobs,retained_cases=2160,source_owner_rules_unchanged=True))
 save('inputs.json',{str(p):sha(p) for p in [audit.ONTOLOGY,audit.R13/'requirement_term_index.json',BASE/'baseline_results.json',BASE/'retained_rows.json',OWN/'findings.json',BASE/'environment.json']})
 print('Prepared:',len(corrections),'changed ordinary fixtures;',len(ordinary_jobs),'eligible changed-input validation jobs;',Counter(e.get('kind') for e in plan));print('Pair blockers:',[(e['case_id'],[b['code'] for b in e.get('blockers',[])]) for e in plan if e.get('blockers')],flush=True)


def validate_job(job):
 folder=DEST/'validation'/job['key'];folder.mkdir(parents=True,exist_ok=True)
 fingerprint=dict(data=sha(job['data']),shape=sha(job['shape']),environment=read(BASE/'environment.json'));assert fingerprint['shape']==job['shape_sha256']
 cache=folder/'execution.json'
 if cache.exists() and read(cache)['fingerprint']==fingerprint:return dict(job,result=read(cache)['result'],reused=True)
 result=audit.validate(graph(job['data']),graph(job['shape']),folder,'report')
 atomic(cache,dict(fingerprint=fingerprint,result=result))
 return dict(job,result=result,reused=False)

def validate(workers):
 plan=read(DEST/'plan.json');jobs=plan['validation_jobs'];results=[]
 env=read(BASE/'environment.json');assert (audit.platform.python_version(),audit.rdflib.__version__,audit.pyshacl.__version__)==(env['python'],env['rdflib'],env['pyshacl']) and env['options']==audit.OPTIONS
 with ProcessPoolExecutor(max_workers=workers) as pool:
  fs={pool.submit(validate_job,j):j['key'] for j in jobs}
  for i,f in enumerate(as_completed(fs),1):
   r=f.result();results.append(r);save('validation_checkpoints/'+r['key'].replace('/','__')+'.json',r)
   if i%10==0 or i==len(jobs):print(f'Validation checkpoint {i}/{len(jobs)}',flush=True)
 save('executions.json',results)


def causal_trf050(rec):
 bad=graph(rec['negative_fixture']);good=graph(rec['repaired_fixture']);frame=next(bad.subjects(RDF.type,N.frame));record=next(bad.objects(frame,N.frameAttachment))
 assert INDEX['termOwners']['TRF-050']['frameShellWeldType']=='frameAttachmentRecord'
 assert set(bad)-set(good)=={(frame,N.frameShellWeldType,N.doubleContinuousWeld)}
 assert set(good)-set(bad)=={(record,N.frameShellWeldType,N.doubleContinuousWeld)}
 assert (N.frameShellWeldType,RDFS.domain,N.frameAttachmentRecord) in ONTO
 assert (frame,RDF.type,N.frameAttachmentRecord) not in bad
 assert not list(bad.subjects(N.frameAttachment,frame)) and (frame,N.frameAttachment,record) in good
 assert bad.value(record,N.shellPlateButtCrossing)==good.value(record,N.shellPlateButtCrossing)==Literal(False)
 assert bad.value(record,N.scallopingPresent)==good.value(record,N.scallopingPresent)==Literal(False)
 proofs={}
 for w,v in rec['workflows'].items():
  assert sha(ROW[w,rec['case_id']]['shape_path'])==ROW[w,rec['case_id']]['generated_shape_sha256']
  scopes=read(OWN/'groups/TRF-050__shellPlateButtCrossing.json')['workflows'][w]['generated_shape']
  assert scopes['sha256']==ROW[w,rec['case_id']]['generated_shape_sha256']
  assert scopes['occurrences'] and all(o['owner_class_hints']==[str(N.frameAttachmentRecord)] for o in scopes['occurrences'])
  sg=graph(ROW[w,rec['case_id']]['shape_path']);details=reason_matcher.violations(graph(v['negative']['report_path']),sg)
  assert v['original_eligible'] and v['negative']['conforms'] is False and v['repaired']['conforms'] is True
  assert set(graph(v['negative']['report_path']).objects(None,S.conforms))=={Literal(False)} and set(graph(v['repaired']['report_path']).objects(None,S.conforms))=={Literal(True)}
  source_shapes=set()
  for d in details:
   focus=d['focus'];component=d['component'];path=d['path']
   if focus==str(record) and path==str(N.frameShellWeldType) and component in ['MinCountConstraintComponent','HasValueConstraintComponent']:
    assert reason_matcher.parameter(d,S.minCount)==Literal(1) if component=='MinCountConstraintComponent' else reason_matcher.parameter(d,S.hasValue)==N.doubleContinuousWeld
    continue
   assert focus==str(frame),'Unexpected independent focus'
   if path==str(N.shellPlateButtCrossing) and component=='MinCountConstraintComponent':
    assert reason_matcher.parameter(d,S.minCount)==Literal(1)
    continue
   if component=='SPARQLConstraintComponent':assert d['query_sha256']=='afe5916e144601efcb9f21c35390b0c94ce1d043a27277d96bc7b3355054a007';continue
   assert component=='OrConstraintComponent','Unreviewed consequent constraint'
   source=URIRef(d['source_shape']);assert (source,S.targetClass,N.frameAttachmentRecord) in sg
   # Branch property requirements must be the legitimate source-backed record
   # selector/exception fields. Merely being caused by the mutation is not enough.
   closure=set();pending=[source]
   while pending:
    node=pending.pop()
    if node in closure:continue
    closure.add(node)
    for p,o in sg.predicate_objects(node):
     if p in [S.property,S.node]:pending.append(o)
     if p==S['or']:pending.extend(Collection(sg,o))
   allowed={N.frameShellWeldType,N.shellPlateButtCrossing,N.scallopingPresent}
   assert {p for n in closure for p in sg.objects(n,S.path)}<=allowed
   for node in closure:
    field=sg.value(node,S.path)
    if field is None:continue
    for count in [S.minCount,S.maxCount]:assert all(int(value)==1 for value in sg.objects(node,count))
    if field in [N.shellPlateButtCrossing,N.scallopingPresent]:
     assert all(dt==XSD.boolean for dt in sg.objects(node,S.datatype))
     assert set(sg.objects(node,S.hasValue))<=({Literal(True),Literal(False)} if field==N.shellPlateButtCrossing else {Literal(False)})
    elif field==N.frameShellWeldType:assert set(sg.objects(node,S.hasValue))<={N.doubleContinuousWeld}
  proofs[w]=dict(status='STRICT_INTENDED_MATCH',legitimate_source_constraints_only=True,direct_intended_failure='Required weld value absent on the linked attachment record.',causal_chain=[['frame','frameShellWeldType','doubleContinuousWeld'],['frameShellWeldType','rdfs:domain','frameAttachmentRecord'],['frame','rdf:type inferred','frameAttachmentRecord'],['record-targeted obligations','apply to the extra inferred record','missing selector / exception / inverse-link failures']],why_not_unrelated='These are legitimate obligations for the source-backed attachment-record role, instantiated on an extra inferred record solely by the intended wrong-owner mutation. There is no extra fixture defect or invented record obligation. Restoring only the weld owner removes that extra role and satisfies the real record.',all_reported_violations=details,negative_report=v['negative']['report_path'],repaired_report=v['repaired']['report_path'],reports_reused=True)
 return proofs


def revision_record_unresolved(rec,reason,entry=None):
 r=copy.deepcopy(rec);r['historical_state']=rec['state'];r['state']='BLOCKED';r['independent_negative_valid']=None;r['independent_repaired_valid']=None;r['repair_validity']='WITHDRAWN_OR_UNESTABLISHED';r['reconciliation_revision']=str(DEST)
 r['blockers']=[dict(code=reason,detail='Strict intended-only validity is not established under the unchanged explicit contract. No labels, exclusions, ownership assignments or shapes are changed.',evidence=str(DEST/'pair_reviews'/f'{r["case_id"]}.json') if entry else str(OWN/'findings.json'))]
 for w,v in r.get('workflows',{}).items():
  if not v['original_eligible']:assert v['status']=='NO_VERDICT';continue
  v['previous_strict_status']=v['status'];v['status']='UNRESOLVED_REASON';v['blocker']=r['blockers'][0];v['likely_cause']=dict(primary='FIXTURE_OR_ORACLE_DEFECT' if entry else 'UNRESOLVED',detail=reason)
 if entry:r['old_repair_validity']='WITHDRAWN_INVALID_EXPLICIT_OWNERSHIP';r['invalid_repair_path']=entry['old_repair_path'];r['canonical_candidate_review']=str(DEST/'pair_reviews'/f'{r["case_id"]}.json')
 return r


def review():
 before=read(DEST/'records_before.json');after=copy.deepcopy(before);plan=read(DEST/'plan.json');executions=read(DEST/'executions.json');ex={r['key']:r['result'] for r in executions};base={(r['condition'],r['case_id']):r for r in read(BASE/'baseline_results.json')};decisions=[]
 semantic.GUARDS['TRF-030']=['loadLengthDeterminedFromArrangement'] # scoped source-backed guard; no contract mutation
 for cid in plan['underspecified_cases']:after[cid]=revision_record_unresolved(before[cid],'OWNERSHIP_CONTRACT_UNDERSPECIFIED')
 for cid in plan['known_population_counterfactuals']:
  after[cid]=revision_record_unresolved(before[cid],'SUPPLIED_REPAIR_REMOVES_AFFECTED_POPULATION');after[cid]['repair_validity']='WITHDRAWN_NOT_INTENDED_ONLY';after[cid]['independent_repaired_valid']=False
 for entry in plan['entries']:
  cid=entry['case_id'];r=copy.deepcopy(before[cid])
  if cid=='TRF-050-F05':
   proof=causal_trf050(r);save('TRF-050-F05_causal_review.json',proof)
   for w,v in r['workflows'].items():
    v['previous_strict_status']=v['status'];v['status']='STRICT_INTENDED_MATCH';v['reason_evidence']=str(DEST/'TRF-050-F05_causal_review.json');v['likely_cause']=dict(primary='NONE_IDENTIFIED',detail='Legitimate RDFS-target consequences demonstrate the intended wrong-owner mutation.')
    v['historical_violation_reason_review']=v['violation_reason_review'];v['violation_reason_review']=dict(intended=proof[w]['all_reported_violations'],unrelated=[],unresolved=[],causal_proof=proof[w])
   r['independent_repaired_valid']=True;r['repair_validity']='VERIFIED_INTENDED_ONLY_ROLE_REPAIR';r['reconciliation_revision']=str(DEST);after[cid]=r;continue
  # Re-run only the independent oracle analysis (not validation) when a
  # previously omitted declared input exposes a gap in the old oracle's scope.
  if entry['requirement_id']=='TRF-130':
   entry['negative_oracle']=independent(graph(entry['negative_fixture']),entry['negative_corrections'],before[cid])
   entry['repaired_oracle']=independent(graph(entry['repaired_fixture']),entry['repair_corrections'],before[cid])
   gaps=entry['repaired_oracle']['open_declared_input_scope']
   entry['blockers']=[b for b in entry['blockers'] if b['code']!='DECLARED_INPUT_COMPLETENESS_UNRESOLVED']+gaps
   entry['candidate_repair_validity']='UNRESOLVED_DECLARED_INPUT_COMPLETENESS'
   save('pair_reviews/'+cid+'.json',entry)
  if entry['blockers']:
   after[cid]=revision_record_unresolved(r,'CANONICAL_REPAIR_REMAINS_UNRESOLVED',entry);continue
  r['repair_history']=dict(withdrawn_path=entry['old_repair_path'],withdrawn_sha256=entry['old_repair_sha256'],reason=entry['old_repair_validity'])
  r.update(negative_fixture=entry['negative_fixture'],repaired_fixture=entry['repaired_fixture'],negative_fixture_sha256=entry['negative_sha256'],repaired_fixture_sha256=entry['repaired_sha256'],independent_negative_valid=False,independent_repaired_valid=True,repair_validity='VERIFIED_CANONICAL_CONTRACT_AND_INTENDED_ONLY',reconciliation_revision=str(DEST),state='COMPLETED',blockers=[])
  r['selected_repair']=dict(method='CANONICAL_OWNER_PROJECTION_THEN_FROZEN_INTENDED_REPAIR',removed_triples=entry['removed_triples'],added_triples=entry['added_triples'],semantic_roots=entry['semantic_roots'],independent_oracle=entry['repaired_oracle'],repaired_schema_issues=[],legacy_oracle_requires_documented_owner_view=True)
  for w,old in before[cid]['workflows'].items():
   v=copy.deepcopy(old)
   if not v['original_eligible']:assert v['status']=='NO_VERDICT';r['workflows'][w]=v;continue
   shape=graph(ROW[w,cid]['shape_path']);key=f'ordinary/{w}/{cid}'
   neg=ex.get(key) or dict(conforms=base[w,cid]['corrected_conforms'],report_path=base[w,cid]['corrected_report'],reused_unchanged_input=True)
   good=ex[f'repaired/{w}/{cid}'];negative=dict(neg,violations=reason_matcher.violations(graph(neg['report_path']),shape));repaired=dict(good,violations=reason_matcher.violations(graph(good['report_path']),shape))
   v.update(previous_strict_status=old['status'],negative=negative,repaired=repaired,negative_fixture=entry['negative_fixture'],repaired_fixture=entry['repaired_fixture'],canonical_source_oracle=entry['repaired_oracle'],reconciliation_revision=str(DEST));v.pop('blocker',None)
   if negative['conforms'] is True:status='MISSED_INTENDED_DEFECT';meaning={}
   elif repaired['conforms'] is False:status='MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE';meaning=dict(reason='The corrected, independently source/contract-valid intended-only counterfactual still fails the complete unchanged shape.')
   else:
    oracle=lambda g:bool(independent(g,entry['repair_corrections'],before[cid])['valid'])
    with patch.object(reason_matcher,'oracle_callable',return_value=oracle):meaning=reason_matcher.match_reason(dict(r,_workflow=w),graph(entry['negative_fixture']),graph(entry['repaired_fixture']),shape,negative['violations'])
    residual=[]
    for d in meaning['unresolved']:
     p=None
     if d['component'] in ['OrConstraintComponent','XoneConstraintComponent']:
      rg=graph(neg['report_path']);src=URIRef(d['source_shape']);sg=rg if list(rg.predicate_objects(src)) else shape
      p=semantic.wrapper_proof(r,d,sg,graph(entry['negative_fixture']),graph(entry['repaired_fixture']))
     elif d['component']=='SPARQLConstraintComponent' and cid=='TRF-014-F05' and w=='NO_SEMANTIC':
      bg=graph(entry['negative_fixture']);gg=graph(entry['repaired_fixture']);ship=next(bg.subjects(RDF.type,N.ship));cert=bg.value(ship,N.hasClassCertificate)
      def number_at(dataset,owner,prop):
       qs=list(dataset.objects(owner,prop));assert len(qs)==1
       ns=list(dataset.objects(qs[0],Q.numericValue));assert len(ns)==1
       return ns[0].toPython()
      dates_ok=bg.value(ship,N.constructionDate).toPython()>=date(2007,7,1)
      applicable=dates_ok and number_at(bg,ship,N.summerLoadLineFreshWaterDraught)>number_at(bg,ship,N.upperIceWaterlineDraught)
      flags_ok=all(bg.value(ship,p)==gg.value(ship,p)==Literal(True) for p in [N.warningTrianglePresent,N.iceClassDraughtMarkPresent])
      before_mark=number_at(bg,ship,N.iceClassDraughtMarkDraughtAmidships);after_mark=number_at(gg,ship,N.iceClassDraughtMarkDraughtAmidships);maximum=number_at(bg,cert,N.maximumIceClassDraughtAmidships)
      p=dict(resolved=applicable and flags_ok and before_mark!=maximum and after_mark==maximum and d['query_sha256']=='36b862384e9c9d7a00ee1b083ec52fe7ee498b0c2e6fd69b9947a2cffc25bd9b',meaning='Exact reviewed query: post-2007 ship, summer draught 7>UIWL 6, both marking flags true. Only marked draught 5.5 differs from certificate maximum 6; restoring 6 satisfies the applicable positive branch. Pre-cutoff branches are inapplicable.',query=d['query'],witness=dict(mark_before=str(before_mark),mark_after=str(after_mark),certificate_maximum=str(maximum)))
     elif d['component']=='SPARQLConstraintComponent' and r['requirement_id']=='TRF-036':
      expected_queries={hashlib.sha256(str(q).encode()).hexdigest() for q in shape.objects(None,S.select)}
      p=dict(resolved=d['query_sha256']=='229c4743691391e68183eed59bf46d1398f913effae5eba65430e3c5b1ea70e2' and d['query_sha256'] in expected_queries and 'hasIceClassDesignParameterSet' in d['query'] and 'iceClass' in d['query'],meaning='Reviewed Table-4-1 query joins the parameter set to ship-owned iceClass and rejects the source table cell discrepancy. No owner or table rule is changed.',query=d['query'])
     if p and p['resolved']:meaning['intended'].append(d);meaning.setdefault('additional_proofs',[]).append(p)
     else:residual.append(d)
    meaning['unresolved']=residual
    status='MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE' if meaning['unrelated'] else 'UNRESOLVED_REASON' if residual or not meaning['intended'] else 'STRICT_INTENDED_MATCH'
   v['status']=status;v['violation_reason_review']=meaning
   if status=='UNRESOLVED_REASON':v['blocker']=dict(code='CANONICAL_PAIR_VIOLATION_SEMANTICS_UNRESOLVED',detail='No credit inferred from the corrected verdict transition alone.');r['blockers'].append(dict(workflow=w,**v['blocker']))
   v['likely_cause']=dict(primary='GENERATED_SHAPE_DEFECT' if status in ['MISSED_INTENDED_DEFECT','MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE'] else 'UNRESOLVED' if status=='UNRESOLVED_REASON' else 'NONE_IDENTIFIED',detail='Classification uses corrected fixtures and unchanged historical SHACL. Source ownership defects and old invalid repairs are not blamed on the generator.')
   r['workflows'][w]=v
  r['state']='BLOCKED' if r['blockers'] else 'COMPLETED';after[cid]=r
 save('plan_before_declared_input_scope_check.json',read(DEST/'plan.json')) if not (DEST/'plan_before_declared_input_scope_check.json').exists() else None
 save('plan.json',plan)
 save('records_after.json',after)
 for cid,r in after.items():
  if r!=before[cid]:save('records/'+cid+'.json',r)
 make_reports(before,after,plan,executions)


def make_reports(before,after,plan,executions):
 summaries=[];ids={}
 for version,data in [('before',before),('after',after)]:
  common=[r for r in data.values() if r['state'] in ['COMPLETED','COMPLETED_PRIOR50']];ids[version]=sorted(r['case_id'] for r in common)
  for w,label in audit.WORKFLOWS.items():
   counts=Counter(r['workflows'][w]['status'] for r in common)
   assert not counts['UNRESOLVED_REASON']
   for status in ['STRICT_INTENDED_MATCH','MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE','MISSED_INTENDED_DEFECT','NO_VERDICT']:summaries.append(dict(version=version,workflow=label,status=status,count=counts[status],denominator=len(common),percentage=100*counts[status]/len(common),requirements=len({r['requirement_id'] for r in common})))
 intersection=sorted(set(ids['before'])&set(ids['after']));intersection_rows=[]
 for version,data in [('before',before),('after',after)]:
  for w,label in audit.WORKFLOWS.items():
   counts=Counter(data[c]['workflows'][w]['status'] for c in intersection)
   for status in ['STRICT_INTENDED_MATCH','MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE','MISSED_INTENDED_DEFECT','NO_VERDICT']:intersection_rows.append(dict(version=version,workflow=label,status=status,count=counts[status],denominator=len(intersection)))
 ids['common_before_after_intersection']=intersection
 save('common_subset_case_ids.json',ids);csvout('strict_before_after.csv',summaries);csvout('strict_fixed_intersection_before_after.csv',intersection_rows)
 changes=[]
 for cid,r in after.items():
  if r==before[cid]:continue
  for w,v in r.get('workflows',{}).items():changes.append(dict(case_id=cid,requirement_id=r['requirement_id'],workflow=audit.WORKFLOWS[w],before=before[cid].get('workflows',{}).get(w,{}).get('status'),after=v['status'],case_state_before=before[cid]['state'],case_state_after=r['state'],repair_validity=r.get('repair_validity'),revision=str(DEST)))
 csvout('classification_changes.csv',changes)
 axes=[]
 for e in plan['entries']:
  axes.append(dict(case_id=e['case_id'],requirement_id=e['requirement_id'],intentional_negative_ownership_mutation=e['case_id']=='TRF-050-F05',unintended_original_fixture_defect=e.get('unintended_original_fixture_defect',False),invalid_supplied_repaired_counterfactual=e.get('old_repair_invalid',False),negative_defect_rationale=before[e['case_id']]['intended_rationale'],revised_state=after[e['case_id']]['state'],repair_validity=after[e['case_id']].get('repair_validity'),review=str(DEST/'pair_reviews'/f'{e["case_id"]}.json') if e['case_id']!='TRF-050-F05' else str(DEST/'TRF-050-F05_causal_review.json')))
 csvout('fixture_finding_reconciliation.csv',axes)
 # Ordinary verdict agreement: only benchmark inputs that actually changed are
 # rerun; no-verdicts, labels and identical exclusions are retained.
 ordinary=copy.deepcopy(read(BASE/'baseline_results.json'));ex={(x['condition'],x['case_id']):x for x in executions if x['kind']=='ordinary'}
 for row in ordinary:
  k=row['condition'],row['case_id']
  if k in ex:row['corrected_conforms']=ex[k]['result']['conforms'];row['corrected_report']=ex[k]['result']['report_path'];row['ownership_projection_revision']=str(DEST)
 save('ordinary_version_results.json',ordinary)
 ordinary_summaries={}
 for version,results in [('before',read(BASE/'baseline_results.json')),('after',ordinary)]:
  summary,fig,per_req=audit.metrics(ROWS,results,'corrected_conforms',True);ordinary_summaries[version]=summary
  csvout(f'ordinary_{version}_summary.csv',summary);csvout(f'ordinary_{version}_per_requirement.csv',per_req);csvout(f'ordinary_{version}_figure6.csv',fig)
 summary=dict(authoritative_baseline=str(BASE),strict_summary=summaries,common_subset_before=len(ids['before']),common_subset_after=len(ids['after']),states_after=dict(Counter(r['state'] for r in after.values())),fixture_finding_axes=dict(intentional_ownership_mutation=sum(r['intentional_negative_ownership_mutation'] for r in axes),unintended_original_fixture_defect=sum(r['unintended_original_fixture_defect'] for r in axes),invalid_repaired_counterfactual=sum(r['invalid_supplied_repaired_counterfactual'] for r in axes)),underspecified_cases_withdrawn=len(plan['underspecified_cases']),known_population_repair_claims_withdrawn=len(plan['known_population_counterfactuals']),corrected_benchmark_fixtures=len(read(DEST/'fixture_corrections.json')),corrected_positive_fixtures=sum(r['expected']=='PASS' for r in read(DEST/'fixture_corrections.json')),new_validation_jobs=len(executions),ordinary=ordinary_summaries,shapes_changed=False,contracts_strengthened=False,new_exclusions=0,new_generation_or_api_calls=0)
 summary['fixed_intersection_denominator']=len(intersection);summary['strict_fixed_intersection']=intersection_rows
 save('summary.json',summary)
 lines=['# Ownership / strict intended-failure reconciliation','', 'A versioned revision of the latest semantic audit. Original shapes, benchmark, reports, labels and exclusions remain frozen. Current classifications are the complete records_after.json snapshot identified by authoritative_run.json/current_case_records; the older all_negatives/records cache is superseded, not silently overwritten. The canonical fixture version changes only owners explicitly assigned by the locked contract. Broad domains and fallback requiredOwner are not ownership evidence.','',f"Confirmed fixture-side findings cover 29 unique cases. Axes overlap: {summary['fixture_finding_axes']}. The old independently-valid repair claim is withdrawn for every invalid supplied counterfactual, before any new strict judgment.",'', '## Strict results on common fully classified subsets','', '| Version | Workflow | Denominator | Strict | Unrelated/additional | Missed | No verdict |','|---|---|---:|---:|---:|---:|---:|']
 for version in ['before','after']:
  for label in audit.WORKFLOWS.values():
   rs=[r for r in summaries if r['version']==version and r['workflow']==label];lines.append('| '+version+' | '+label+' | '+str(rs[0]['denominator'])+' | '+' | '.join(str(r['count']) for r in rs)+' |')
 lines+=['',f"{len(plan['underspecified_cases'])} cases with underspecified ownership are unresolved for both workflows (original no-verdict remains NO_VERDICT). No owner mapping, cardinality or test label is strengthened to recover credit. The two previously noted lifeboat-removing counterfactuals also lose their intended-only validity claims.",'','## TRF-050-F05','', 'Both workflows now receive STRICT_INTENDED_MATCH. The wrong frame-owned weld assertion infers an extra frameAttachmentRecord target. Every reported violation is either the real record missing its required weld, or a legitimate source-backed record obligation applied to that extra inferred record. Restoring only the weld owner removes the extra role and makes the full unchanged shape pass. This is a reviewed causal correspondence, not a general rule that all mutation-caused violations are intended. Cached reports are reused; no unchanged pair is rerun.','', '## Fixture and oracle review','', 'The independent oracle has two separate gates: explicit canonical owner/type/unit checks on the actual graph, and the retained source-authored regulation logic through a documented inverse-placement view. That view round-trips the original authored graph exactly; it neither validates nor changes generated SHACL. Values, quantity nodes, labels and literal lexical forms are preserved. The original oracle alone is no longer advertised as certifying ownership.','', 'All TRF-130 candidate repairs remain unresolved: the contract lists maximumContinuousRatingPower but neither supplies its value nor settles its relationship to the stored aggregate power. The old oracle misses this input. No MCR value, mandatory cardinality or equivalence to aggregate power is invented. Two structural chest counterfactuals also change an extra shared-input assertion after canonicalization. Their already executed repaired validations are diagnostic only, never strict credit. If canonicalizing a structural counterfactual changes more than the intended semantic field, the new candidate remains unresolved. Pair candidates, oracle outcomes, exact correction/repair deltas and both reports are saved.','', '## Ordinary verdict agreement, separate from strict credit','']
 for label in audit.WORKFLOWS.values():
  b=next(r for r in ordinary_summaries['before'] if r['workflow']==label);a=next(r for r in ordinary_summaries['after'] if r['workflow']==label);lines.append(f"- {label}: {b['correct']}/{b['cases']} -> {a['correct']}/{a['cases']}; requirement mean {100*b['requirement_averaged_accuracy']:.4f}% -> {100*a['requirement_averaged_accuracy']:.4f}%.")
 lines+=['',f"Only changed benchmark inputs were revalidated, including {summary['corrected_positive_fixtures']} positive fixtures. The full unchanged baseline was not rerun. New Figure 6 files include expected-class denominators. This is ordinary verdict agreement on the owner-projected fixture version, not certification that every source expectation is fully adjudicated; the TRF-130 declared-input scope and underspecified owner cases remain unresolved for strict scoring. Valid unresolved tests stay in the ordinary denominator; no exclusions are added.",'', '## Artifacts','', '`fixture_finding_reconciliation.csv` separates intentional mutations, unintended original defects and invalid supplied repairs. `pair_reviews/` records withdrawal and candidate validity. `fixture_corrections.*` gives exact RDF changes and source/contract pointers. `records_before.json`, `records_after.json` and `classification_changes.csv` version the decisions; `validation/` saves only new changed-input executions. `strict_before_after.csv` and `common_subset_case_ids.json` expose matching denominators for both workflows. strict_fixed_intersection_before_after.csv additionally compares both versions on an identical case intersection, separating changed classifications from denominator changes. These are reviewed-subset strict results, not full-benchmark strict accuracy.']
 (DEST/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(summary,indent=2),flush=True)


def apply():
 before=read(DEST/'records_before.json');after=read(DEST/'records_after.json')
 for path,h in read(DEST/'protected_before.json').items():assert sha(path)==h,path
 for r in after.values():
  for w,v in r.get('workflows',{}).items():
   if not v['original_eligible']:assert v['status']=='NO_VERDICT'
   if v['status']=='STRICT_INTENDED_MATCH':assert v['negative']['conforms'] is False and v['repaired']['conforms'] is True and r.get('independent_repaired_valid',True) is True
 for cid in read(DEST/'plan.json')['underspecified_cases']:assert after[cid]['state']=='BLOCKED' and after[cid]['independent_repaired_valid'] is None
 changed=[c for c in before if before[c]!=after[c]]
 save('applied.json',dict(recorded_utc=datetime.now(timezone.utc).isoformat(),changed_records=changed,mode='IMMUTABLE_CURRENT_VERSION',current_case_records=str(DEST/'records_after.json'),superseded_cache=str(CURRENT/'records'),unchanged_prior_artifacts_preserved=True,old_repair_validity_withdrawn=True,exclusions_unchanged=True))
 authority=read(audit.HERE/'authoritative_run.json');authority['latest_report']=str(DEST/'SUMMARY.md');authority['latest_ownership_reconciliation']=str(DEST);authority['current_fixture_revision']=str(DEST/'benchmark');authority['current_case_records']=str(DEST/'records_after.json');authority['current_ordinary_results']=str(DEST/'ordinary_version_results.json');authority['superseded_case_cache']=str(CURRENT/'records');atomic(audit.HERE/'authoritative_run.json',authority)
 print('Published immutable current version:',DEST,'revised case classifications:',len(changed))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['prepare','validate','review','apply'],required=True);p.add_argument('--workers',type=int,default=4);a=p.parse_args()
 if a.phase=='prepare':prepare()
 elif a.phase=='validate':validate(a.workers)
 elif a.phase=='review':review()
 else:apply()
