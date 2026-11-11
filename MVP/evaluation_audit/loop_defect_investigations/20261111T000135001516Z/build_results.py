import json,pathlib,sys,collections,re,hashlib,csv
from rdflib import Graph,URIRef,Literal,RDF,XSD
ROOT=pathlib.Path.cwd();D=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'evaluation_audit'));import audit
sys.path.insert(0,str(ROOT/'evaluation_audit/full_audit'));import evaluate
A=audit.read(D/'authority_snapshot.json');R=audit.read(A['current_case_records']);ROWS=audit.read(pathlib.Path(A['run_dir'])/'retained_rows.json');ROW={(x['condition'],x['case_id']):x for x in ROWS};SH={(x['condition'],x['requirement_id']):x for x in audit.read(D/'shape_inventory.json')};S,N,Q=audit.S,audit.N,audit.Q
FS=audit.read(D/'static_findings.json')+audit.read(D/'kind_findings.json');TR={(x['condition'],x['requirement_id']):x for x in audit.read(D/'execution_trace_audit.json')};EX={x['key']:x for x in audit.read(D/'diagnostic_executions.json')};PLAN=audit.read(D/'diagnostic_plan.json')
def save(n,x):(D/n).write_text(json.dumps(x,indent=2,default=str)+'\n')
def csvout(n,x):audit.csvout(D/n,x)
def add(family,req,w,cases,mechanism,evidence,effect,primary='CONFIRMED_SHACL_DEFECT'):
 sh=SH[w,req];text=pathlib.Path(sh['path']).read_text();parts=text.splitlines();excerpt=[line.strip() for line in parts if any(t in line for t in evidence)];manual.append(dict(**sh,family=family,mechanism=mechanism,confirmed_affected_case_ids=cases,evidence_tokens=evidence,code_excerpt=excerpt,source_evidence=sh['source_text'],effect=effect,certainty=primary,source_ownership_not_inferred_from_domain=True))
manual=[]
add('SPARQL_BINDING_SCOPE','TRF-017','NO_SEMANTIC',['TRF-017-F02'],'UNION_FILTER_USES_OUTER_JOIN_BINDINGS',['FILTER (?restriction','FILTER (?maximumValue','UNION'],'DEFECTIVE_PASS')
add('OWNER_PATH','TRF-036','SINGLESHOT',['TRF-036-'+c for c in ['F01','F02','F03','F04','F06']],'ICE_CLASS_READ_DIRECTLY_ON_PARAMETER_SET',['sh:targetClass nltl:iceClassDesignParameterSet','sh:path nltl:iceClass'],'VALID_FAIL')
for req,w,cids,code in [('IMO-003','NO_SEMANTIC',['IMO-003-F02'],['FILTER NOT EXISTS','nltl:designIceCondition']),('IMO26-014','NO_SEMANTIC',['IMO26-014-A-F0'+str(i) for i in range(1,5)],['sh:or','sh:hasValue true','sh:hasValue false','sh:minInclusive 2']),('TRF-052','NO_SEMANTIC',['TRF-052-F01','TRF-052-F05'],['FILTER ( ! (?asym','antitrippingSupportSpacing']),('IMO-114','NO_SEMANTIC',['IMO-114-M-F01','IMO-114-M-F03'],['FILTER (STR(?tankType) != "3")']),('IMO-114','SINGLESHOT',['IMO-114-M-F01','IMO-114-M-F03'],['FILTER NOT EXISTS','administrationCarriageApprovalStatus','applicableCertificatePolarOperationEntryPresent']),('IMO-110','SINGLESHOT',['IMO-110-L-F01','IMO-110-L-F02'],['FILTER NOT EXISTS','entireCargoTankLengthDoubleBottomProtectionStatus','wingTankProtectionStatus']),('TRF-076','SINGLESHOT',['TRF-076-F01','TRF-076-F03','TRF-076-F04','TRF-076-F05'],['FILTER NOT EXISTS','propellerBladeLoadCaseNumber'])]:
 assert all(c in R for c in cids),(req,cids)
 add('BOOLEAN_APPLICABILITY',req,w,cids,'VALIDITY_USED_AS_FAILURE_OR_CONJUNCTION_OF_FAILURES',code,'DEFECTIVE_PASS')
