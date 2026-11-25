"""Offline software verification, interface replay and packet preparation. Never imports a live transport.
This is an audit artifact builder, not another workflow or a live continuation executor.
"""
from pathlib import Path
import argparse,copy,dataclasses,hashlib,importlib.util,io,json,re,sys,unittest,contextlib
from nltlv2.core import Project,Candidate,Finding,digest,offline_network_guard,write
from nltlv2.runner import Runner
from nltlv2.tracking import Tracker
from nltlv2.schema import Schema
from nltlv2.admission import load_admission
from nltlv2.checks import check,runtime_probe
from nltlv2.evidence import evidence_catalog,citation_error,code_location,probe_summary
from nltlv2.requests import parse_review,review_conflicts,repair_request,compact_review,review_base
from nltlv2.review_validation import validate_review
from nltlv2.prompt_accounting import measure

SEED='d8986fa2c5186ae5d619696650e5f56328480bc5c3430465c4fdbc1ef9d94f9a'
V091='outputs/experiments/20261123T120732989561Z_V091_I2_004_BOUNDED_OPERATIONAL_CHECK'
V092='outputs/experiments/20261123T144916393610Z_V092_I2_004_DEVELOPMENT_CONTINUATION'

class PreparedBoundary(Exception):pass
class CaptureOnly:
 is_live=False
 def dispatch(self,request,*args):
  self.request=copy.deepcopy(request)
  raise PreparedBoundary('PREPARED_UNDISPATCHED: no model transport exists')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def short(path,root):return str(path.relative_to(root))
def internal_packet(root,c,ctx,probe,findings,out,config):
 runner=Runner(Project(root),config,CaptureOnly(),out);runner.admission_context=ctx['admission'];runner.execution_summaries[c.version]=probe_summary(c,probe)
 (out/f'candidate_{c.version:02d}.ttl').write_text(c.code)
 try:runner.review(c,ctx,None,{'status':'INITIAL_CANDIDATE','changes':[]},Tracker(),findings)
 except PreparedBoundary:pass
 else:raise AssertionError('Preparation must stop before any transport')
 request=runner.transport.request;body=json.loads((out/'review_state_001.json').read_text());return request,body

