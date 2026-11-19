from __future__ import annotations
import json
from .core import digest,finding
CATEGORIES={'RESPONSE_FORMAT_ERROR','PARSE_ERROR','CANONICAL_IDENTIFIER_ERROR','TERM_KIND_ERROR','UNIT_CONSISTENCY_ERROR','PATH_CONTRACT_ERROR','SPARQL_ERROR','SOURCE_BACKED_LOGIC_ERROR','UNRESOLVED_CONTEXT','SPARQL_STATIC_WARNING','INFRASTRUCTURE_ERROR','RESOURCE_UNCERTAIN','NUMERIC_TERM_REVIEW','PRESERVATION_CONFLICT'}
def initial_request(project,context,settings):
 return dict(route='generation',system=project.path('prompts/generator.txt').read_text(),user=json.dumps(dict(context=context,generation_settings=settings),ensure_ascii=False),settings=settings)
def repair_request(project,context,c,findings,persistent_summary=None):
 if not findings:raise ValueError('Repair requires current findings')
 if any(f.version!=c.version or f.candidate_sha256!=c.sha256 for f in findings):raise ValueError('STALE_FEEDBACK')
 payload=dict(requirement_id=context['requirement']['id'],exact_regulatory_text=context['requirement']['text'],source_clause=context['requirement']['clause'],source_documents=context['source_documents'],verification_scope=context['scope'],schema_contract_evidence={k:context[k] for k in ['schema_terms','ontology_evidence','contract','termOwners','modelPaths','unresolvedOwnership']},candidate_version=c.version,candidate_sha256=c.sha256,previous_candidate=c.code,previous_raw_response=c.raw,current_findings=[f.asdict() for f in findings],interpretation_policy='Model review findings are grounded interpretations, not independently validated facts. Resolve uncertain source/schema context explicitly. No handwritten solution or change permissions.',preserve='Preserve source obligations, not every accidental restriction in old code. Explain removals/replacements against source/schema; do not invent obligations, conversions or applicability.')
 if persistent_summary is not None:payload['persistent_failure_summary']=persistent_summary
 route='syntax_repair' if all(f.category in ['PARSE_ERROR','RESPONSE_FORMAT_ERROR'] for f in findings) else 'targeted_repair'
 return dict(route=route,system=project.path('prompts/repair.txt').read_text(),payload=payload,user=json.dumps(payload,ensure_ascii=False))
def assert_integrity(request,latest,expected_findings=None):
 if request['route'] in ['syntax_repair','targeted_repair']:
  p=request.get('payload',{});code=p.get('previous_candidate')
  if not isinstance(code,str) or not code or code!=latest.code:raise ValueError('ABSENT_STALE_OR_TRUNCATED_PREVIOUS_CODE')
  if p.get('candidate_version')!=latest.version or p.get('candidate_sha256')!=latest.sha256 or digest(code)!=latest.sha256:raise ValueError('STALE_CANDIDATE_HASH_OR_VERSION')
  if json.loads(request['user'])!=p:raise ValueError('RENDERED_REQUEST_PAYLOAD_MISMATCH')
  fs=p.get('current_findings',[])
  if expected_findings is not None and fs!=[f.asdict() for f in expected_findings]:raise ValueError('FEEDBACK_NOT_IDENTICAL_TO_LATEST_CHECK_REPORT')
  if not fs or any(f.get('version')!=latest.version or f.get('candidate_sha256')!=latest.sha256 for f in fs):raise ValueError('STALE_FEEDBACK')
  if any(k in p for k in ['validated_constraint_changes','expected_verdicts','behavioral_witnesses']):raise ValueError('LEGACY_SOLUTION_PACKET_FORBIDDEN')
  for f in fs:
   if f['category'] not in CATEGORIES or not f.get('diagnostic') or not f.get('location') or not f.get('suggestion'):raise ValueError('INCOMPLETE_FINDING')
 elif request['route']=='fresh_regeneration':raise ValueError('FRESH_REGENERATION_DISABLED')
 elif request['route'] not in ['generation','review','review_format_retry']:raise ValueError('UNKNOWN_ROUTE')
 return dict(previous_code_full=True,version=latest.version,sha256=latest.sha256,feedback_same_version=True,route=request['route'])