add('COMPARISON_ARITHMETIC','I2-004','SINGLESHOT',['I2-004-G-F01','I2-004-G-F02','I2-004-G-F03'],'SELECT_VALID_MAXIMUM_AS_VIOLATION',['FILTER (?caseValue = ?duiValue)','FILTER NOT EXISTS','FILTER (?otherValue > ?duiValue)'],'BOTH')
for w in audit.WORKFLOWS:add('MISSING_OBLIGATION','TRF-062',w,['TRF-062-F01','TRF-062-F03'],'ONLY_PRESENCE_NO_CLEARANCE_GE_H0',['sh:path nltl:propellerBladeTipHullClearance'],'DEFECTIVE_PASS')
add('MISSING_OBLIGATION','IMO26-005','SINGLESHOT',['IMO26-005-A-F02'],'EXISTS_APPROVED_INSTEAD_OF_ALL_APPROVED',['sh:hasValue nltl:evidenceStateApproved'],'DEFECTIVE_PASS')
add('MISSING_OBLIGATION','TRF-001','SINGLESHOT',['TRF-001-F02'],'MISSING_APPLICABILITY_READINESS_DATE',['sh:path nltl:constructionContractDate','when supplied'],'DEFECTIVE_PASS','CONFIRMED_REPRESENTATION_READINESS_GAP_NOT_UNIVERSAL_SOURCE_DATE_OBLIGATION')
# Unconditional selector restrictions are established against explicit conditional
# comparison models, not from a positive label or an assumed property owner.
for req,w in [('TRF-018','NO_SEMANTIC'),('TRF-018','SINGLESHOT'),('IMO-110','NO_SEMANTIC'),('IMO-110','SINGLESHOT'),('IMO-037','SINGLESHOT'),('IMO-119','SINGLESHOT')]:
 cs=[]
 for row in ROWS:
  if row['condition']!=w or row['requirement_id']!=req or row['expected']!='PASS':continue
  g=Graph().parse(pathlib.Path(A['current_fixture_revision'])/row['rdf_path'])
  outside=(req=='TRF-018' and N.iceClassIi in set(g.objects(None,N.iceClass))) or (req!='TRF-018' and N.polarShipCategoryC in set(g.objects(None,N.shipCategory)))
  if outside:cs.append(row['case_id'])
 add('EXCESSIVE_SCOPE_CARDINALITY',req,w,cs,'CONDITIONAL_SELECTOR_VALUES_MADE_GLOBAL_CLOSED_LIST',['sh:targetClass nltl:ship','sh:path nltl:iceClass','sh:path nltl:shipCategory','nltl:polarShipCategoryA','nltl:polarShipCategoryB','nltl:iceClassIa'],'VALID_FAIL')
for f in manual:
 f['contract']=audit.read(f['context'])['selection']['dependencyContract'];f['representation_evidence']=str(ROOT/'BENCHMARK_VOCABULARY/FINAL_LOCK_R13/requirement_term_index.json')
 if f['family']=='OWNER_PATH':f['required_path']='parameterSet/^hasIceClassDesignParameterSet/iceClass';f['explicit_term_owner']='termOwners/TRF-036/iceClass=ship'
 if f['mechanism']=='ONLY_PRESENCE_NO_CLEARANCE_GE_H0':assert 'minimumClearance' not in pathlib.Path(f['path']).read_text()
 if f['mechanism']=='MISSING_APPLICABILITY_READINESS_DATE':f['scope_note']='Keep regulatory presence and representation readiness distinct; this count is not a source mandate for every conditional date.'
