from __future__ import annotations
import json
from .core import digest,finding
CATEGORIES={'RESPONSE_FORMAT_ERROR','PARSE_ERROR','CANONICAL_IDENTIFIER_ERROR','TERM_KIND_ERROR','UNIT_CONSISTENCY_ERROR','PATH_CONTRACT_ERROR','SPARQL_ERROR','SOURCE_BACKED_LOGIC_ERROR','TECHNICAL_REPRESENTATION_ERROR','UNRESOLVED_CONTEXT','SPARQL_STATIC_WARNING','INFRASTRUCTURE_ERROR','RESOURCE_UNCERTAIN','NUMERIC_TERM_REVIEW','PRESERVATION_CONFLICT','ACTIVATION_ERROR','ADMISSION_SCOPE_ERROR','SHACL_STRUCTURE_ERROR'}
def initial_request(project,context,settings):
 return dict(route='generation',system=project.path('prompts/generator.txt').read_text(),user=json.dumps(dict(context=context,generation_settings=settings),ensure_ascii=False),settings=settings)
def repair_request(project,context,c,findings,persistent_summary=None):
 if not findings:raise ValueError('Repair requires current findings')
 if any(f.version!=c.version or f.candidate_sha256!=c.sha256 for f in findings):raise ValueError('STALE_FEEDBACK')
 payload=dict(admission=context.get('admission'),requirement_id=context['requirement']['id'],exact_regulatory_text=context['requirement']['text'],source_clause=context['requirement']['clause'],source_documents=context['source_documents'],source_selection=context.get('source_selection'),unresolved_source_context=context.get('unresolvedSourceContext',[]),retrieval_evidence=context.get('retrieval_evidence',[]),retrieved_schema_evidence=context.get('retrieved_schema_evidence',[]),verification_scope=context['scope'],schema_contract_evidence={k:context[k] for k in ['schema_terms','ontology_evidence','contract','termOwners','modelPaths','unresolvedOwnership','quantityEncoding']},candidate_version=c.version,candidate_sha256=c.sha256,previous_candidate=c.code,current_findings=repair_findings(findings,c),interpretation_policy='Model review findings are grounded interpretations, not independently validated facts. Resolve uncertain source/schema context explicitly. No handwritten solution or change permissions.',preserve='Preserve source obligations, not every accidental restriction in old code. Explain removals/replacements against source/schema; do not invent obligations, conversions or applicability.')
 for key in ['exact_regulatory_text','source_clause','source_documents','source_selection','unresolved_source_context','retrieval_evidence','retrieved_schema_evidence','schema_contract_evidence','admission','verification_scope','interpretation_policy','preserve']:payload.pop(key,None)
 from .evidence import evidence_catalog,wire_catalog
 payload.update(protocol_version=2,context=compact_context(context),evidence_catalog=wire_catalog(evidence_catalog(context)),admission_sha256=digest(json.dumps(context.get('admission'),sort_keys=True)))
 if persistent_summary is not None:payload['persistent_failure_summary']={k:persistent_summary[k] for k in ['current_version','current_sha256','repeat_detection'] if k in persistent_summary}
 payload['repair_packet_sha256']=digest(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')))
 route='syntax_repair' if all(f.category in ['PARSE_ERROR','RESPONSE_FORMAT_ERROR'] for f in findings) else 'targeted_repair'
 return dict(route=route,system=project.path('prompts/repair.txt').read_text(),payload=payload,user=json.dumps(payload,ensure_ascii=False))
def assert_integrity(request,latest,expected_findings=None):
 if request['route'] in ['syntax_repair','targeted_repair']:
  p=request.get('payload',{});code=p.get('previous_candidate')
  if not isinstance(code,str) or not code or code!=latest.code:raise ValueError('ABSENT_STALE_OR_TRUNCATED_PREVIOUS_CODE')
  if p.get('candidate_version')!=latest.version or p.get('candidate_sha256')!=latest.sha256 or digest(code)!=latest.sha256:raise ValueError('STALE_CANDIDATE_HASH_OR_VERSION')
  if json.loads(request['user'])!=p:raise ValueError('RENDERED_REQUEST_PAYLOAD_MISMATCH')
  fs=p.get('current_findings',[])
  if expected_findings is not None and fs!=repair_findings(expected_findings,latest):raise ValueError('FEEDBACK_NOT_IDENTICAL_TO_LATEST_CHECK_REPORT')
  if not fs or any(f.get('version')!=latest.version or f.get('candidate_sha256')!=latest.sha256 for f in fs):raise ValueError('STALE_FEEDBACK')
  if any(k in p for k in ['validated_constraint_changes','expected_verdicts','behavioral_witnesses']):raise ValueError('LEGACY_SOLUTION_PACKET_FORBIDDEN')
  for f in fs:
   if f['category'] not in CATEGORIES or not f.get('diagnostic') or not f.get('location') or not f.get('suggestion'):raise ValueError('INCOMPLETE_FINDING')
  if p.get('protocol_version')==2:
   unsigned={k:v for k,v in p.items() if k!='repair_packet_sha256'}
   if p.get('repair_packet_sha256')!=digest(json.dumps(unsigned,sort_keys=True,ensure_ascii=False,separators=(',',':'))):raise ValueError('REPAIR_CONTEXT_INTEGRITY_FAILURE')
 elif request['route']=='fresh_regeneration':raise ValueError('FRESH_REGENERATION_DISABLED')
 elif request['route'] not in ['generation','review','review_format_retry']:raise ValueError('UNKNOWN_ROUTE')
 return dict(previous_code_full=True,version=latest.version,sha256=latest.sha256,feedback_same_version=True,route=request['route'])
from .review_protocol import ReviewerFormatError,normalize_response,reviewer_schema

def parse_review(response,c,context,max_issues=12,*,previous=None,changes=None,prior_issues=(),request_body=None):
 from .review_validation import validate_review
 obj,normalization,errors=validate_review(response,c,context,max_issues,previous=previous,changes=changes,prior_issues=prior_issues,request_body=request_body)
 if errors:
  first=errors[0];exception=ReviewerFormatError(first['code'],first['path'],first['expected'],first.get('observed'),first['category']);exception.errors=errors;exception.details=dict(first,validation_errors=errors);exception.args=(json.dumps(exception.details,ensure_ascii=False),);raise exception
 out=[];raw=response['text']
 for x in obj['issues']:
  out.append(finding(c,x['category'],x['reason'],(x.get('candidate_excerpt') or ''),x['expected'],json.dumps(dict(source_clause=x.get('source_clause'),source_evidence_id=x.get('source_evidence_id'),source_excerpt=x.get('source_excerpt'),evidence_id=x['evidence_id'],schema_excerpt=x['evidence_excerpt'],claim_basis=x.get('claim_basis'),reviewer_proposal={k:x[k] for k in ['property','proposed_path','proposed_path_role','proposed_unit','proposed_datatype','operands','representation_disposition'] if k in x},epistemic_status='MODEL_INTERPRETATION_NOT_INDEPENDENTLY_VERIFIED')),x['suggestion'],location='semantic reviewer excerpt' if x.get('candidate_excerpt') else 'semantic reviewer context (no offending code asserted)' if x['category']=='UNRESOLVED_CONTEXT' else 'semantic reviewer insertion context: '+str(x.get('insertion_context','')),confirmed=False,diagnostic=raw,contract_id='source-review:'+context['requirement']['id'],obligation_id=x['issue_id'],check_id='semantic-issue',assessment='UNRESOLVED_CONTEXT' if x['category']=='UNRESOLVED_CONTEXT' else 'MODEL_INTERPRETATION'))
 for i,entry in enumerate(obj['material_unchecked']):
  out.append(finding(c,'UNRESOLVED_CONTEXT','Material review scope remains unchecked: '+entry['scope'],'',expected='Resolve material applicability/activation/source uncertainty before acceptance',evidence=json.dumps(entry),suggestion='Resolve from supplied evidence; execution success is not regulatory correctness.',location='review unchecked['+str(i)+']',confirmed=False,diagnostic=raw,contract_id='review-scope',obligation_id=entry['scope'],check_id='material-scope',assessment='MATERIAL_REVIEW_UNCERTAINTY'))
 obj['normalization']=dict(aliases=normalization['aliases'],values_modified=False);obj['epistemic_status']='GROUNDED_MODEL_REVIEW_NOT_INDEPENDENT_VERIFICATION'
 return obj,out

def review_conflicts(obj,schema,rid):
 _,allowed=schema.allowed_paths(rid);conflicts=[]
 for x in obj.get('issues',[]):
  prop=x.get('property');term=schema.terms.get(prop,{})
  if x.get('proposed_unit') and term.get('unitIri') and x['proposed_unit']!=term['unitIri']:conflicts.append(dict(property=prop,reviewer_issue=x,reason='Proposed unit contradicts declared representation; conversion/interpretation is not an identifier fix'))
  if x.get('proposed_datatype') and term.get('datatype') and x['proposed_datatype']!=term['datatype'].replace('xsd:','http://www.w3.org/2001/XMLSchema#'):conflicts.append(dict(property=prop,reviewer_issue=x,reason='Proposed datatype contradicts explicit schema'))
  if x.get('proposed_path') and allowed.get(prop):
   proposed=tuple(x['proposed_path']);supported=set(allowed[prop]);role=x.get('proposed_path_role') or 'PROPERTY'
   if role=='NUMERIC_OPERAND' and (term.get('kind')=='QuantityProperty' or term.get('parentOrRange')==schema.quantity_profile['quantity_class']):supported={p+(schema.quantity_profile['numeric_predicate'],) for p in supported}
   if proposed not in supported:conflicts.append(dict(property=prop,reviewer_issue=x,reason='Proposed '+role+' path contradicts explicit representation mapping'))
 return conflicts


def compact_context(context):
 """Metadata only; supplied source/schema content lives once in evidence_catalog."""
 keys=['requirement','scope','source_selection','source_completeness']
 result={k:context[k] for k in keys if k in context}
 if 'requirement' in result:result['requirement']={k:v for k,v in result['requirement'].items() if k!='text'}
 return result

def concise_prior(prior):
 return [dict(issue_id=x['issue_id'],last_seen_version=x.get('last_seen_version'),last_seen_sha256=x.get('last_seen_sha256'),summary=(x.get('finding') or {}).get('message',x.get('reason','')),state='UNRESOLVED') for x in prior]

def concise_changes(changes):
 return dict(status=changes.get('status'),changes=[dict(change_id=x['change_id'],kind=x['kind'],removed_count=len(x.get('removed',[])),added_count=len(x.get('added',[])),removal_required=bool(x.get('removal_alerts'))) for x in changes.get('changes',[])])

def concise_findings(findings):
 return [dict(finding_key=f.key,category=f.category,message=f.message,location=f.location,expected=f.expected,suggestion=f.suggestion,blocking=f.blocking,assessment=f.assessment,diagnostic=f.diagnostic if f.assessment not in ['MODEL_INTERPRETATION','UNRESOLVED_CONTEXT'] else 'Raw reviewer response in artifacts',diagnostic_sha256=digest(f.diagnostic)) for f in findings]

def compact_review(body):
 out={k:body[k] for k in ['candidate_version','candidate_sha256','review_request_id','full_candidate','previous_candidate','max_issues','expected_response_schema','execution_probe','citation_format']}
 execution=dict(out['execution_probe'])
 logs=execution.pop('exact_diagnostics',{})
 execution['diagnostics']={k:dict(sha256=digest(str(v)),characters=len(str(v)),artifact_field='execution_probe.exact_diagnostics.'+k) for k,v in logs.items()}
 out['execution_probe']=execution
 from .evidence import wire_catalog
 out.update(protocol_version=2,context=compact_context(body['context']),admission_sha256=digest(json.dumps(body['context'].get('admission'),sort_keys=True)),evidence_catalog=wire_catalog(body['evidence_catalog']),change_manifest=concise_changes(body['change_manifest']),prior_issues=concise_prior(body['prior_issues']),findings=body['concise_findings'])
 out['packet_sha256']=digest(json.dumps(out,sort_keys=True,ensure_ascii=False,separators=(',',':')))
 return out

def review_base(body):return {k:v for k,v in body.items() if k!='format_feedback'}

def assert_compact_review(body,c):
 from .evidence import extract_location
 base=review_base(body);expected=base.pop('packet_sha256',None)
 if expected!=digest(json.dumps(base,sort_keys=True,ensure_ascii=False,separators=(',',':'))):raise ValueError('REVIEW_RETRY_STATE_INTEGRITY_FAILURE')
 if type(base.get('candidate_version')) is not int or base['candidate_version']!=c.version or base['candidate_sha256']!=c.sha256 or base['full_candidate']!=c.code:raise ValueError('STALE_REVIEW_CANDIDATE')
 if digest(base['full_candidate'])!=c.sha256:raise ValueError('STALE_REVIEW_CANDIDATE')
 prev=base.get('previous_candidate')
 if prev and digest(prev['full_code'])!=prev['sha256']:raise ValueError('STALE_PREVIOUS_CANDIDATE')
 return base

def repair_findings(findings,c):
 result=[]
 for f in findings:
  row=f.asdict()
  excerpt=row.pop('excerpt')
  if excerpt and excerpt in c.code:
   from .evidence import code_location
   start=c.code.index(excerpt);row['candidate_location']=code_location(c,start,start+len(excerpt))
  elif excerpt:row['identifier_excerpt']=excerpt
  if f.assessment in ['MODEL_INTERPRETATION','UNRESOLVED_CONTEXT']:
   row['diagnostic_artifact_sha256']=digest(row.pop('diagnostic'));row['diagnostic']='Grounded model interpretation; full raw response retained in artifacts.'
   try:
    support=json.loads(row['evidence']);row['evidence']={k:v for k,v in support.items() if k in ['source_evidence_id','evidence_id','epistemic_status','reviewer_proposal']}
   except (ValueError,TypeError):pass
  result.append(row)
 return result


def review_proposal_routing(obj,schema,rid,context):
 """Route failures without changing properties, paths, roles, evidence or issues.
 Only a declared path belonging to a different declared property proves a
 pairing inconsistency. Unknown mappings and actual representation conflicts
 remain blocking; this function never manufactures a corrected proposal.
 """
 _,allowed=schema.allowed_paths(rid);correctable=[];blocking=[]
 supplied=context.get('contract',{})
 bindings=schema.bindings.get(rid,{})
 evidenced=(supplied.get('kind')=='REPRESENTATION_ONLY' and supplied.get('owners')==bindings.get('owners',{}) and supplied.get('modelPaths')==bindings.get('model_paths',[]) and supplied.get('target_owner')==bindings.get('target_owner') and context.get('quantityEncoding')==schema.quantity_profile)
 for index,issue in enumerate(obj.get('issues',[])):
  base='$.issues['+str(index)+']';contradiction=issue.get('representation_disposition')=='UNRESOLVED_CONTRADICTION' or issue.get('category')=='UNRESOLVED_CONTEXT'
  if issue.get('representation_disposition')=='UNRESOLVED_CONTRADICTION':
   blocking.append(dict(code='UNRESOLVED_REPRESENTATION_CONTRADICTION',path=base,reason='Reviewer explicitly reports unresolved source/schema representation contradiction',reviewer_issue=issue))
  proposals=[(base,issue)]+[(base+'.operands['+str(i)+']',operand) for i,operand in enumerate(issue.get('operands') or [])]
  for path,proposal in proposals:
   fields=['proposed_path','proposed_unit','proposed_datatype']
   if not any(proposal.get(k) is not None for k in fields):continue
   prop=proposal.get('property');proposed=proposal.get('proposed_path');role=proposal.get('proposed_path_role') or 'PROPERTY'
   conflicts=review_conflicts({'issues':[proposal]},schema,rid)
   if not allowed.get(prop):
    blocking.append(dict(code='UNRESOLVED_PROPOSAL_MAPPING',path=path+'.property',reason='No explicit current-requirement property/path mapping; no correction inferred',property=prop,proposed_path=proposed,reviewer_issue=issue));continue
   for conflict in conflicts:
    is_path=conflict['reason'].startswith('Proposed '+role+' path contradicts')
    alternatives=[]
    if is_path and evidenced and not contradiction:
     for other in sorted(allowed):
      if other==prop or not allowed[other]:continue
      paired=dict(proposal,property=other)
      # Reuse the same validator, including quantity-tail, unit and datatype checks.
      if not review_conflicts({'issues':[paired]},schema,rid):alternatives.append(other)
    error=dict(code='INCONSISTENT_REVIEWER_PROPERTY_PATH_PAIRING' if alternatives else 'UNRESOLVED_REPRESENTATION_CONFLICT',path=path+'.proposed_path' if is_path else path,category='REVIEWER_PROPOSAL_ERROR' if alternatives else 'REPRESENTATION_CONFLICT',expected='Correct or withdraw this inconsistent proposal; explicitly pair each operand with its declared property/path/role. Do not change candidate or invent a representation.' if alternatives else 'Resolve the source/schema contradiction without overriding declared representation',observed=dict(property=prop,proposed_path=proposed,proposed_path_role=role),reason=conflict['reason'],matching_declared_properties=alternatives,issue_id=issue['issue_id'])
    (correctable if alternatives else blocking).append(error)
 # A real contradiction is never hidden behind a response-correction opportunity.
 return dict(correctable=correctable,blocking=blocking,route='CONFLICT' if blocking else 'CORRECT_RESPONSE' if correctable else 'VALID')