class ReviewerFormatError(ValueError):pass
def parse_review(response,c,context,max_issues=12,*,previous=None,changes=None,prior_issues=()):
 raw=response['text']
 if response.get('finish_reason') in ['length','max_tokens','max_output_tokens'] or response.get('status')=='incomplete':raise ReviewerFormatError('TRUNCATED_REVIEW finish_reason='+str(response.get('finish_reason')))
 try:obj=json.loads(raw)
 except Exception as e:raise ReviewerFormatError('INVALID_JSON '+str(e)) from e
 if not isinstance(obj,dict) or set(obj)!={'decision','issues','change_assessments','reconciliations','unchecked'} or obj['decision'] not in ['ACCEPT','REJECT','UNRESOLVED'] or any(not isinstance(obj[k],list) for k in ['issues','change_assessments','reconciliations','unchecked']) or len(obj['issues'])>max_issues:raise ReviewerFormatError('INVALID_REVIEW_STRUCTURE_OR_ISSUE_BOUND')
 if any(not isinstance(x,str) or not x.strip() for x in obj['unchecked']):raise ReviewerFormatError('INVALID_UNCHECKED_SCOPE')
 if bool(obj['issues'])==(obj['decision']=='ACCEPT'):raise ReviewerFormatError('DECISION_ISSUE_CONTRADICTION')
 source_texts=[d['text'] for d in context['source_documents']]
 schema_text=json.dumps({k:context[k] for k in ['schema_terms','ontology_evidence','contract','termOwners','modelPaths']},ensure_ascii=False)
 def source_quote(value):return isinstance(value,str) and bool(value.strip()) and any(value in text for text in source_texts)
 def current_quote(x):
  excerpt=x.get('candidate_excerpt');anchor=x.get('insertion_context')
  return isinstance(excerpt,str) and bool(excerpt.strip()) and excerpt in c.code or not excerpt and isinstance(anchor,str) and bool(anchor.strip()) and anchor in c.code
 out=[];ids=[]
 for x in obj['issues']:
  fields=['issue_id','category','source_clause','source_excerpt','reason','expected','suggestion','evidence_excerpt']
  if not isinstance(x,dict) or any(not isinstance(x.get(k),str) or not x[k].strip() for k in fields) or x['category'] not in ['SOURCE_BACKED_LOGIC_ERROR','UNRESOLVED_CONTEXT']:raise ReviewerFormatError('INCOMPLETE_EVIDENCED_ISSUE')
  if x['source_clause']!=context['requirement']['clause'] or not source_quote(x['source_excerpt']) or not current_quote(x):raise ReviewerFormatError('ISSUE_EVIDENCE_NOT_IN_SOURCE_OR_CANDIDATE')
  if x['evidence_excerpt'] not in schema_text and not source_quote(x['evidence_excerpt']):raise ReviewerFormatError('UNSUPPORTED_SCHEMA_EVIDENCE')
  ids.append(x['issue_id']);out.append(finding(c,x['category'],x['reason'],x.get('candidate_excerpt',''),x['expected'],json.dumps(dict(source_clause=x['source_clause'],source_excerpt=x['source_excerpt'],schema_excerpt=x['evidence_excerpt'],epistemic_status='MODEL_INTERPRETATION_NOT_INDEPENDENTLY_VERIFIED')),x['suggestion'],location='semantic reviewer excerpt' if x.get('candidate_excerpt') else 'semantic reviewer insertion context: '+x['insertion_context'],confirmed=False,diagnostic=raw,contract_id='source-review:'+context['requirement']['id'],obligation_id=x['issue_id'],check_id='semantic-issue',assessment='UNRESOLVED_CONTEXT' if x['category']=='UNRESOLVED_CONTEXT' else 'MODEL_INTERPRETATION'))
 if len(ids)!=len(set(ids)):raise ReviewerFormatError('DUPLICATE_ISSUE_ID')
 if obj['decision']=='UNRESOLVED' and not any(x['category']=='UNRESOLVED_CONTEXT' for x in obj['issues']):raise ReviewerFormatError('UNRESOLVED_DECISION_NEEDS_CONTEXT_ISSUE')
 expected_changes={x['change_id'] for x in (changes or {}).get('changes',[])};seen=[]
 for x in obj['change_assessments']:
  if not isinstance(x,dict) or x.get('disposition') not in ['SUPPORTED','REGRESSION','UNRESOLVED'] or x.get('change_id') not in expected_changes or not source_quote(x.get('source_excerpt')) or not current_quote(x) or not x.get('reason'):raise ReviewerFormatError('UNGROUNDED_CHANGE_ASSESSMENT')
  if previous is None or not isinstance(x.get('previous_excerpt'),str) or not x['previous_excerpt'] or x['previous_excerpt'] not in previous.code:raise ReviewerFormatError('CHANGE_NOT_TIED_TO_PREVIOUS_CODE')
  seen.append(x['change_id'])
  if obj['decision']=='ACCEPT' and x['disposition']!='SUPPORTED':raise ReviewerFormatError('ACCEPT_WITH_UNRESOLVED_OR_REGRESSIVE_CHANGE')
  if x['disposition']!='SUPPORTED' and not any(issue.get('change_id')==x['change_id'] for issue in obj['issues']):raise ReviewerFormatError('CHANGE_FAILURE_NEEDS_ACTIONABLE_ISSUE')
  if x['disposition']=='UNRESOLVED' and obj['decision']!='UNRESOLVED':raise ReviewerFormatError('UNRESOLVED_CHANGE_NEEDS_UNRESOLVED_DECISION')
  if obj['decision']=='ACCEPT' and x['disposition']!='SUPPORTED':raise ReviewerFormatError('ACCEPT_WITH_UNRESOLVED_OR_REGRESSIVE_CHANGE')
 if set(seen)!=expected_changes or len(seen)!=len(set(seen)):raise ReviewerFormatError('INCOMPLETE_CHANGE_REVIEW')
 expected_prior={x['issue_id'] for x in prior_issues};reconciled=[]
 for x in obj['reconciliations']:
  if not isinstance(x,dict) or x.get('issue_id') not in expected_prior or x.get('state') not in ['RESOLVED','PERSISTENT','REGRESSED','UNASSESSABLE'] or not source_quote(x.get('source_excerpt')) or not current_quote(x) or not x.get('reason'):raise ReviewerFormatError('UNGROUNDED_ISSUE_RECONCILIATION')
  reconciled.append(x['issue_id'])
  if x['state']=='RESOLVED' and x['issue_id'] in ids:raise ReviewerFormatError('RECONCILIATION_CONTRADICTION')
  if obj['decision']=='ACCEPT' and x['state']!='RESOLVED':raise ReviewerFormatError('ACCEPT_WITH_UNRESOLVED_PRIOR_ISSUE')
 if set(reconciled)!=expected_prior or len(reconciled)!=len(set(reconciled)):raise ReviewerFormatError('INCOMPLETE_PRIOR_ISSUE_RECONCILIATION')
 obj['epistemic_status']='GROUNDED_MODEL_REVIEW_NOT_INDEPENDENT_VERIFICATION'
 return obj,out

def review_conflicts(obj,schema,rid):
 _,allowed=schema.allowed_paths(rid);conflicts=[]
 for x in obj.get('issues',[]):
  prop=x.get('property');term=schema.terms.get(prop,{})
  if x.get('proposed_unit') and term.get('unitIri') and x['proposed_unit']!=term['unitIri']:conflicts.append(dict(property=prop,reviewer_issue=x,reason='Proposed unit contradicts declared representation; conversion/interpretation is not an identifier fix'))
  if x.get('proposed_datatype') and term.get('datatype') and x['proposed_datatype']!=term['datatype'].replace('xsd:','http://www.w3.org/2001/XMLSchema#'):conflicts.append(dict(property=prop,reviewer_issue=x,reason='Proposed datatype contradicts explicit schema'))
  if x.get('proposed_path') and allowed.get(prop) and tuple(x['proposed_path']) not in allowed[prop]:conflicts.append(dict(property=prop,reviewer_issue=x,reason='Proposed path contradicts explicit representation mapping'))
 return conflicts