def adapt_response(raw,body,c):
 """Interface-only projection; no reason/decision/path/uncertainty edits. Never production normalization."""
 obj=json.loads(raw['text']);original=copy.deepcopy(obj);actions=[];unmapped=[];catalog=body['evidence_catalog']
 obj.update({k:body[k] for k in ['candidate_version','candidate_sha256','review_request_id']})
 def location(quote):
  if not isinstance(quote,str) or not quote.strip():return None
  start=c.code.find(quote)
  if start>=0:return code_location(c,start,start+len(quote))
  # Only the saved indentation discrepancy may be projected to an exact span.
  needle=' '.join(quote.split());tokens=list(re.finditer(r'\S+',c.code));matches=[]
  for i in range(len(tokens)):
   value=[]
   for j in range(i,len(tokens)):
    value.append(tokens[j].group());joined=' '.join(value)
    if joined==needle:matches.append((tokens[i].start(),tokens[j].end()));break
    if len(joined)>=len(needle):break
  if len(matches)==1:
   a,b=matches[0];actions.append(dict(kind='CODE_WHITESPACE_TO_SPAN',asserted_original=quote,extracted_exact=c.code[a:b]));return code_location(c,a,b)
  return None
 def visit(x,path='$'):
  if isinstance(x,list):
   for i,v in enumerate(x):visit(v,path+'['+str(i)+']')
  elif isinstance(x,dict):
   for source,key,quote in [(True,'source_evidence_id','source_excerpt'),(False,'evidence_id','evidence_excerpt')]:
    if quote in x:
     matches=[e for e in catalog['entries'] if citation_error(catalog,e['evidence_id'],x[quote],source=source) is None]
     if len(matches)==1:
      old=x.get(key);x[key]=matches[0]['evidence_id'];actions.append(dict(path=path+'.'+key,kind='SUPPLIED_EVIDENCE_ALIAS',original=old,new=x[key]))
     else:unmapped.append(dict(path=path+'.'+key,matches=len(matches),original=x.get(key)))
   if 'candidate_excerpt' in x or 'insertion_context' in x:
    quote=x.get('candidate_excerpt') or x.get('insertion_context');loc=location(quote)
    if loc:x['candidate_location']=loc;x.pop('candidate_excerpt',None);x.pop('insertion_context',None)
    else:unmapped.append(dict(path=path+'.candidate_location',reason='No unique exact/token-equivalent code span; unchanged'))
   # Historical proposals did not distinguish path roles. Make the field-role
   # projection explicit only for an exact declared numeric tail. Never edit path.
   if x.get('proposed_path') and x['proposed_path'][-1]==body['context']['quantityEncoding']['numeric_predicate']:
    x['proposed_path_role']='NUMERIC_OPERAND';actions.append(dict(path=path+'.proposed_path_role',kind='EXPLICIT_NUMERIC_OPERAND_ROLE',original=None,new='NUMERIC_OPERAND'))
   for k,v in list(x.items()):
    if k not in ['candidate_location','previous_location']:visit(v,path+'.'+k)
 visit(obj)
 def substance(x):
  if isinstance(x,list):return [substance(v) for v in x]
  if isinstance(x,dict):return {k:substance(v) for k,v in x.items() if k not in ['candidate_version','candidate_sha256','review_request_id','source_evidence_id','evidence_id','candidate_excerpt','insertion_context','candidate_location','previous_location','proposed_path_role']}
  return x
 assert substance(original)==substance(obj),'SUBSTANTIVE_REPLAY_EDIT_FORBIDDEN'
 return obj,dict(label='INTERFACE_ONLY_PROJECTION_NOT_HISTORICAL_CREDIT',actions=actions,unmapped=unmapped,substantive_claims_unchanged=True)

