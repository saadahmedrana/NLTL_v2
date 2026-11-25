from pathlib import Path
import sys,json,hashlib,collections,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0114_IMO001_DIAGNOSTIC_PREFLIGHT';B=R/'outputs/experiments/20261125_V0114_IMO001_HOSTED_DEVELOPMENT_DIAGNOSTIC_01';S=R/'results/20261125_V0114_IMO001_HOSTED_DEVELOPMENT_DIAGNOSTIC_01';S.mkdir(exist_ok=False);sys.path.insert(0,str(R/'src'))
from nltlv2.hosted_pilot import verify
from nltlv2.core import write
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
closed=load(B/'dispatch_closed.json');assert closed['dispatch_closed'] and closed['outstanding_provider_processes']==0 and not closed['errors'];assert closed['physical_calls']==5;verify(R,load(B/'freeze_lock.json'));d=B/'IMO-001/NLTL';run=load(d/'run.json');pair=load(B/'IMO-001/pair.json');evaluation=load(B/'evaluation/evaluation_complete.json');assert pair['shared_start_equal'] and pair['shared_raw_equal'] and pair['initial_request_equal'];assert evaluation['dispatch_closed_sha256']==sha(B/'dispatch_closed.json');assert sha(B/'selected_outputs.json')==closed['selection_manifest_sha256'];assert all(sha(R/n)==h for n,h in closed['all_candidate_sha256'].items());assert run['repair_counts']==dict(technical=1,semantic=0) and run['accepted_version']==2
manifest=load(B/'manifest.frozen.json');actualcfg=load(B/'IMO-001/config.json');scopefile=manifest['scope_files']['IMO-001'];assert actualcfg['admission_file']==scopefile;scopeproof=load(A/'scope_files_resolution.json');assert sha(R/scopefile)==scopeproof['approved_declaration_sha256'];gen=load(B/'provider/call_001_request.json')['payload'];assert json.loads(gen['input'][1]['content'][0]['text'])['context']['admission']==scopeproof['loaded_admission']['context']
metrics=[];review_trace=[];questions=[];wires={}
for p in sorted((B/'provider').glob('call_*_request.json')):
 n=int(p.stem.split('_')[1]);req=load(p);payload=req['payload'];wire=json.loads(payload['input'][1]['content'][0]['text']);wires[n]=wire;resp=load(B/'provider'/f'call_{n:03d}_response.json');assert json.loads((B/'provider'/f'call_{n:03d}_request.body').read_text())==payload
 metrics.append(dict(call=n,route=req['route'],request_file=str(p),exact_request_body=str(B/'provider'/f'call_{n:03d}_request.body'),request_sha256=sha(B/'provider'/f'call_{n:03d}_request.body'),request_bytes=(B/'provider'/f'call_{n:03d}_request.body').stat().st_size,response_file=str(B/'provider'/f'call_{n:03d}_response.json'),raw_response_file=str(B/'provider'/f'call_{n:03d}_response.body'),model=resp.get('returned_model'),identity_status=resp.get('identity_status'),status=resp['status'],usage=resp['usage'],client_seconds=resp['elapsed_seconds'],capacity=resp.get('token_budget')))
 if req['route']=='review':
  raw=load(B/'provider'/f'call_{n:03d}_response.json');obj=json.loads(raw['text']);validated=load(d/f'review_validated_{n-1:03d}.json');routing=load(d/f'reviewer_proposal_validation_{n-1:03d}.json');assert routing['route']=='VALID';catalog={e['evidence_id']:e for e in wire['evidence_catalog']['entries']}
  for q in obj['questions']:
   questions.append(dict(call=n,question=q,resolved_evidence=[catalog[e if isinstance(e,str) else e['id']] for e in q.get('evidence',[])],source_inference_is_not_proven_by_reference_validity=True))
  review_trace.append(dict(call=n,assessment=obj['assessment'],response=raw['text'],validated=validated,proposal_validation=routing,questions=obj['questions'],issues=obj['issues'],original_prior_issue_summaries=wire['prior_issues'],validation_failures=[]))