save('manual_confirmations.json',manual)
# Versioned separation of uncertainties and previously overturned blame.
nonshape=[dict(requirement_id='TRF-050',cases=['TRF-050-F05'],classification='INTENTIONAL_NEGATIVE_MUTATION_NOT_SHACL_DEFECT',evidence=A['latest_ownership_reconciliation']+'/TRF-050-F05_causal_review.json'),dict(requirement_id='TRF-017',cases=['TRF-017-F01'],classification='SOURCE_CONTEXT_CONTRADICTION_AND_MISSING_OPERAND_BINDING',detail='Full source includes additional power. Normalized requirement/dependency comparison omits it; original allowedVocabulary lacks additionalPropulsionPower although global registry contains it. termOwners supplies no TRF-017 owner for this additional operand. Do not infer its owner from broad benchmarkEntity domain. The source-informed diagnostic sum uses a provisional ship binding and is not a certified repair or confirmed generator-only arithmetic defect.'),dict(requirement_id='TRF-030',classification='COUNTERFACTUAL_POPULATION_SCOPE_REQUIRES_FURTHER_REVIEW',detail='The explicit context says several directAnalysisCase nodes. Single-shot minCount 2 is not by itself a confirmed excessive constraint. Canonical owner projection alone does not settle case population/coverage readiness.'),dict(requirement_id='I2-024',classification='DECLARED_INPUT_SCOPE_NOT_FULLY_ESTABLISHED',detail='Canonical contract lists longitudinal/transverse thickness operands as well as endpoint representation. Generic calculationCase targets are not ownership errors merely because subclasses are reached. Do not automatically blame missing declared inputs on excessive shape constraints.'),dict(requirement_id='TRF-130',classification='WITHDRAWN_REPAIR_VALIDITY_UNRESOLVED',detail='Latest reconciliation withdrew independent validity for all eight candidate repairs; omitted MCR/aggregate binding remains unsettled. No repaired-report rejection is counted as a confirmed shape defect.'),dict(classification='UNDERSPECIFIED_OWNERSHIP',cases=audit.read(pathlib.Path(A['latest_ownership_reconciliation'])/'plan.json')['underspecified_cases'],detail='52 cases remain unresolved; no fallback owner is treated as authoritative.'),dict(classification='GENERATION_NO_VERDICT',detail='22 NLTL_v2 and 47 Single-shot requirement outputs were historically ineligible; no offline diagnostic credit. Overall ordinary no-verdict counts remain 202/401.')]
save('non_shape_and_unresolved.json',nonshape)
# Diagnostic report semantics are explicitly reviewed, not credited from a
# reject/pass transition alone. All constraints/queries are preserved or have
# a source-backed manual transformation recorded in the ledger.
proofs=[];ds=[]
HASHES={'TRF-018':{'e808b846b2387e4918aa0a86734096b22d145ab55fbb6f559ca03f135e29174e'},'TRF-080':{'93eb0144ab41d9a0e0562d89d06b239b2dd2ca922bee28a40a01713909051075','532ff46d315d1fca3728a7ad56db9b41e87369a6809de71bbb09ebe6dbf881f1'},'TRF-076':{'6b6c42750f493d0972ad01d233315e4ddbb5941877542d2268e1c9ad32e643c4'},'I2-004':{'623478465ae6d844905aacda768db7f439938e406235ef3e83f2479ba4782dd9'}}
CORE={'TRF-080':{'MinCountConstraintComponent'},'IMO-031':{'InConstraintComponent','HasValueConstraintComponent','MinCountConstraintComponent'}}
for e in PLAN:
 if not e.get('case_id'):continue
 arm,w,cid=e['arm'],e['condition'],e['case_id'];req=e['requirement_id'];key=f'{arm}/{w}/{cid}/negative_or_positive';out=EX[key]['result'] if e['shape_changed'] else dict(conforms=e['baseline'],report_path=e['baseline_report']);new=out['conforms'];row=dict(arm=arm,condition=w,case_id=cid,requirement_id=req,expected=e['expected'],before_conforms=e['baseline'],after_conforms=new,before_agreement=e['baseline']==(e['expected']=='PASS'),after_agreement=new==(e['expected']=='PASS'),shape_changed=e['shape_changed'],diagnostic_report=out['report_path'])
 if e.get('repaired_fixture'):
  v=e['baseline_pair'];good=EX[f'{arm}/{w}/{cid}/repaired']['result'] if e['shape_changed'] else v['repaired'];status=v['status'];meaning=[]
  if arm=='scope_and_additional_power' and e['shape_changed']:status='UNRESOLVED_REASON';meaning=['PROVISIONAL_SOURCE_CONTEXT_BINDING_NO_STRICT_CREDIT']
  elif not e['shape_changed']:pass
  elif new is True:status='MISSED_INTENDED_DEFECT'
  elif good['conforms'] is False:status='MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE'
  else:
   vs=evaluate.violations(Graph().parse(out['report_path']),Graph().parse(e['shape']));assert vs
   for d in vs:
    component=d['component']
    if component=='SPARQLConstraintComponent':assert d['query_sha256'] in HASHES.get(req,set()) or arm=='scope_only',(cid,d['query_sha256'])
    elif req=='TRF-018':assert component in ['NodeConstraintComponent','HasValueConstraintComponent'] and cid.endswith('F05')
    elif req in CORE:assert component in CORE[req]
    elif arm=='violation_polarity':assert component in ['NodeConstraintComponent','HasValueConstraintComponent','MinCountConstraintComponent']
    elif arm in ['explicit_owner_path','paired_boolean_branch']:assert component in ['OrConstraintComponent','MinCountConstraintComponent']
    else:raise AssertionError((cid,d))
   status='STRICT_INTENDED_MATCH';meaning=[dict(case=cid,source_rationale=R[cid]['intended_rationale'],source_clause=R[cid]['source_clause'],binding='TRF-036: ship-owned selector reached by exact inverse approved relationship; Table 4-1 and intended missing selector/link/unit repair.' if arm=='explicit_owner_path' else 'IMO26-014: daylight=true OR (daylight=false AND count>=2), including required selector readiness.' if arm=='paired_boolean_branch' else 'I2-004: violation is NOT(valid represented maximum); Core handles missing and wrong-unit selected result.' if arm=='violation_polarity' else 'TRF-017-F02: restricted base 4200 vs reported 5000, no additional-power assertion; locally bound branch comparison.' if arm=='scope_only' else 'TRF-018: explicit class-specific required power/floor; TRF-080: cycle count times blade count; IMO-031: exact R13 approval strings/state/PST/material; TRF-076: cases 1-4 and reversing FP case 5. Only applicable constraint families listed in violations are admitted.',violations=vs,negative=out['report_path'],repaired=good['report_path'],counterfactual_same_as_authoritative_review=True)]
  row.update(before_strict=v['status'],after_strict=status,before_repaired_conforms=v['repaired']['conforms'],after_repaired_conforms=good['conforms'],repaired_report=good['report_path']);proofs.extend(meaning)
 ds.append(row)
