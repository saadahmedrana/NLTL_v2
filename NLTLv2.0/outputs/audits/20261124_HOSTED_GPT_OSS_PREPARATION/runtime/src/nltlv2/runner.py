from __future__ import annotations
import json,time,copy,hashlib
from .core import GenerationProject,Candidate,finding,normalize,WrapperError,write
from .schema import Schema
from .admission import load_admission,blocked_result,target_findings
from .checks import check,runtime_probe
from .change_review import manifest
from .tracking import Tracker
from .context_resolution import Resolver
from .review_protocol import normalize_response,response_format,reviewer_schema
from .prompt_accounting import measure
from .evidence import evidence_catalog,review_binding,assert_review_packet,probe_summary,CITATION_FORMAT
from .requests import compact_review,review_base,concise_findings,review_proposal_routing
from .requests import initial_request,repair_request,assert_integrity,parse_review,ReviewerFormatError,review_conflicts
class Runner:
 def __init__(self,project,config,transport,output):
  self.p=GenerationProject(project.root);self.cfg=copy.deepcopy(config);self.transport=transport;self.output=output;self.schema=Schema(self.p);self.sequence=0;self.latest_findings=();self.calls=[];self.response_metrics=[];self.input_hashes={};self.resolver=Resolver(self.schema,self.cfg);self.controller_transitions=[];self.execution_summaries={};self.active_review_body=None
  if config.get('seed_candidate') or config.get('fresh_regeneration'):raise ValueError('LEGACY_MODE_FORBIDDEN')
  if config['method']=='NLTL' and not config.get('semantic_review'):raise ValueError('SOURCE_REVIEW_REQUIRED')
 def verify_inputs(self):
  for name,sha in self.input_hashes.items():
   if hashlib.sha256(self.p.path(name).read_bytes()).hexdigest()!=sha:raise ValueError('SOURCE_INPUT_INTEGRITY_FAILURE '+name)
 def dispatch(self,request,latest=None):
  limit=self.cfg.get('continuation',{}).get('max_provider_calls')
  if limit is not None:
   if type(limit) is not int or limit<1:raise ValueError('INVALID_PROVIDER_CALL_CAP')
   if len(self.calls)>=limit:raise RuntimeError('PROVIDER_CALL_LIMIT_EXHAUSTED')
  self.verify_inputs()
  body=json.loads(request['user']);body=body.get('original_request',body)
  supplied=body.get('context',{}).get('admission') if request['route'] in ['generation','review','review_format_retry'] else body.get('admission')
  if body.get('protocol_version')==2:
   if body.get('admission_sha256')!=hashlib.sha256(json.dumps(self.admission_context,sort_keys=True).encode()).hexdigest():raise ValueError('ADMISSION_REQUEST_INTEGRITY_FAILURE')
  elif supplied!=self.admission_context:raise ValueError('ADMISSION_REQUEST_INTEGRITY_FAILURE')
  self.sequence+=1;request=dict(request,model=self.cfg['model'],max_output_tokens=self.cfg['review_max_tokens'] if request['route'].startswith('review') else self.cfg['generation_max_tokens'])
  if latest is not None:
   if (self.output/f'candidate_{latest.version:02d}.ttl').read_text()!=latest.code:raise ValueError('PRECEDING_CANDIDATE_ARTIFACT_STALE')
   if request['route'].endswith('repair'):write(self.output/f'request_{self.sequence:03d}_integrity.json',assert_integrity(request,latest,self.latest_findings))
   if request['route'].startswith('review'):
    data=json.loads(request['user']);data=data.get('original_request',data)
    if review_base(data)!=self.active_review_body:raise ValueError('REVIEW_RETRY_STATE_INTEGRITY_FAILURE')
    assert_review_packet(data,latest)
    if data['candidate_version']!=latest.version or data['candidate_sha256']!=latest.sha256 or data['full_candidate']!=latest.code:raise ValueError('STALE_REVIEW_CANDIDATE')
  write(self.output/f'request_{self.sequence:03d}_sizes.json',measure(request));write(self.output/f'request_{self.sequence:03d}.json',request);(self.output/f'request_{self.sequence:03d}.rendered.txt').write_text(request['system']+'\n\n--- USER ---\n'+request['user']);self.calls.append(request)
  response=self.transport.dispatch(request,latest,self.latest_findings);write(self.output/f'response_{self.sequence:03d}.json',response)
  self.response_metrics.append(dict(sequence=self.sequence,route=request['route'],usage=response.get('usage',{}),elapsed_seconds=response.get('elapsed_seconds',0)));return response
 def review(self,c,context,previous,changes,tracker,warnings,prior_override=None):
  self.review_failure_outcome='REVIEWER_FORMAT_FAILURE';self.review_blocking_conflicts=[];proposal_correction_seen=False
  prior=copy.deepcopy(tracker.prior_semantic_issues() if prior_override is None else prior_override);body=dict(context=context,candidate_version=c.version,candidate_sha256=c.sha256,full_candidate=c.code,previous_candidate=None if previous is None else dict(version=previous.version,sha256=previous.sha256,full_code=previous.code),change_manifest=changes,prior_issues=prior,static_warnings=[f.asdict() for f in warnings if not f.blocking],deterministic_findings=[dict(f.asdict(),finding_key=f.key) for f in warnings],acceptance_blockers=[dict(f.asdict(),finding_key=f.key) for f in warnings if f.blocking],max_issues=self.cfg['review_max_issues'],expected_response_schema=reviewer_schema(self.cfg['review_max_issues']))
  execution=self.execution_summaries.get(c.version,probe_summary(c))
  body.update(protocol_version=2,concise_findings=concise_findings(warnings),**review_binding(c,context,prior,previous,changes,execution),execution_probe=copy.deepcopy(execution),evidence_catalog=evidence_catalog(context,execution),citation_format=CITATION_FORMAT)
  wire=compact_review(body);self.active_review_body=copy.deepcopy(wire);assert_review_packet(wire,c)
  write(self.output/f'review_state_{self.sequence+1:03d}.json',body)
  write(self.output/f'review_packet_{self.sequence+1:03d}_evidence.json',body['evidence_catalog'])
  request=dict(route='review',system=self.p.path('prompts/reviewer.txt').read_text(),user=json.dumps(wire,ensure_ascii=False))
  fmt=response_format(self.cfg)
  if fmt:request['response_format']=fmt
  for retry in range(self.cfg['review_format_retries']+1):
   response=self.dispatch(request,c)
   try:
    _,normalization=normalize_response(response);write(self.output/f'reviewer_normalized_{self.sequence:03d}.json',{k:v for k,v in normalization.items() if k!='raw_text'})
    obj,fs=parse_review(response,c,context,self.cfg['review_max_issues'],previous=previous,changes=changes,prior_issues=prior,request_body=body)
    routing=review_proposal_routing(obj,self.schema,context['requirement']['id'],context)
    write(self.output/f'reviewer_proposal_validation_{self.sequence:03d}.json',routing)
    if routing['blocking']:
     self.review_blocking_conflicts=routing['blocking'];return None,[],None
    if routing['correctable']:
     errors=routing['correctable'];first=errors[0];e=ReviewerFormatError(first['code'],first['path'],first['expected'],first['observed'],first['category']);e.errors=errors;e.details=dict(first,validation_errors=errors);raise e
    return obj,fs,None
   except ReviewerFormatError as e:
    errors=getattr(e,'errors',[e.details]);proposal=any(x.get('category')=='REVIEWER_PROPOSAL_ERROR' for x in errors);proposal_correction_seen|=proposal
    integrity=any(x.get('category')=='REQUEST_VERSION_BINDING' or x.get('code','').startswith('STALE_') or 'INTEGRITY' in x.get('code','') for x in errors)
    outcome='REQUEST_INTEGRITY_FAILURE' if integrity else 'REVIEWER_PROPOSAL_CORRECTION_EXHAUSTED' if proposal_correction_seen else 'REVIEWER_FORMAT_FAILURE'
    write(self.output/f'reviewer_format_failure_{self.sequence:03d}.json',dict(error=str(e),error_details=e.details,validation_errors=errors,original_prior_issues=prior,raw_response=response,candidate_version=c.version,sha256=c.sha256,not_regulatory_rejection=True,correction_kind='PROPOSAL' if proposal else 'FORMAT',terminal_integrity=integrity,response_correction_index=retry,outcome_if_terminal=outcome))
    if integrity or retry==self.cfg['review_format_retries']:
     self.review_failure_outcome=outcome;return None,[],str(e)
    feedback=dict(validation_errors=errors,allowed_reconciliation_ids=[x['issue_id'] for x in prior],failed_review_is_not_prior_state=True,correction_kind='PROPOSAL' if proposal else 'FORMAT',shared_response_correction_allowance=True,instruction='Correct every error or withdraw an inconsistent issue. Pair each comparison operand explicitly using supplied representation evidence. Keep the SAME candidate, evidence, request binding and ORIGINAL prior issues; rejected output creates NO accepted issues or repair authorization. Return one complete response. Do not rewrite candidate code, relabel properties or invent paths to bypass validation. Full raw responses remain artifacts.')
    retry_body=copy.deepcopy(wire);retry_body['format_feedback']=feedback
    request=dict(request,route='review_format_retry',user=json.dumps(retry_body,ensure_ascii=False))

 def transition(self,c,state,**details):
  self.controller_transitions.append(dict(state=state,candidate_version=c.version,candidate_sha256=c.sha256,**details));write(self.output/'controller_transitions.json',self.controller_transitions)
 def retrieve_context(self,c,context,requests,rid):
  self.transition(c,'RETRIEVE_CONTEXT',requests=requests)
  context,event=self.resolver.resolve(context,requests,rid);self.input_hashes.update(self.resolver.input_hashes);write(self.output/'retrieved_input_hashes.json',self.resolver.input_hashes)
  write(self.output/f'context_retrieval_{len(self.resolver.events):02d}_{len(self.controller_transitions):02d}.json',event);write(self.output/'resolved_context.json',context);write(self.output/'retrieval_ledger.json',self.resolver.events)
  self.transition(c,event['status'],novel=event['novel'])
  return context,event
 def assess_candidate(self,c,context,previous,changes,tracker,findings,rid):
  base=list(findings);self.transition(c,'CHECK_COMPLETE',blocking=[f.key for f in base if f.blocking]);policy=self.resolver.policy
  hard=[f for f in base if f.blocking and f.category not in ['ACTIVATION_ERROR','UNRESOLVED_CONTEXT']]
  if hard:return context,base,None,None,[],'CODE_FAILURE'
  context_blockers=[f for f in base if f.blocking]
  if context_blockers or context.get('unresolvedSourceContext'):
   context,_=self.retrieve_context(c,context,self.resolver.default_requests(context,c),rid)
  prior=tracker.prior_semantic_issues();obj=None;semantic=[];error=None;conflicts=[]
  for round_index in range(policy['max_reviews_per_candidate']):
   if sum(x['route']=='review' for x in self.calls)>=policy['max_reviews_per_run']:
    self.transition(c,'REVIEW_LIMIT_EXHAUSTED');return context,base+semantic,obj,error,conflicts,'CONTEXT_LIMIT_EXHAUSTED'
   self.transition(c,'REVIEW',review_round=round_index+1,code_unchanged=True)
   obj,semantic,error=self.review(c,context,previous,changes,tracker,base,prior_override=prior)
   if error:
    self.transition(c,self.review_failure_outcome);return context,base,None,error,[],self.review_failure_outcome
   conflicts=self.review_blocking_conflicts
   if conflicts:self.transition(c,'CONFLICT');return context,base,None,None,conflicts,'CONFLICT'
   requests=obj.get('evidence_requests',[])
   pending=obj['decision'] in ['REQUEST_EVIDENCE','UNRESOLVED'] or bool(obj.get('material_unchecked'))
   if requests or pending:
    context,event=self.retrieve_context(c,context,requests or self.resolver.default_requests(context,c),rid)
    if not event['novel']:
     stop=event['status'] if event['status'] in ['CONTEXT_LIMIT_EXHAUSTED','REPEATED_EVIDENCE_REQUEST'] else 'UNRESOLVED_CONTEXT'
     if self.controller_transitions[-1]['state']!=stop:self.transition(c,stop)
     return context,base+semantic,obj,None,[],stop
    combined={x['issue_id']:x for x in prior}
    for issue in obj.get('issues',[]):combined[issue['issue_id']]=issue
    prior=list(combined.values());continue
   if obj['decision']=='ACCEPT':
    status='UNRESOLVED_CONTEXT' if context_blockers else 'ACCEPTED';self.transition(c,status,reason='Static blockers cannot be erased by reviewer ACCEPT' if context_blockers else 'Checks plus grounded review')
    return context,base+semantic,obj,None,[],status
   if context_blockers:
    assessments={x['finding_key']:x for x in obj.get('context_assessments',[])}
    repairable=all(assessments.get(f.key,{}).get('disposition')=='REPAIRABLE_CODE' for f in context_blockers) and not any(f.category=='UNRESOLVED_CONTEXT' for f in semantic)
    if not repairable:self.transition(c,'UNRESOLVED_CONTEXT',reason='Missing information/unsupported activation cannot be changed by assumption');return context,base+semantic,obj,None,[],'UNRESOLVED_CONTEXT'
   self.transition(c,'REPAIR_PROPOSED',assessment='Source-grounded model interpretation, not verified authorization; code remains unchanged until a bounded repair call')
   return context,base+semantic,obj,None,[],'REJECTED'
  self.transition(c,'REVIEW_LIMIT_EXHAUSTED');return context,base+semantic,obj,error,conflicts,'CONTEXT_LIMIT_EXHAUSTED'
 def run(self,rid,*,shared_start=None):
  admission=load_admission(self.p,self.cfg,self.schema,rid);write(self.output/'admission_validation.json',admission)
  if not admission['valid']:
   result=blocked_result(self.cfg,rid,admission);write(self.output/'run.json',result);return result
  self.admission_context=copy.deepcopy(admission['context'])
  context=self.schema.context(rid);context['admission']=copy.deepcopy(self.admission_context);context['scope']+=' External population/date eligibility and edition selection are supplied by caller admission, not independently inferred from RDF. Conditions within the represented requirement remain in scope; activation and query correctness are separate obligations.';write(self.output/'context.json',context);write(self.output/'source_selection_manifest.json',self.schema.source_manifests[rid])
  files=['schema/Schema_for_NLTL.ttl','schema/term_registry.json','schema/representation_bindings.json','schema/locked_representation_context.jsonld','data/requirements/requirements.json','data/requirements/source_catalog.json','prompts/generator.txt','prompts/reviewer.txt','prompts/repair.txt']+[d['file'] for d in context['source_documents']]
  self.input_hashes={name:hashlib.sha256(self.p.path(name).read_bytes()).hexdigest() for name in files};self.input_hashes.update(admission['input_hashes']);write(self.output/'source_input_hashes.json',self.input_hashes)
  settings={k:self.cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']};request=initial_request(self.p,context,settings);maximum=1 if self.cfg['method']=='Single-shot' else self.cfg['maximum_candidate_attempts']
  start=time.monotonic();history=[];old=None;tracker=Tracker();operational=None;status='ATTEMPT_LIMIT_EXHAUSTED'
  for attempt in range(1,maximum+1):
   attempt_start=time.monotonic();metrics_start=len(self.response_metrics)
   try:
    if attempt==1 and shared_start is not None:
     expected=dict(request,model=self.cfg['model'],max_output_tokens=self.cfg['generation_max_tokens'])
     if shared_start['request']!=expected:raise ValueError('SHARED_START_REQUEST_INTEGRITY_FAILURE')
     response=copy.deepcopy(shared_start['response'])
     if hashlib.sha256(json.dumps(response,sort_keys=True).encode()).hexdigest()!=shared_start['response_sha256']:raise ValueError('SHARED_START_RESPONSE_INTEGRITY_FAILURE')
     write(self.output/'shared_start.json',dict(request=expected,response=response,response_sha256=shared_start['response_sha256'],physical_call=False))
    else:response=self.dispatch(request,old)
    raw=response['text'];fmt=None;normalization=None
    if response.get('status')=='incomplete' or response.get('finish_reason') in ['length','max_tokens','max_output_tokens']:fmt='Provider output incomplete'
    try:code,normalization=normalize(raw)
    except WrapperError as e:code=raw;fmt=str(e)
    c=Candidate(attempt,code,raw);(self.output/f'candidate_{attempt:02d}.ttl').write_text(code);write(self.output/f'candidate_{attempt:02d}.json',dict(version=attempt,sha256=c.sha256,normalization=normalization,origin='RESPONSE'))
    if self.cfg['method']=='Single-shot':
     status='SINGLE_SHOT_COMPLETE';history.append(dict(attempt=attempt,version=attempt,sha256=c.sha256,accepted=None,status='FORMAT_ERROR' if fmt else 'ORIGINAL_RESPONSE',response_format_error=fmt,findings=[],elapsed_seconds=time.monotonic()-attempt_start,request_metrics=self.response_metrics[metrics_start:]));write(self.output/'history.json',history);break
    changes=manifest(old,c) if old else dict(status='INITIAL_CANDIDATE',changes=[])
    write(self.output/f'change_manifest_{attempt:02d}.json',changes)
    if old:(self.output/f'diff_{attempt-1:02d}_{attempt:02d}.patch').write_text(changes['diff'])
    check_start=time.monotonic();fs=[finding(c,'RESPONSE_FORMAT_ERROR','Missing or ambiguous wrapper',raw,expected='<BEGIN_SHACL> ... <END_SHACL>',evidence='Generic output format',suggestion='Return one full unambiguous SHACL block.',diagnostic=fmt)] if fmt else check(c,self.schema,rid,admission=self.admission_context)
    self.execution_summaries[c.version]=probe_summary(c,reason='Blocked by current format/static checks; no execution occurred')
    parsed=not fmt and not any(f.category=='PARSE_ERROR' for f in fs);runtime_complete=False
    if not any(f.blocking for f in fs):
     execution,probe=runtime_probe(c,self.schema);self.execution_summaries[c.version]=probe_summary(c,probe);fs+=execution;runtime_complete=not execution;write(self.output/f'runtime_probe_{attempt:02d}.json',probe)
    technical=dict(candidate_version=c.version,candidate_sha256=c.sha256,qualifies=not fmt and runtime_complete and not any(f.blocking and f.category!='UNRESOLVED_CONTEXT' for f in fs),runtime_complete=runtime_complete,findings=[f.asdict() for f in fs],check_seconds=time.monotonic()-check_start)
    write(self.output/f'technical_{attempt:02d}.json',technical)
    check_seconds=time.monotonic()-check_start
    context,fs,obj,review_error,conflicts,controller_status=self.assess_candidate(c,context,old,changes,tracker,fs,rid)
    reconciled,persistent=tracker.observe(c,fs,static_complete=parsed,review=obj,runtime_complete=runtime_complete)
    accepted=not any(f.blocking for f in fs) and not review_error and not conflicts and obj is not None and obj['decision']=='ACCEPT' and controller_status=='ACCEPTED'
    resource=any(f.assessment=='RESOURCE_UNCERTAIN' for f in fs);infra=any(f.assessment=='INFRASTRUCTURE_OR_UNKNOWN' for f in fs)
    status='ACCEPTED' if accepted else 'RESOURCE_ATTRIBUTION_UNCERTAIN' if resource else 'INFRASTRUCTURE_FAILURE' if infra else controller_status if review_error else 'CONFLICT' if conflicts else controller_status if controller_status in ['UNRESOLVED_CONTEXT','CONTEXT_LIMIT_EXHAUSTED','REPEATED_EVIDENCE_REQUEST'] else 'REJECTED'
    stagnation=tracker.stagnation_stop(self.cfg.get('stagnation',{})) if not accepted else None
    if stagnation and status=='REJECTED':status='STAGNATION_STOP'
    row=dict(technical=technical,attempt=attempt,version=attempt,sha256=c.sha256,status=status,accepted=accepted,findings=[f.asdict() for f in fs],review=obj,reviewer_format_failure=review_error,conflicts=conflicts,changes=reconciled,structural_change_manifest=changes,persistent_failure_summary=persistent,elapsed_seconds=time.monotonic()-attempt_start,deterministic_check_seconds=check_seconds,request_metrics=self.response_metrics[metrics_start:],acceptance_scope='Static/execution checks and grounded model review only. No independent regulatory correctness certification; no behavioral gold or expected verdict was consulted.')
    history.append(row);write(self.output/'history.json',history);write(self.output/f'findings_{attempt:02d}.json',row['findings']);write(self.output/f'reconciliation_{attempt:02d}.json',reconciled);self.latest_findings=tuple(fs)
    if accepted or status in ['RESOURCE_ATTRIBUTION_UNCERTAIN','INFRASTRUCTURE_FAILURE','REVIEWER_FORMAT_FAILURE','REVIEWER_PROPOSAL_CORRECTION_EXHAUSTED','REQUEST_INTEGRITY_FAILURE','CONFLICT','UNRESOLVED_CONTEXT','CONTEXT_LIMIT_EXHAUSTED','REPEATED_EVIDENCE_REQUEST','STAGNATION_STOP']:break
    old=c
    if attempt<maximum:self.transition(c,'REPAIR_REQUEST_READY',latest_code_complete=True)
    if attempt<maximum:request=repair_request(self.p,context,c,fs,persistent_summary=persistent)
    status='ATTEMPT_LIMIT_EXHAUSTED'
   except Exception as e:
    text=str(e);integrity=any(w in text for w in ['STALE','INTEGRITY','ABSENT','FEEDBACK','TRUNCATED_PREVIOUS','RENDERED_REQUEST'])
    status='PROVIDER_CALL_LIMIT_EXHAUSTED' if text=='PROVIDER_CALL_LIMIT_EXHAUSTED' else 'REQUEST_INTEGRITY_FAILURE' if integrity else 'RESOURCE_ATTRIBUTION_UNCERTAIN' if isinstance(e,(TimeoutError,MemoryError,RecursionError)) or 'timeout' in type(e).__name__.lower() else 'INFRASTRUCTURE_FAILURE';operational=dict(status=status,type=type(e).__name__,diagnostic=text,attempt=attempt,no_automatic_retry=True);write(self.output/'operational_failure.json',operational);break
  try:self.verify_inputs()
  except Exception as e:
   status='REQUEST_INTEGRITY_FAILURE';operational=dict(status=status,diagnostic=str(e),no_automatic_retry=True);write(self.output/'operational_failure.json',operational)
  result=dict(version='0.11.0',admission=dict(status=admission['status'],admission_id=self.admission_context['declaration']['admission_id'],declaration_sha256=self.admission_context['declaration_sha256'],eligibility_independently_certified=False),run_label='SOURCE_GROUNDED_LIVE' if getattr(self.transport,'is_live',False) else 'OFFLINE_SCRIPTED_SOFTWARE_TEST',provider_calls=len(self.calls) if getattr(self.transport,'is_live',False) else 0,method=self.cfg['method'],requirement_id=rid,status=status,complete_verification=False,candidate_attempts=len(history),dispatch_attempts=len(self.calls),generation_calls=sum(r['route']=='generation' for r in self.calls),repair_calls=sum(r['route'].endswith('repair') for r in self.calls),auxiliary_format_retries=sum(r['route']=='review_format_retry' for r in self.calls),accepted_version=next((h['version'] for h in history if h['accepted']),None),evaluation_candidate=next((h['version'] for h in history if h['accepted']),1 if self.cfg['method']=='Single-shot' and history and history[0]['status']!='FORMAT_ERROR' else None),elapsed_seconds=time.monotonic()-start,history=history,operational_failure=operational,exhaustion_policy='No accepted NLTL candidate means NO_VERDICT; rejected candidates remain diagnostics only.',interpretation_policy='Model conclusions are not independently verified facts.',behavioral_gold_consulted=False)
  if self.cfg.get('delivery_policy')=='latest_technical':
   from .delivery import finalize
   result['delivery']=finalize(self.output,history,status)
   result['accepted_only_evaluation_candidate']=result['evaluation_candidate']
   result['evaluation_candidate']=result['delivery']['version']
   result['exhaustion_policy']='Latest technically qualifying candidate; ACCEPTED requires unchanged grounded acceptance. UNVERIFIED is not correctness approval.'
  result['shared_start']=shared_start is not None
  write(self.output/'run.json',result);return result