assert not list(d.glob('reviewer_format_failure_*.json'));assert [x['assessment'] for x in review_trace]==['HUMAN_REVIEW_REQUIRED','HUMAN_REVIEW_REQUIRED','APPROVE'];assert all(not x['issues'] for x in review_trace)
# Verify readable question handoff directly from serialized provider input, including nested JSON catalog text.
def strings(value):
 out=[]
 if isinstance(value,dict):
  for v in value.values():out+=strings(v)
 elif isinstance(value,list):
  for v in value:out+=strings(v)
 elif isinstance(value,str):
  out.append(value)
  if value.startswith(('[','{')):
   try:nested=json.loads(value)
   except Exception:return out
   if not isinstance(nested,str):out+=strings(nested)
 return out
handoff=[]
for n in [4,5]:
 texts=strings(wires[n]);prior=[q for q in questions if q['call']<n]
 handoff.append(dict(next_provider_call=n,prior_issues=wires[n]['prior_issues'],earlier_questions=[dict(original_call=q['call'],missing=q['question']['missing'],missing_text_present=any(q['question']['missing'] in s for s in texts),why_text_present=any(q['question']['why'] in s for s in texts)) for q in prior],evidence_catalog_has_query_hashes=True,readable_prior_question_history_present=False))
assert all(not q['missing_text_present'] and not q['why_text_present'] for h in handoff for q in h['earlier_questions'])
retrieval=load(d/'retrieval_ledger.json');retrieval_summary=[]
for e in retrieval:
 rows=e['entries'];retrieval_summary.append(dict(round=e['round'],status=e['status'],novel=e['novel'],requests=e['requests'],new_schema_terms=sum(len(x.get('term_iris',[])) for x in rows),new_explicit_triples=sum(len(x.get('ontology_triples',[])) for x in rows),new_source_characters=sum(x.get('characters',0) for x in rows if x['kind']=='source'),term_iris=[t for x in rows for t in x.get('term_iris',[])],current_requirement_representation_mappings=[m for x in rows for m in x.get('representation_mappings',[]) if m['scope']=='CURRENT_REQUIREMENT'],all_entries=rows))