for e in PLAN:
 if e.get('status')!='NO_VERDICT':continue
 for rr in ROWS:
  if rr['condition']!=e['condition'] or rr['requirement_id']!=e['requirement_id']:continue
  entry=dict(arm=e['arm'],condition=e['condition'],case_id=rr['case_id'],requirement_id=e['requirement_id'],expected=rr['expected'],before_conforms=None,after_conforms=None,before_agreement=False,after_agreement=False,shape_changed=False,diagnostic_report=None)
  if rr['case_id'] in R and R[rr['case_id']]['state'] in ['COMPLETED','COMPLETED_PRIOR50']:entry.update(before_strict='NO_VERDICT',after_strict='NO_VERDICT',before_repaired_conforms=None,after_repaired_conforms=None)
  ds.append(entry)
save('diagnostic_reason_proofs.json',proofs);csvout('diagnostic_case_results.csv',ds)
arm_summ=[]
for arm in sorted({x['arm'] for x in ds}):
 for w,label in audit.WORKFLOWS.items():
  es=[x for x in ds if x['arm']==arm and x['condition']==w];pos=[x for x in es if x['expected']=='PASS'];pairs=[x for x in es if 'before_strict' in x]
  arm_summ.append(dict(arm=arm,workflow=label,positive_denominator=len(pos),positive_recoveries=sum(not x['before_agreement'] and x['after_agreement'] for x in pos),positive_regressions=sum(x['before_agreement'] and not x['after_agreement'] for x in pos),reviewed_pair_denominator=len(pairs),strict_recoveries=sum(x['before_strict']!='STRICT_INTENDED_MATCH' and x['after_strict']=='STRICT_INTENDED_MATCH' for x in pairs),strict_losses=sum(x['before_strict']=='STRICT_INTENDED_MATCH' and x['after_strict']!='STRICT_INTENDED_MATCH' for x in pairs),missed_after=sum(x['after_strict']=='MISSED_INTENDED_DEFECT' for x in pairs),no_verdict_pairs=sum(x['after_strict']=='NO_VERDICT' for x in pairs),repaired_pass_to_fail=sum(x['before_repaired_conforms'] is True and x['after_repaired_conforms'] is False for x in pairs),ordinary_retained_denominator=len(es),ordinary_recoveries=sum(not x['before_agreement'] and x['after_agreement'] for x in es),ordinary_regressions=sum(x['before_agreement'] and not x['after_agreement'] for x in es),note='Provisional sum binding: no strict gains counted.' if arm=='scope_and_additional_power' else 'Single-shot IMO26-014 remains original NO_VERDICT; no execution.' if arm=='paired_boolean_branch' and w=='SINGLESHOT' else 'Same deterministic transform applied to both workflows; unchanged counterpart reuses saved reports.'))
csvout('diagnostic_summary.csv',arm_summ)
# Gains deduplicated by (workflow, case), not added across arms.
accepted={'canonical_operands','violation_polarity','paired_boolean_branch','explicit_owner_path'};gainsets={}
for w,label in audit.WORKFLOWS.items():
 es=[x for x in ds if x['arm'] in accepted and x['condition']==w];cs={x['case_id'] for x in es if 'after_strict' in x};gain={x['case_id'] for x in es if x.get('before_strict')!='STRICT_INTENDED_MATCH' and x.get('after_strict')=='STRICT_INTENDED_MATCH'}
 gainsets[label]=dict(strict_gain_cases=sorted(gain),strict_gain_count=len(gain),reviewed_pair_cases=sorted(cs),reviewed_pair_denominator=len(cs),positive_recovery_cases=sorted({x['case_id'] for x in es if x['expected']=='PASS' and not x['before_agreement'] and x['after_agreement']}),ordinary_regression_cases=sorted({x['case_id'] for x in es if x['before_agreement'] and not x['after_agreement']}))