def retention_ledger(root):
 import ast
 rows=[
 ('KEEP','Full latest candidate and version/hash integrity','requests.py::repair_request,requests.py::assert_integrity,runner.py::Runner.dispatch','Stale/truncated repair risks; chained repairs, exact diagnostic and complete-latest delivery controls pass.','Frozen candidate/hash, latest findings, artifact bytes and dispatch validator.'),
 ('FIX','Original parser/SHACL/SPARQL diagnostics','checks.py::check,checks.py::runtime_probe,sparql_analysis.py::analyze','Malformed unreachable minCount now fails generic Meta-SHACL. Full original diagnostic reports are retained; concise review findings reference artifacts.','Pinned parsers/engine, structural validation, raw logs and candidate-bound findings.'),
 ('SIMPLIFY','Canonical vocabulary, quantities, units and datatypes','schema.py::Schema.context,checks.py::check,requests.py::repair_findings','One evidence collection replaces repeated context; canonical/type/unit declarations and no-conversion controls remain.','Unchanged ontology/registry/quantity encoding and representation mappings.'),
 ('KEEP','Ontology individuals without registry rows','schema.py::Schema.__init__,schema.py::Schema.closure','Range/member controls retain registry-absent individuals without broad ancestor expansion.','Explicit ontology type/range/hierarchy and relevance seeds; no answer lists.'),
 ('FIX','Nested SELECT actual pre-binding context','checks.py::check,checks.py::sparql_checks,sparql_analysis.py::analyze','Standard SPARQL constraints bind focus; custom validators also bind value and supplied parameters. Controls exercise missing projection and valid contexts.','Locked engine contract, validator attachment/parameter declarations and AST; uncertain bindings stay warnings.'),
 ('KEEP','Activation, deactivation and reachable enforcement','activation.py::analyze,activation.py::checks,runner.py::Runner.assess_candidate','Existing root/nested/orphan/deactivated/material-scope controls still pass.','Supported SHACL graph semantics, explicit scope and uncertainty gate.'),
 ('SIMPLIFY','Stable issues, regressions, repetition and oscillation','tracking.py::Tracker.observe,tracking.py::Tracker.stagnation_stop,requests.py::concise_prior','Tracker is byte-identical. Wire prior state is concise; explicit reconciliation and repetition/regression controls are preserved.','Stable obligation/check IDs, immutable event history and structural heuristics.'),
 ('SIMPLIFY','Source/reference retrieval and provenance','context_resolution.py::Resolver.resolve,source_context.py::select_document,evidence.py::wire_catalog','Material context remains available through bounded retrieval. Wire aliases omit repeated internal hash maps; exact provenance stays in artifacts.','Pinned catalog, exact passages, internal content/provenance hashes and explicit gaps.'),
 ('KEEP','Common research scope without evaluation IDs','admission.py::validate_declaration,runner.py::Runner.dispatch','Existing route-wide canary/admission integrity controls pass; approved declaration bytes preserved.','One common approved declaration and evaluation-only per-input node/hash bindings.'),
 ('FIX','Grounded review with short IDs and code ranges','evidence.py::evidence_catalog,evidence.py::extract_location,evidence.py::resolve_locations,review_validation.py::validate_review','E aliases bind immutable evidence hashes. Server extracts exact code; unknown IDs, stale/invalid spans and altered asserted quotations fail.','Trusted supplied context, immutable candidate/request binding, exact source/fact identity; model interpretation remains unverified.'),
 ('SIMPLIFY','Unified functional change and removal assessment','review_protocol.py::reviewer_schema,review_validation.py::validate_review,change_review.py::manifest','One change assessment includes removal disposition; no nested duplicate list on the wire. Missing/contradictory assessment controls remain.','Previous/current full code once, functional change IDs, source grounds and explicit obligation-loss disposition.'),
 ('FIX','Property versus numeric-operand path roles','requests.py::review_conflicts,schema.py::Schema.allowed_paths','Declared quantity-tail traversals pass only with NUMERIC_OPERAND role; wrong owner branches/tails still conflict. Saved proposals stay unchanged.','Explicit role, owner/subclass mapping and declared numeric predicate; no inferred conversion.'),
 ('KEEP','Immutable retries and bounded candidates/reviews/retrieval','requests.py::compact_review,requests.py::review_base,runner.py::Runner.review,core.py::Project.config','Retry adds feedback only; identical candidate/prior packet retained, failed review never enters tracker or authorizes repair.','Separate counters, deep-frozen request, all independent errors and explicit terminal outcomes.'),
 ('KEEP','Identical initial inputs/settings for paired workflows','requests.py::initial_request,runner.py::Runner.run','Existing exact paired-request equality control passes; generator prompt/context route unchanged.','One frozen initial context/settings and provider renderer; cross-version contexts are not matched experiments.'),
 ('KEEP','One-call Single-shot','runner.py::Runner.run,core.py::Project.config','Existing control prohibits checks/probe/review on the Single-shot path and verifies one generation dispatch.','Original raw response and one-call policy; no feedback from evaluation.'),
 ('FIX','Evaluation isolation and mandatory dispatch closure','core.py::GenerationProject.path,../evaluation/independent.py::require_dispatch_closure','Closure is now mandatory and bound to selection manifest and candidate bytes. General guard controls run without scoring evaluation fixtures.','Separate evaluator/resources, closure receipt, frozen selection/NO_VERDICT and unchanged denominators.'),
 ('REMOVE','Redundant wire copies and answer-bearing production machinery','requests.py::compact_review,evidence.py::wire_catalog,core.py::GenerationProject.path','Nested request/raw-response copies, duplicate execution-catalog entries and duplicated change/removal responses removed. Forbidden-resource controls remain.','Keep full logs/history as artifacts and source/representation metadata only; no profiles, permissions, witnesses, matcher framework or regeneration.')]
 result=[]
 for i,(rec,cap,refs,problem,deps) in enumerate(rows,1):
  locations=[]
  for ref in refs.split(','):
   file,qual=ref.split('::');path=(root/'src/nltlv2'/file).resolve()
   if file.startswith('../evaluation/'):path=root/'evaluation'/file.split('/')[-1]
   tree=ast.parse(path.read_text());parts=qual.split('.');nodes=tree.body
   for name in parts:
    node=next(n for n in nodes if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name);nodes=getattr(node,'body',[])
   locations.append(str(path.relative_to(root))+':'+str(node.lineno)+' :: '+qual)
  result.append(dict(item=i,recommendation=rec,capability=cap,references=locations,problem_and_evidence=problem,verification='OFFLINE/SCRIPTED: full software suite and representative packets; saved-response projections are labelled, no new live verification.',dependencies=deps))
 return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--output',required=True);args=parser.parse_args();root=Path(args.project).resolve();out=root/args.output
 if out.exists():raise ValueError('New offline audit destination required; never overwrite historical evidence')
 out.mkdir(parents=True);project=Project(root)
 # No sockets or model/API calls anywhere in this audit, including tests.
 with offline_network_guard():
  sys.path.insert(0,str(root/'tests'));import os
  os.environ['NLTL_TEST_OUTPUT']=str(out/'software_packets');os.environ['NLTL_TEST_PROJECT']=str(root);(out/'software_packets').mkdir()
  suite=unittest.defaultTestLoader.discover(str(root/'tests'));stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);(out/'software_tests.txt').write_text(stream.getvalue());write(out/'software_summary.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),network='BLOCKED',model_calls=0,evaluation_scores_rerun=False))
  if not result.wasSuccessful():raise RuntimeError('Software controls failed; see software_tests.txt')
  saved=root/V092/'I2-004/nltl';old_request=json.loads((saved/'request_001.json').read_text());old_body=json.loads(old_request['user']);seed=(saved/'candidate_01.ttl').read_bytes();assert hashlib.sha256(seed).hexdigest()==SEED;c=Candidate(1,seed.decode(),'')
  ctx=copy.deepcopy(old_body['context']);config=project.config('configs/nltl.json');ad=load_admission(project,dict(config,admission_file='data/admissions/i2_004_research_scope.approved.json'),Schema(project),'I2-004');assert ad['valid'] and ctx['admission']==ad['context']
  # Verify every supplied historical source span against unchanged retained bytes.
  for d in ctx['source_documents']:
   raw=project.path(d['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==d['sha256'];text=raw.decode();span=d.get('selection');assert d['text']==(text[span['start']:span['end']] if span else text)
  for name in ['nltl','single_shot','offline_smoke','evaluation']:project.config('configs/'+name+'.json')
  schema=Schema(project);fs=check(c,schema,'I2-004',admission=ctx['admission']);probe_findings,probe=runtime_probe(c,schema);fs+=probe_findings
  prep=out/'prepared_continuation';prep.mkdir();(prep/'candidate_01.ttl').write_bytes(seed);write(prep/'source_schema_context.json',ctx);write(prep/'findings.json',[f.asdict() for f in fs]);write(prep/'execution_only_probe.json',probe)
  request,body=internal_packet(root,c,ctx,probe,fs,prep,config);write(prep/'review_request.json',request);(prep/'review_request.rendered.txt').write_text(request['system']+'\n\n'+request['user']);assert sha(prep/'candidate_01.ttl')==SEED
  cont=copy.deepcopy(project.config('configs/v092_review_continuation.json'));cont.update(method='offline',network_enabled=False,proposal_only=True,pipeline_version='0.10.0');cont['continuation'].update(seed_file=short(prep/'candidate_01.ttl',root),source_context=short(prep/'source_schema_context.json',root),seed_sha256=SEED,initial_generation_calls=0,max_repair_calls=1,max_total_candidates_including_seed=2,prior_issue_ids=[],dispatch_prepared_only=True,requires_separate_model_authorization=True,main_run_cli_must_reject=True);write(prep/'continuation_config.json',cont)
  write(prep/'PREPARED_UNDISPATCHED.json',dict(seed_sha256=SEED,initial_generations=0,max_repairs=1,max_total_candidates=2,max_primary_reviews=4,max_reviews_per_candidate=3,max_format_retries_per_review=1,max_retrieval_rounds=2,max_provider_calls=9,early_acceptance=True,regeneration=False,production_routes=['Runner.assess_candidate','Runner.review','repair_request','Runner.dispatch','check','runtime_probe'],transport='NONE; CaptureOnly stops before provider boundary',model_calls=0,history_failed_issues_loaded=False,prepared_only=True))
  replay=out/'saved_response_replay';replay.mkdir();replays=[]
  cases=[('v091_review',root/'outputs/audits/20261123T141223Z_V092_REVIEW_EVIDENCE/saved_review_replay/original_response_002.json'),('v091_retry',root/'outputs/audits/20261123T141223Z_V092_REVIEW_EVIDENCE/saved_review_replay/original_response_003.json'),('v092_review',saved/'response_001.json'),('v092_retry',saved/'response_002.json')]
  for label,file in cases:
   raw=json.loads(file.read_text());raw=raw if 'text' in raw else {'text':json.dumps(raw)}
   # Each saved response is replayed against the context actually supplied then,
   # not against facts only available in a later review.
   if label.startswith('v091'):
    historical=json.loads((root/'outputs/audits/20261123T141223Z_V092_REVIEW_EVIDENCE/saved_review_replay/review_request.json').read_text());hbody=json.loads(historical['user']);context=hbody['context']
   else:context=ctx
   b=copy.deepcopy(body);b['context']=copy.deepcopy(context);b['evidence_catalog']=evidence_catalog(context)
   from nltlv2.evidence import review_binding
   b.update(review_binding(c,context,[],None,b['change_manifest'],b['execution_probe']))
   adapted,receipt=adapt_response(raw,b,c);_,_,errors=validate_review({'text':json.dumps(adapted)},c,context,previous=None,changes=b['change_manifest'],prior_issues=[],request_body=b);conflicts=review_conflicts(adapted,schema,'I2-004')
   record=dict(label=label,original_path=short(file,root),original_sha256=sha(file),projection=receipt,validation_errors=errors,schema_conflicts=conflicts,workflow_usable=not errors and not conflicts,claims_are_model_interpretations=True,decision_unchanged=json.loads(raw['text']).get('decision')==adapted.get('decision'))
   write(replay/(label+'_adapted.json'),adapted);write(replay/(label+'_assessment.json'),record);replays.append(record)
  write(replay/'summary.json',replays)
  # Exact bytes, not fabricated token estimates. Same code/context comparison.
  old_retry=json.loads((saved/'request_002.json').read_text());new_retry=copy.deepcopy(request);retry_body=json.loads(new_retry['user']);retry_body['format_feedback']=dict(validation_errors=[dict(code='MISSING_OR_UNSUPPLIED_EVIDENCE_ID',path='$.issues[0].evidence_id',expected='Use a supplied E ID')],allowed_reconciliation_ids=[],failed_review_is_not_prior_state=True);new_retry['route']='review_format_retry';new_retry['user']=json.dumps(retry_body,ensure_ascii=False);write(prep/'representative_format_retry.json',new_retry)
  pairs={'saved_context_review':(old_request,request),'saved_context_retry':(old_retry,new_retry)}
  # Counterfactual old/new repair rendering on the same generic software control,
  # never an invented finding or solution applied to the saved regulatory seed.
  sample=out/'software_packets/complete_review_retry_repair_recheck';new_repair=next(json.loads(f.read_text()) for f in sorted(sample.glob('request_[0-9][0-9][0-9].json')) if json.loads(f.read_text())['route']=='targeted_repair');history=json.loads((sample/'history.json').read_text());latest=Candidate(1,(sample/'candidate_01.ttl').read_text(),'');context=json.loads((sample/'context.json').read_text());findings=[Finding(**f) for f in history[0]['findings']]
  old_module=root/V092/'snapshot/src/nltlv2/requests.py';spec=importlib.util.spec_from_file_location('nltlv2.legacy_audit_renderer',old_module);legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy);old_repair=legacy.repair_request(Project(root),context,latest,findings,history[0]['persistent_failure_summary']);old_repair.update(model=new_repair['model'],max_output_tokens=new_repair['max_output_tokens']);old_repair['system']=(root/V092/'snapshot/prompts/repair.txt').read_text();pairs['same_software_candidate_repair']=(old_repair,new_repair)
  sizes={}
  for name,(before,after) in pairs.items():
   sizes[name]=dict(before=measure(before),after=measure(after),reduction_bytes=measure(before)['rendered_bytes']-measure(after)['rendered_bytes'],same_candidate=True,scope='Renderer comparison only; not a workflow rerun or provider token measurement');sizes[name]['reduction_percent']=round(100*sizes[name]['reduction_bytes']/sizes[name]['before']['rendered_bytes'],2)
   write(out/(name+'_before.json'),before);write(out/(name+'_after.json'),after)
  write(out/'request_size_accounting.json',sizes)
  write(out/'verification.json',dict(version='0.10.0',software_tests=result.testsRun,software_success=True,config_schema_check='Source schema audit and active configs parsed',schema=schema.audit(),new_model_calls=0,new_evaluation_runs=0,prepared_seed_sha256=SEED,replays=len(replays),replay_workflow_usable=sum(r['workflow_usable'] for r in replays),size_comparisons={k:{f:v[f] for f in ['reduction_bytes','reduction_percent']} for k,v in sizes.items()},limitations='Scripted software controls and interface projections do not establish real-model interpretation quality, legal correctness or fresh workflow performance.'))
  ledger=retention_ledger(root)
  write(out/'retention_ledger.json',ledger)
  lines=['Focused source-grounded simplification — v0.10.0 — 24 November 2026','',
   'Implemented inside NLTLv2.0 only. MVP and historical evidence were preserved.',
   'Offline scripted verification; no models/APIs, evaluation-score reruns or candidate edits.',
   '', 'Control flow: identical frozen initial context/settings -> generation. Single-shot closes.',
   'NLTL: generic structural/vocabulary/type/unit/path/SPARQL/activation checks -> execution-only probe',
   '-> bounded source-grounded review/retrieval -> validated targeted repair -> complete recheck.',
   'Accept early only after checks and complete grounded review; otherwise bounded NO_VERDICT.',
   'Freeze selection and dispatch closure before separate independent evaluation.',
   '', 'Interface: local E IDs map internally to immutable content/provenance hashes. Candidate-bound',
   'Unicode character spans or inclusive line ranges are extracted server-side. Asserted source',
   'quotations remain exact. Unknown IDs/stale spans/unsupported supplied-evidence claims fail.',
   'Interpretation is still a model judgment, not proved by a citation.',
   '', 'Wire packets contain current code once, one evidence collection and concise findings/probe.',
   'Full original logs and internal hash/state maps are retained as artifacts. Retry adds only',
   'format_feedback to the same immutable packet; failed responses never become prior issues.',
   'One change-group assessment includes removal disposition instead of a nested duplicate list.',
   'Tracker implementation and stable reconciliation/regression/repetition behavior are retained.',
   '', 'Exact rendered UTF-8 bytes (system + user), not provider token estimates:']
  for name,data in sizes.items():lines.append(f"  {name}: {data['before']['rendered_bytes']:,} -> {data['after']['rendered_bytes']:,} ({data['reduction_percent']}% smaller)")
  lines+=['Review/retry use the unchanged saved seed/context. Repair uses the same generic software',
   'candidate/context/findings rendered by old and new code, not a regulatory repair or live run.',
   '',f'Verification: {result.testsRun} software controls pass with sockets blocked; active config/schema checks pass.',
   'General controls cover exact literals, IDs, stale ranges, actual validator pre-binding, path roles,',
   'orphan Meta-SHACL, immutable retries, complete repair delivery and dispatch-closure integrity.',
   '', 'Saved-response interface projections retain reasons, decisions, paths, reconciliations and',
   'uncertainty. ID/range binding and explicit numeric-operand role are labelled adaptations.',
   'Original files remain unchanged; projections earn no historical workflow credit.']
  for record in replays:
   lines.append('  '+record['label']+': '+str(len(record['validation_errors']))+' protocol failures, '+str(len(record['schema_conflicts']))+' schema conflicts; '+str(len(record['projection']['unmapped']))+' unmapped references.')
   for conflict in record['schema_conflicts']:lines.append('    '+conflict['reason']+'; proposed='+str(conflict['reviewer_issue'].get('proposed_path')))
   for error in record['validation_errors']:lines.append('    '+error['code']+' '+error['path'])
  lines+=['The later saved responses still assert a one-sided comparison concern and a material',
   'waterline-set adequacy uncertainty. These are not repaired, independently proved or given',
   'workflow credit. No candidate was patched, no known solution entered prompts and no new',
   'compliance witnesses were made. Valid REJECT/UNRESOLVED is not acceptance or repair success.',
   '', 'Remaining limitations: real-model usability remains untested for this interface; exact',
   'source quotes can still fail. Citation checks do not prove entailment/completeness. Retrieval',
   'is bounded, lexical and edition-qualified, not guaranteed complete. Static branch analysis',
   'and structural repeat detection are conservative; custom validators depend on engine context.',
   'Execution-only probes do not cover every branch or prove arithmetic/regulatory correctness.',
   'Initial complete context is not silently truncated; large single-source passages may still',
   'produce large requests. Existing local engine resource limits are not a hard process sandbox.',
   '', 'Prepared continuation: exact seed SHA '+SEED,
   'zero initial generations; <=1 repair; <=2 candidates including seed; <=4 primary reviews;',
   '<=3 reviews/candidate; <=1 format retry/review; <=2 retrieval rounds; early acceptance;',
   'no regeneration; max 9 provider calls if separately authorized later. No live executor is',
   'added. Offline preparation captures existing production review packets at a no-transport',
   'boundary. Normal run CLI rejects method=offline. Use Runner.assess_candidate/review,',
   'repair_request/dispatch and check/runtime_probe for any separately authorized continuation.',
   'Prior issues are empty; failed historical reviews are not imported as accepted state.',
   '', 'Representative complete packets:',
   'software_packets/complete_review_retry_repair_recheck/ contains synthetic full requests,',
   'responses, rendered text, original diagnostics, code versions, diffs and reconciliations.',
   'prepared_continuation/ contains full seed, source/schema, execution probe, review/retry',
   'packets, offline config and explicit PREPARED_UNDISPATCHED.json bounds.',
   'request_size_accounting.json and *_before/after.json contain complete size evidence.',
   'saved_response_replay/ preserves projections, original file hashes and every remaining failure.',
   '', 'Updated 17-item KEEP/SIMPLIFY/FIX/REMOVE ledger (all current verification offline):']
  for item in ledger:
   lines += ['',str(item['item'])+'. '+item['recommendation']+' — '+item['capability'],
    '  Exact: '+'; '.join(item['references']),
    '  Problem/evidence: '+item['problem_and_evidence'],
    '  Verification: '+item['verification'],
    '  Dependencies: '+item['dependencies']]
  (out/'REPORT.txt').write_text('\n'.join(lines)+'\n')

 print(json.dumps(dict(output=str(out),tests=result.testsRun,model_calls=0,prepared_only=True)))
if __name__=='__main__':main()
