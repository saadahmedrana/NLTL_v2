import pathlib,json,hashlib,sys,socket,time,copy,collections,importlib.util
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0')
O=R/'outputs/audits/20261124_V0101_REPAIR_ASSESSMENT_FRESH_PILOT_PREPARATION'
RUN=R/'outputs/experiments/20261124T113231275705Z_V0101_I2_004_DEVELOPMENT_CONTINUATION'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def deny(*a,**k):raise RuntimeError('OFFLINE_NETWORK_DISABLED')
socket.create_connection=deny;socket.socket.connect=deny
assert not O.exists()
before={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
O.mkdir(parents=True)
from nltlv2.core import Project,GenerationProject
from nltlv2.schema import Schema,N,Q,U
from nltlv2.requests import initial_request
from nltlv2.prompt_accounting import measure
from nltlv2.admission import validate_declaration,definition_hash
from nltlv2.evidence import literal_identity
from rdflib import Graph,Literal,XSD,RDF,RDFS,OWL
from rdflib.compare import isomorphic
p=Project(R);s=Schema(p)
spec=importlib.util.spec_from_file_location('external_independent',R/'evaluation/independent.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
seed=RUN/'I2-004/nltl/candidate_01.ttl';repair=RUN/'I2-004/nltl/candidate_02.ttl'
assert sha(seed)=='d8986fa2c5186ae5d619696650e5f56328480bc5c3430465c4fdbc1ef9d94f9a'
assert sha(repair)=='823c65db62106f8b2c8f2fab358ee1f7b9de76fce380965915eeda6bc315164a'
closure=json.loads((RUN/'dispatch_closed.json').read_text())
D=O/'external_development_diagnostic';D.mkdir()
base=R/'evaluation/fixtures/I2-004-G-P01.ttl'
with literal_identity():g=Graph().parse(base)
ship=next(g.subjects(RDF.type,N.ship));selected=g.value(ship,N.upperIceWaterlineDisplacement);old=g.value(selected,Q.numericValue)
assert str(old)=='12.0'
with literal_identity():above=Graph().parse(base)
above.remove((selected,Q.numericValue,old));above.add((selected,Q.numericValue,Literal('13.0',datatype=XSD.decimal,normalize=False)))
above.serialize(D/'above_maximum.ttl',format='turtle');g.serialize(D/'intended_only_corrected.ttl',format='turtle')
admission=json.loads((R/'data/admissions/i2_004_research_scope.approved.json').read_text())
validated=validate_declaration(admission,s,'I2-004');assert validated['valid'],validated
results=[];start=time.monotonic()
for name,expected in [('above_maximum',False),('intended_only_corrected',True)]:
 datafile=D/(name+'.ttl')
 with literal_identity():data=Graph().parse(datafile)
 binding=dict(format_version=1,scope_id=admission['admission_id'],scope_definition_sha256=definition_hash(admission),input_sha256=sha(datafile),admitted_nodes=[str(ship)],construction_provenance=dict(kind='SYNTHETIC_CONSTRUCTION_REVIEWED',references=['User-authorized external development diagnostic, 2026-11-24','data/requirements/IACS_I2_full.txt#I2.1.2.2','mutation_provenance.json']))
 write(D/(name+'.admission.json'),binding)
 oracle=ev.oracle(data,'I2-004');assert oracle['conforms']==expected,oracle
 for label,shape_file in [('seed',seed),('repair',repair)]:
  with literal_identity():shape=Graph().parse(shape_file)
  verdict,report=ev.validate_admitted_graph(data,shape,s,'I2-004',admission,binding,sha(datafile))
  if report is not None:report.serialize(D/(label+'_'+name+'_report.ttl'),format='turtle')
  assert verdict['conforms'] is not None,verdict
  assert verdict['conforms']==(True if label=='seed' else expected),verdict
  results.append(dict(candidate=label,candidate_sha256=sha(shape_file),diagnostic=name,expected=expected,independent_oracle=oracle,verdict=verdict,agreement=verdict['conforms']==expected))
write(D/'results.json',dict(label='EXTERNAL_POST_REPAIR_DEVELOPMENT_DIAGNOSTIC_NOT_HELD_OUT',model_access=False,original_benchmark_modified=False,dispatch_closure_sha256=sha(RUN/'dispatch_closed.json'),runtime_seconds=time.monotonic()-start,results=results))
with literal_identity():roundtrip=Graph().parse(D/'intended_only_corrected.ttl')
assert isomorphic(g,roundtrip)
write(D/'mutation_provenance.json',dict(base=str(base.relative_to(R)),base_sha256=sha(base),source=str('data/requirements/IACS_I2_full.txt'),source_sha256=sha(R/'data/requirements/IACS_I2_full.txt'),clause='I2.1.2.2',quotation="Where multiple waterlines are used for determining the UIWL, the displacement is to be determined from the waterline corresponding to the greatest displacement.",above_expected='FAIL: selected 13.0 kt exceeds maximum of supplied 10.0, 12.0, 11.0 kt.',corrected_expected='PASS: replace only selected numeric value with 12.0 kt.',removed_triple=[str(selected),str(Q.numericValue),old.n3()],added_triple=[str(selected),str(Q.numericValue),Literal('13.0',datatype=XSD.decimal,normalize=False).n3()],changed_graph_triples=dict(removed=len(set(g)-set(above)),added=len(set(above)-set(g))),corrected_graph_isomorphic_to_original=True,limitations='Diagnostic deliberately authored after observing coverage gap; not held out. No generation/review/repair input, score change, or original fixture change.'))
# Pilot documents are inert proposal configurations, never transport/runner instances.
P=O/'pilot_preparation';P.mkdir();cfg=json.loads((R/'configs/nltl.json').read_text());cfg['maximum_candidate_attempts']=2;cfg['context_resolution']['max_reviews_per_run']=4;cfg['context_resolution']['max_reviews_per_candidate']=3;cfg['continuation']={'max_provider_calls':10};cfg['method']='offline';cfg['network_enabled']=False
settings={k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']}
rids=['I2-004','I2-005','IMO-001','TRF-010','TRF-035'];readiness=[];sizes=[]
for rid in rids:
 ctx=s.context(rid)
 if rid=='I2-004':
  ctx['admission']=copy.deepcopy(validated['context'])
  ctx['scope']+=' External population/date eligibility and edition selection are supplied by caller admission, not independently inferred from RDF. Conditions within the represented requirement remain in scope; activation and query correctness are separate obligations.'
 req=initial_request(GenerationProject(R),ctx,settings);row=measure(req);row.update(requirement_id=rid,admission_included=rid=='I2-004',status='EXACT_CURRENT_INITIAL_RENDER' if rid=='I2-004' else 'CONDITIONAL_BASELINE_EXCLUDING_UNAPPROVED_ADMISSION',identical_for_both_arms=True)
 sizes.append(row)
 write(P/(rid+'_initial_request_OFFLINE_ONLY.json'),req)
 for method in ['NLTL','Single-shot']:
  c=copy.deepcopy(cfg);c.update(proposed_method=method,proposal_only=True,admission_file='data/admissions/i2_004_research_scope.approved.json' if rid=='I2-004' else None)
  if method=='Single-shot':c.update(maximum_candidate_attempts=1,semantic_review=False);c['continuation']['max_provider_calls']=1
  write(P/(rid+'_'+method+'_PROPOSED.json'),c)
  p.config(str((P/(rid+'_'+method+'_PROPOSED.json')).relative_to(R)))
 source=s.catalog[ctx['requirement']['source']];terms=ctx['schema_terms']
 root,paths=s.allowed_paths(rid)
 readiness.append(dict(requirement_id=rid,status='READY_FOR_SEPARATELY_AUTHORIZED_FRESH_PAIR' if rid=='I2-004' else 'BLOCKED_NO_APPROVED_REQUIREMENT_SCOPE',source_clause=ctx['requirement']['clause'],source_file=source['file'],source_sha256=source['sha256'],source_hash_valid=sha(R/source['file'])==source['sha256'],catalog_metadata_missing=[k for k in ['document_id','edition','authority','provenance'] if not source.get(k)],target_owner=str(root),allowed_paths={k:[list(v) for v in vals] for k,vals in paths.items()},unresolved_ownership=ctx.get('unresolvedOwnership'),unresolved_source_context=ctx.get('unresolvedSourceContext'),source_selection=ctx.get('source_selection'),schema_terms=terms,ontology_evidence=ctx.get('ontology_evidence'),quantity_encoding=ctx.get('quantityEncoding')))
write(P/'readiness.json',readiness);write(P/'request_sizes.json',sizes)
selection=json.loads((R/'evaluation/selections/regression_core.json').read_text());inventory=[]
for rid in rids:
 cases=[c for c in selection['cases'] if c['requirement_id']==rid]
 inventory.append(dict(requirement_id=rid,original_cases=len(cases),positive=sum(c['expected']=='PASS' for c in cases),negative=sum(c['expected']=='FAIL' for c in cases),counterparts=sum(bool(c.get('counterfactual')) for c in cases)))
write(P/'plan.json',dict(status='PREPARED_UNDISPATCHED_BLOCKED_PENDING_SCOPES_AND_EVALUATION_ADMISSIONS',requirements=rids,deferred=['I2-042'],destination='https://aalto-openai-apigw.azure-api.net/v1/openai/responses',settings=settings,initial_candidate_policy='FRESH_GENERATION_NO_SEED_NO_PRIOR_ISSUES_NO_HISTORY_NO_SOLUTIONS',per_requirement=dict(single_shot_provider_calls=1,nltl_initial_generations=1,nltl_repairs_max=1,nltl_candidates_max=2,nltl_primary_reviews_max=4,primary_reviews_per_candidate_max=3,shared_response_correction_per_review=1,retrieval_rounds_max=2,nltl_provider_calls_max=10),aggregate_provider_calls_max=55,evaluation_inventory=inventory,selected_output_policy='Evaluate only after every dispatch closes. Internally accepted NLTL only; otherwise NO_VERDICT. Single-shot delivered output independently evaluated. Rejected candidates diagnostic-only.',readiness_gate='All five separately admitted and source/representation ambiguities reviewed; no inferred scope extension. No dispatch authorized by this preparation.',resources='Existing production source/schema/prompt routes only; no pilot artifact or diagnostic paths in generation resource allowlist.',packet_sizes='Exact current rendered UTF-8 bytes, not tokens or total future-run sizes. Four unapproved admission envelopes excluded. Review/retry/repair sizes depend on unseen outputs and bounded retrieval; no fabricated code used.'))
# Capture narrow ontology evidence to assess unresolved representation semantics.
evidence={}
for name in ['designIceCondition','shipCategory','mediumFirstYearIceWithPossibleOldIceInclusions','classificationSocietyRuleLength','ruleLength','classificationSociety','bowRegion','iceClass']:
 evidence[name]=[(str(pred),str(obj)) for pred,obj in s.graph.predicate_objects(N[name])]
write(P/'representation_semantics_review.json',evidence)
write(O/'exact_inspected_references.json',dict(seed=str(seed.relative_to(R)),seed_sha256=sha(seed),repair=str(repair.relative_to(R)),repair_sha256=sha(repair),diff=str((RUN/'I2-004/nltl/diff_01_02.patch').relative_to(R)),diff_sha256=sha(RUN/'I2-004/nltl/diff_01_02.patch'),source='data/requirements/IACS_I2_full.txt',source_sha256=sha(R/'data/requirements/IACS_I2_full.txt'),approved_scope='data/admissions/i2_004_research_scope.approved.json',approved_scope_sha256=sha(R/'data/admissions/i2_004_research_scope.approved.json'),independent_evaluator_sha256=sha(R/'evaluation/independent.py'),dispatch_closed=closure))
changed=[k for k,v in before.items() if not (R/k).is_file() or sha(R/k)!=v];assert not changed,changed
write(O/'preservation_verification.json',dict(status='PASS',protected_existing_files=len(before),modified_or_deleted=[],network='Socket connections disabled; no provider/transport constructed.',pipeline_changes=False,historical_run_unchanged=True,original_cases_scores_fixtures_scope_tracker_unchanged=True,manifest=before))
print(json.dumps(dict(output=str(O),results=[{k:r[k] for k in ['candidate','diagnostic','expected','agreement']}|{'conforms':r['verdict']['conforms']} for r in results],sizes=[{'id':x['requirement_id'],'bytes':x['rendered_bytes'],'status':x['status']} for x in sizes],protected=len(before)),indent=2))