save('deduplicated_diagnostic_gains.json',gainsets)
# Counts make exposure and proof different quantities. No causal family is
# assigned from a provisional historical cause label or solely from a verdict.
for f in FS:
 f['demonstrated_diagnostic_cases']=sorted({x['case_id'] for x in ds if x['arm']=='canonical_operands' and x['condition']==f['condition'] and x['requirement_id']==f['requirement_id'] and (x['before_conforms']!=x['after_conforms'] or ('after_repaired_conforms' in x and x['before_repaired_conforms']!=x['after_repaired_conforms']))})
save('static_findings_with_diagnostic_evidence.json',FS)
allf=FS+manual;family_summary=[]
for family in ['WRONG_IRI_NAMESPACE','SPARQL_BINDING_SCOPE','OWNER_PATH','UNIT_LITERAL','BOOLEAN_APPLICABILITY','COMPARISON_ARITHMETIC','MISSING_OBLIGATION','EXCESSIVE_SCOPE_CARDINALITY']:
 for w,label in audit.WORKFLOWS.items():
  fs=[f for f in allf if f['family']==family and f['condition']==w];reqs={f['requirement_id'] for f in fs};exposed={c for f in fs for c in f['reviewed_cases']};confirmed={c for f in fs for c in f.get('confirmed_affected_case_ids',[])}|{c for f in fs for c in f.get('demonstrated_diagnostic_cases',[])}
  family_summary.append(dict(family=family,workflow=label,faulty_shape_or_runtime_compatibility_artifacts=len(reqs),distinct_requirements=len(reqs),requirements=sorted(reqs),reviewed_negative_exposure=len(exposed),reviewed_negative_exposure_ids=sorted(exposed),manually_demonstrated_affected_cases=len(confirmed),manually_demonstrated_affected_case_ids=sorted(confirmed),retained_case_exposure=len({c for f in fs for c in f['retained_exposure']}),runtime_only_shapes=len({f['requirement_id'] for f in fs if f['certainty'].startswith('CONFIRMED_RUNTIME')})))
save('family_summary.json',family_summary);csvout('family_summary.csv',family_summary)
# Every current mismatch receives a disposition; unmatched mechanisms stay
# unconfirmed, rather than becoming made-up generator defect counts.
coverage=[]
for cid,r in R.items():
 if r['state'] not in ['COMPLETED','COMPLETED_PRIOR50']:continue
 for w,v in r['workflows'].items():
  if v['status'] not in ['MISSED_INTENDED_DEFECT','MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE']:continue
  applicable=[f for f in allf if f['condition']==w and f['requirement_id']==r['requirement_id']]
  proof=[f['mechanism'] for f in applicable if cid in f.get('confirmed_affected_case_ids',[]) or cid in f.get('demonstrated_diagnostic_cases',[])]
  coverage.append(dict(case_id=cid,requirement_id=r['requirement_id'],condition=w,current_strict_status=v['status'],confirmed_case_specific_mechanisms=sorted(set(proof)),confirmed_static_sites_on_same_shape=sorted({f['mechanism'] for f in applicable if 'confirmed_affected_case_ids' not in f}),disposition='CONFIRMED_CASE_SPECIFIC_MECHANISM' if proof else 'CONFIRMED_STATIC_ARTIFACT_DEFECT_CASE_CAUSALITY_NOT_AUTOMATICALLY_ASSIGNED' if applicable else 'MECHANISM_NOT_ESTABLISHED_DO_NOT_REUSE_PROVISIONAL_CAUSE',record=A['current_case_records']+'#/'+cid))
csvout('all_current_mismatch_dispositions.csv',coverage)
print('CORE',len({(f['condition'],f['requirement_id']) for f in FS if f['mechanism']!='RDFLIB_PLAIN_VS_XSD_STRING_COMPATIBILITY'}),'REQUIREMENTS',len({f['requirement_id'] for f in FS if f['mechanism']!='RDFLIB_PLAIN_VS_XSD_STRING_COMPATIBILITY'}));print(json.dumps(arm_summ,indent=2));print('gains',json.dumps(gainsets,indent=2))