assert [(x['new_schema_terms'],x['new_explicit_triples']) for x in retrieval_summary]==[(20,298),(24,284)]
repair_request=load(B/'provider/call_002_request.json');packet=json.loads(repair_request['payload']['input'][1]['content'][0]['text']);first=load(d/'technical_01.json');assert packet['previous_candidate']==(d/'candidate_01.ttl').read_text();assert packet['candidate_sha256']==first['candidate_sha256'];assert packet['current_findings'][0]['diagnostic']==first['findings'][0]['diagnostic'];assert load(d/'request_001_integrity.json')['previous_code_full'];code_diff=(d/'diff_01_02.patch').read_text();assert sum(line.startswith('+') and not line.startswith('+++') for line in code_diff.splitlines())==1
summary=dict(label='FRESH_PREVIOUSLY_EXPOSED_SHARED_START_DEVELOPMENT_DIAGNOSTIC_NOT_CONTROLLED_PERFORMANCE_STUDY',run_id=B.name,version='0.11.4',design='FRESH_NOT_SEEDED',approved_scope_file=scopefile,approved_scope_sha256=sha(R/scopefile),scope_loaded_through_scope_files=True,shared_start_bytes_equal=True,shared_raw_equal=True,initial_requests_equal=True,seed_candidate=None,initial_sha256=first['candidate_sha256'],revised_sha256=load(d/'technical_02.json')['candidate_sha256'],calls=5,used=dict(initial_generation=1,technical_revisions=1,semantic_revisions=0,candidates=2,primary_reviews=3,corrections=0,retrieval_rounds=2),limits=dict(physical_calls=11,technical_revisions=1,semantic_revisions=1,candidates=3,primary_reviews=4,primary_per_candidate=3,shared_correction_per_review=1,retrieval_rounds=2,seconds=600),review_validation_failures=[],all_three_reviews_validated=True,review_assessments=[x['assessment'] for x in review_trace],material_questions=questions,retrieval=retrieval_summary,semantic_feedback_authorized_revision=False,semantic_repair_exercised=False,technical_revision=dict(change='Added missing default Turtle prefix only',diff=code_diff,latest_candidate_full=True,exact_original_diagnostic_delivered=True),technical_recheck=load(d/'technical_02.json'),terminal=run['status'],delivery=run['delivery'],reviewer_approval='APPROVE',approval_is_not_correctness_certification=True,question_handoff_limitation=handoff,question_resolution='Final APPROVE implicitly clears questions; no explicit rationale, readable prior questions absent from later packets. Evidence does not establish resolution.',usage={k:sum(q['usage'][k] for q in metrics) for k in ['input_tokens','output_tokens','total_tokens']},phase_client_seconds={route:sum(q['client_seconds'] for q in metrics if q['route']==route) for route in ['generation','syntax_repair','review','review_format_retry','targeted_repair']},technical_check_seconds=sum(load(p)['check_seconds'] for p in d.glob('technical_*.json')),workflow_seconds=closed['elapsed_seconds'],independent_evaluation_seconds=evaluation['elapsed_seconds'],retrieval_separate_timing='NOT_RECORDED_BY_FROZEN_CONTROLLER',provider_internal_timings='UNAVAILABLE',independent_results=evaluation['summary'],selection_fixed_before_evaluation=True,no_further_provider_calls=True)
write(S/'summary.json',summary);write(A/'actual_request_index.json',metrics);write(A/'actual_review_trace.json',review_trace);write(A/'question_evidence_and_retrieval.json',dict(questions=questions,retrieval=retrieval_summary));write(A/'question_handoff_audit.json',handoff);write(A/'complete_actual_technical_repair_packet.json',dict(original_candidate_sha256=first['candidate_sha256'],exact_original_diagnostics=first['findings'],actual_provider_request=repair_request,integrity=load(d/'request_001_integrity.json'),response=load(B/'provider/call_002_response.json'),code_diff=code_diff,recheck=load(d/'technical_02.json'),semantic_repair_packet_dispatched=False))
report=f'''v0.11.4 fresh IMO-001 shared-start diagnostic — CLOSED

One authorized run at the established Aalto Responses endpoint, gpt-oss-120b. No pipeline/prompt/scope changes, extra requirements, regeneration, manual corrections or preferred-result rerun. Fresh generation (not seeded); previously exposed requirement, not held out. One actual response/candidate preserved byte-for-byte for both arms. Source/configuration verified against 85 frozen files, 282 offline tests passed. scope_files['IMO-001'] actually set config.admission_file={scopefile}; actual initial model admission equals the approved loaded declaration (raw declaration hash {sha(R/scopefile)}), unchanged. No prior diagnosis, failed historical review, solution or evaluation input was added to requests.

1. Simplified review validation

All THREE simplified reviews validated directly. Zero format corrections, citation failures, invalid code locations or proposal-routing failures. Calls 3/4 returned HUMAN_REVIEW_REQUIRED with context questions; call 5 returned APPROVE with empty issues/questions. All five provider responses completed with returned model gpt-oss-120b, identity MATCH; no truncation, infrastructure/integrity failure or provider retry.

2. Context questions, supplied evidence and retrieval

Call 3 asked for a representation of intended operational region/polar waters, citing SOURCE E191 (the supplied Polar Code Definitions passage). Its bounded schema request added 20 terms and 298 explicit triples, including shipOperatesInPolarWaters and many manual/document terms. Zero new source characters; no CURRENT_REQUIREMENT representation mappings. Finding a related property does not prove intended-region semantics or ownership under this requirement; external scope assumptions must remain distinct from conditions inside the definition.

Call 4 asked how to represent “at least medium first-year ice”, noting exact sh:hasValue may reject stronger capability. It cited SOURCE E436 and RDF_FACT E86. E86 is the controlled value's draftConceptId, not proof of ordering semantics. Second bounded schema retrieval added 24 terms and 284 triples, including iceConditionClassification and designIceThickness, plus other design/load terms. Zero new source characters and no CURRENT_REQUIREMENT representation mapping. Related vocabulary was added; no explicit ordering relation or resolution of the question was established by these retrieval records alone. Foreign requirement mappings stayed labelled nontransferable.

Call 5 then returned APPROVE without explaining either withdrawal. Important handoff limitation: actual follow-up requests had prior_issues=[] and did NOT contain the earlier questions' missing/why text, even inside nested catalog JSON. Retrieval metadata supplied query hashes and new terms, not readable question history. The questions survive in review/retrieval artifacts, but their resolution is not demonstrated. question_handoff_audit.json records exact presence checks. The frozen policy treats the complete final APPROVE as clearing uncertainty; this report preserves that INTERNAL status without claiming a substantiated resolution or retroactively overriding selection. No implementation was changed during this run.

3. Feedback that reached the generator

One TECHNICAL syntax repair was dispatched. The fresh candidate used :CategoryAShipShape without declaring ':'. Exact original parser diagnostic “Bad syntax (Prefix ':' not bound)” and the COMPLETE latest candidate/version/hash reached the same generator. The actual diff adds only:
  @prefix : <https://example.org/shapes#> .
No other code changed. Recheck passed Turtle/Meta-SHACL, activation, representation/admission and execution checks with no findings. Original candidate hash {summary['initial_sha256']}; repaired hash {summary['revised_sha256']}.

NO actionable semantic code issue was returned: issues=[] in all three reviews. The second question includes a semantic concern but is structured as a context question, not repair authorization. Therefore zero semantic-repair calls; semantic repair is NOT_EXERCISED. This is not a repair-budget failure: its one reserved slot remained unused. No undispatched semantic packet is described as delivered feedback. Complete actual syntax packet/diagnostics/integrity/diff/recheck: {A}/complete_actual_technical_repair_packet.json. All original packets, raw responses and validated review/evidence artifacts: {B}.

4. Delivery versus approval and independent behavior

Frozen terminal: ACCEPTED, candidate 2. Delivery: ACCEPTED. Reviewer final assessment/handoff: APPROVE. These are INTERNAL checks/model approval, not correctness certification. Selection was sealed before independent evaluation; it was not selected by score. The only recovery was making previously unparsable code executable, not fixing semantic logic.

After verified dispatch closure, existing independent evaluation ran once on unchanged 5 cases and 3 counterparts per arm, with original shapes unedited:
• Single-shot: 5 NO_VERDICT due to the original Turtle parse error; raw original artifact remains preserved. No scope violations detected, but an unparsable shape is not certified scope-compliant.
• NLTL: 4 correct / 1 wrong / 0 no-verdict; zero scope-violation cases; 4 admitted-correct. All 3 counterparts pass. All 3 negative-case strict attributions remain UNRESOLVED_ATTRIBUTION; no verified strict-detection credit.
• Remaining substantive defect: NLTL rejects valid IMO-001-P02. The shape targets all supplied ships and unconditionally requires both Category A and the designated medium-first-year condition, despite the approved scope not assuming every record has that category/condition. The added prefix preserves that logic. Successful execution and final APPROVE did not establish semantic correctness. This diagnosis is post-closure analysis only; no new model calls or edits follow it.

5. Calls, capacity and timings

Used 5/11 total provider HTTP calls: 1 fresh generation + 1 syntax repair + 3 reviews. Two candidates; zero semantic revisions/corrections; two retrieval rounds. Ceilings remained one technical/one semantic revision, three candidates, four primary reviews (three per candidate), one shared correction per review, two retrieval rounds and 600 seconds. Final APPROVE triggered early stopping.

Usage: input {summary['usage']['input_tokens']:,}, output {summary['usage']['output_tokens']:,}, total {summary['usage']['total_tokens']:,} tokens, including provider-reported cached input/reasoning as returned. Client request times: generation {summary['phase_client_seconds']['generation']:.2f}s; syntax repair {summary['phase_client_seconds']['syntax_repair']:.2f}s; reviews {summary['phase_client_seconds']['review']:.2f}s; corrections/semantic repair 0. Technical checks {summary['technical_check_seconds']:.2f}s; total workflow {summary['workflow_seconds']:.2f}s; independent evaluation {summary['independent_evaluation_seconds']:.2f}s. Separate retrieval timer not exposed by the frozen controller; provider queue/loading/GPU timings unavailable.

Exact request bytes and per-call tokens/times/capacity are in actual_request_index.json and {S}/timing_and_usage.tsv. Initial payload 74,648 bytes; supplied text count 21,249 + requested output 16,000 = 37,249 lower bound, below the known 131,072 context. Every later call passed the existing input+output capacity guard without truncation. Provider framing and lower service limit remain unexposed. No arbitrary byte ceiling, hidden retry, extra metadata HTTP call or model fallback.

6. Evidence and preservation

Review trace: {A}/actual_review_trace.json
Question evidence/retrieval: {A}/question_evidence_and_retrieval.json
Question carry-forward limitation: {A}/question_handoff_audit.json
Actual provider bodies/responses: {B}/provider
Independent results: {B}/evaluation/selected_results.json
Summary: {S}/summary.json
All candidates, original diagnostics, requests/responses, usage/latencies, code diff, validation and transitions preserved. Current source/prompts/configuration, approved scope, all previous outputs/scores/fixtures and retention ledger remain unchanged; preservation_verification.json records hashes. No further calls after closure. This is one fresh-generation development diagnostic, not workflow superiority or held-out performance evidence.
'''
(S/'REPORT.txt').write_text(report);(A/'DIAGNOSTIC_REPORT.txt').write_text(report);(S/'timing_and_usage.tsv').write_text('call\troute\trequest_bytes\tinput_tokens\toutput_tokens\tclient_seconds\n'+''.join(f"{x['call']}\t{x['route']}\t{x['request_bytes']}\t{x['usage']['input_tokens']}\t{x['usage']['output_tokens']}\t{x['client_seconds']}\n" for x in metrics))
protected=load(A/'protected_before.json');changed=[n for n,h in protected.items() if not (R/n).is_file() or sha(R/n)!=h];assert not changed,changed;verify(R,load(B/'freeze_lock.json'));write(A/'preservation_verification.json',dict(original_files_checked=len(protected),changed=[],frozen_source_config_prompts_verified=True,scope_loaded_through_scope_files_and_unchanged=True,all_candidate_hashes_verified=True,selection_before_evaluation_verified=True,closure_hash_matches_evaluation=True,previous_results_fixtures_ledger_unchanged=True,provider_calls=5,provider_calls_after_closure=0))
shutil.copyfile('/tmp/preflight_v0114_live.py',A/'preflight_script.py');shutil.copyfile('/tmp/report_v0114_live.py',A/'report_script.py');write(A/'artifact_manifest.json',{str(p.relative_to(A)):sha(p) for p in sorted(A.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})
print(json.dumps(dict(report=str(S/'REPORT.txt'),calls=5,used=summary['used'],terminal=run['status'],reviewer_approval='APPROVE',semantic_repair_exercised=False,usage=summary['usage'],workflow_seconds=summary['workflow_seconds'],evaluation_seconds=summary['independent_evaluation_seconds'],prior_question_handoff_gap_confirmed=True,previous_files_unchanged=len(protected)),indent=2))
