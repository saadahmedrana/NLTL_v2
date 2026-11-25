from __future__ import annotations
import json
from .core import digest,finding
CATEGORIES={'RESPONSE_FORMAT_ERROR','PARSE_ERROR','CANONICAL_IDENTIFIER_ERROR','TERM_KIND_ERROR','UNIT_CONSISTENCY_ERROR','PATH_CONTRACT_ERROR','SPARQL_ERROR','SOURCE_BACKED_LOGIC_ERROR','UNRESOLVED_CONTEXT','SPARQL_STATIC_WARNING','INFRASTRUCTURE_ERROR','RESOURCE_UNCERTAIN','NUMERIC_TERM_REVIEW','PRESERVATION_CONFLICT','ACTIVATION_ERROR'}
def initial_request(project,context,settings):
 return dict(route='generation',system=project.path('prompts/generator.txt').read_text(),user=json.dumps(dict(context=context,generation_settings=settings),ensure_ascii=False),settings=settings)
def repair_request(project,context,c,findings,persistent_summary=None):
 if not findings:raise ValueError('Repair requires current findings')
 if any(f.version!=c.version or f.candidate_sha256!=c.sha256 for f in findings):raise ValueError('STALE_FEEDBACK')
 payload=dict(requirement_id=context['requirement']['id'],exact_regulatory_text=context['requirement']['text'],source_clause=context['requirement']['clause'],source_documents=context['source_documents'],source_selection=context.get('source_selection'),unresolved_source_context=context.get('unresolvedSourceContext',[]),verification_scope=context['scope'],schema_contract_evidence={k:context[k] for k in ['schema_terms','ontology_evidence','contract','termOwners','modelPaths','unresolvedOwnership','quantityEncoding']},candidate_version=c.version,candidate_sha256=c.sha256,previous_candidate=c.code,current_findings=[f.asdict() for f in findings],interpretation_policy='Model review findings are grounded interpretations, not independently validated facts. Resolve uncertain source/schema context explicitly. No handwritten solution or change permissions.',preserve='Preserve source obligations, not every accidental restriction in old code. Explain removals/replacements against source/schema; do not invent obligations, conversions or applicability.')
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
from .review_protocol import ReviewerFormatError,normalize_response,reviewer_schema

def parse_review(response,c,context,max_issues=12,*,previous=None,changes=None,prior_issues=()):
 response,normalization=normalize_response(response);obj=normalization['normalized_response'];raw=response['original_text']
 def fail(code,path,expected,observed=None,category='MALFORMED_STRUCTURE'):raise ReviewerFormatError(code,path,expected,observed,category)
 if not isinstance(obj,dict) or set(obj)!={'decision','issues','change_assessments','reconciliations','unchecked'}:fail('INVALID_REVIEW_STRUCTURE_OR_ISSUE_BOUND','$','Exactly decision, issues, change_assessments, reconciliations, unchecked')
 if obj['decision'] not in ['ACCEPT','REJECT','UNRESOLVED']:fail('INVALID_DECISION','$.decision','ACCEPT | REJECT | UNRESOLVED',obj['decision'])
 for k in ['issues','change_assessments','reconciliations','unchecked']:
  if not isinstance(obj[k],list):fail('INVALID_ARRAY','$.'+k,'Array')
 if len(obj['issues'])>max_issues:fail('ISSUE_BOUND','$.issues','At most '+str(max_issues)+' issues',len(obj['issues']))
 if bool(obj['issues'])==(obj['decision']=='ACCEPT'):fail('DECISION_ISSUE_CONTRADICTION','$.decision','ACCEPT has no issues; REJECT/UNRESOLVED need issues')
 source_texts=[d['text'] for d in context['source_documents']]
 schema_text=json.dumps({k:context.get(k) for k in ['schema_terms','ontology_evidence','contract','termOwners','modelPaths','quantityEncoding']},ensure_ascii=False)
 def source_quote(value):return isinstance(value,str) and bool(value.strip()) and any(value in text for text in source_texts)
 def current_quote(x):
  excerpt=x.get('candidate_excerpt');anchor=x.get('insertion_context')
  return isinstance(excerpt,str) and bool(excerpt.strip()) and excerpt in c.code or not excerpt and isinstance(anchor,str) and bool(anchor.strip()) and anchor in c.code
 def grounded(x,path,previous_required=False):
  if not source_quote(x.get('source_excerpt')):fail('ISSUE_EVIDENCE_NOT_IN_SOURCE_OR_CANDIDATE',path+'.source_excerpt','Verbatim substring of one supplied source passage, retaining whitespace',x.get('source_excerpt'),'INVALID_SOURCE_QUOTATION')
  if not current_quote(x):fail('ISSUE_EVIDENCE_NOT_IN_SOURCE_OR_CANDIDATE',path+'.candidate_excerpt','Verbatim current code excerpt or exact insertion_context',x.get('candidate_excerpt'),'INVALID_CANDIDATE_QUOTATION')
  if previous_required and (previous is None or not x.get('previous_excerpt') or x['previous_excerpt'] not in previous.code):fail('CHANGE_NOT_TIED_TO_PREVIOUS_CODE',path+'.previous_excerpt','Verbatim immediately previous code','', 'INVALID_PREVIOUS_QUOTATION')
  if not isinstance(x.get('reason'),str) or not x['reason'].strip():fail('MISSING_REASON',path+'.reason','Specific source/code-based reason')
 out=[];ids=[]
 for i,x in enumerate(obj['issues']):
  path='$.issues['+str(i)+']';fields=['issue_id','category','source_clause','source_excerpt','reason','expected','suggestion','evidence_excerpt']
  if not isinstance(x,dict):fail('INCOMPLETE_EVIDENCED_ISSUE',path,'Issue object')
  for k in fields:
   if not isinstance(x.get(k),str) or not x[k].strip():fail('INCOMPLETE_EVIDENCED_ISSUE',path+'.'+k,'Nonempty '+k)
  if x['category'] not in ['SOURCE_BACKED_LOGIC_ERROR','UNRESOLVED_CONTEXT']:fail('INVALID_ISSUE_CATEGORY',path+'.category','SOURCE_BACKED_LOGIC_ERROR or UNRESOLVED_CONTEXT')
  if x['source_clause']!=context['requirement']['clause']:fail('WRONG_SOURCE_CLAUSE',path+'.source_clause',context['requirement']['clause'],x['source_clause'],'INVALID_SOURCE_QUOTATION')
  grounded(x,path)
  if x['evidence_excerpt'] not in schema_text and not source_quote(x['evidence_excerpt']):fail('UNSUPPORTED_SCHEMA_EVIDENCE',path+'.evidence_excerpt','Verbatim source or supplied schema/quantity declaration quotation; no paraphrased assertions',x['evidence_excerpt'],'UNSUPPORTED_SCHEMA_ASSERTION')
  ids.append(x['issue_id']);out.append(finding(c,x['category'],x['reason'],x.get('candidate_excerpt',''),x['expected'],json.dumps(dict(source_clause=x['source_clause'],source_excerpt=x['source_excerpt'],schema_excerpt=x['evidence_excerpt'],epistemic_status='MODEL_INTERPRETATION_NOT_INDEPENDENTLY_VERIFIED')),x['suggestion'],location='semantic reviewer excerpt' if x.get('candidate_excerpt') else 'semantic reviewer insertion context: '+x['insertion_context'],confirmed=False,diagnostic=raw,contract_id='source-review:'+context['requirement']['id'],obligation_id=x['issue_id'],check_id='semantic-issue',assessment='UNRESOLVED_CONTEXT' if x['category']=='UNRESOLVED_CONTEXT' else 'MODEL_INTERPRETATION'))
 if len(ids)!=len(set(ids)):fail('DUPLICATE_ISSUE_ID','$.issues','Unique stable IDs')
 if obj['decision']=='UNRESOLVED' and not any(x['category']=='UNRESOLVED_CONTEXT' for x in obj['issues']):fail('UNRESOLVED_DECISION_NEEDS_CONTEXT_ISSUE','$.issues','An explicit UNRESOLVED_CONTEXT issue')
 expected_changes={x['change_id']:x for x in (changes or {}).get('changes',[])};seen=[]
 for i,x in enumerate(obj['change_assessments']):
  path='$.change_assessments['+str(i)+']'
  if not isinstance(x,dict) or x.get('disposition') not in ['SUPPORTED','REGRESSION','UNRESOLVED'] or x.get('change_id') not in expected_changes:fail('UNGROUNDED_CHANGE_ASSESSMENT',path,'Valid change_id and disposition')
  grounded(x,path,True);seen.append(x['change_id'])
  if obj['decision']=='ACCEPT' and x['disposition']!='SUPPORTED':fail('ACCEPT_WITH_UNRESOLVED_OR_REGRESSIVE_CHANGE',path+'.disposition','All accepted changes SUPPORTED')
  if x['disposition']!='SUPPORTED' and not any(issue.get('change_id')==x['change_id'] for issue in obj['issues']):fail('CHANGE_FAILURE_NEEDS_ACTIONABLE_ISSUE',path,'Corresponding issue/change_id')
  if x['disposition']=='UNRESOLVED' and obj['decision']!='UNRESOLVED':fail('UNRESOLVED_CHANGE_NEEDS_UNRESOLVED_DECISION',path,'UNRESOLVED decision')
  alerts={a['alert_id']:a for a in expected_changes[x['change_id']].get('removal_alerts',[])};assessed=[]
  for j,a in enumerate(x.get('removal_assessments',[])):
   apath=path+'.removal_assessments['+str(j)+']'
   if not isinstance(a,dict) or a.get('alert_id') not in alerts or a.get('disposition') not in ['SUPPORTED_REMOVAL','REPLACED','REGRESSION','UNRESOLVED']:fail('INVALID_REMOVAL_ASSESSMENT',apath,'Known alert_id, source-grounded disposition')
   grounded(a,apath,True);assessed.append(a['alert_id'])
   if obj['decision']=='ACCEPT' and a['disposition'] not in ['SUPPORTED_REMOVAL','REPLACED']:fail('ACCEPT_WITH_UNRESOLVED_OBLIGATION_LOSS',apath,'Supported removal/replacement; source uncertainty blocks acceptance')
  if set(assessed)!=set(alerts) or len(assessed)!=len(set(assessed)):fail('UNASSESSED_OBLIGATION_LOSS',path+'.removal_assessments','Explicit source-grounded assessment for every removal alert',sorted(set(alerts)-set(assessed)),'UNASSESSED_CHANGE')
 if set(seen)!=set(expected_changes) or len(seen)!=len(set(seen)):fail('INCOMPLETE_CHANGE_REVIEW','$.change_assessments','Each change ID exactly once')
 expected_prior={x['issue_id'] for x in prior_issues};reconciled=[]
 for i,x in enumerate(obj['reconciliations']):
  path='$.reconciliations['+str(i)+']'
  if not isinstance(x,dict) or x.get('issue_id') not in expected_prior or x.get('state') not in ['RESOLVED','PERSISTENT','REGRESSED','UNASSESSABLE']:fail('UNGROUNDED_ISSUE_RECONCILIATION',path,'Known prior stable issue ID/state')
  grounded(x,path);reconciled.append(x['issue_id'])
  if x['state']=='RESOLVED' and x['issue_id'] in ids:fail('RECONCILIATION_CONTRADICTION',path,'Resolved issue absent from current issues')
  if obj['decision']=='ACCEPT' and x['state']!='RESOLVED':fail('ACCEPT_WITH_UNRESOLVED_PRIOR_ISSUE',path,'All prior issues explicitly resolved')
 if set(reconciled)!=expected_prior or len(reconciled)!=len(set(reconciled)):fail('INCOMPLETE_PRIOR_ISSUE_RECONCILIATION','$.reconciliations','All prior issue IDs exactly once')
 material=[]
 for i,x in enumerate(obj['unchecked']):
  if isinstance(x,str) and x.strip():entry=dict(scope=x,material=True,reason='Legacy untyped uncertainty is conservatively material')
  elif isinstance(x,dict) and isinstance(x.get('scope'),str) and x['scope'].strip() and type(x.get('material')) is bool and isinstance(x.get('reason'),str) and x['reason'].strip():entry=x
  else:fail('INVALID_UNCHECKED_SCOPE','$.unchecked['+str(i)+']','{scope: string, material: boolean, reason: string}')
  if entry['material']:
   material.append(entry);out.append(finding(c,'UNRESOLVED_CONTEXT','Material review scope remains unchecked: '+entry['scope'],'',expected='Resolve material applicability/activation/source uncertainty before acceptance',evidence=json.dumps(entry),suggestion='Resolve this uncertainty from source/schema; do not invent targeting or treat ACCEPT as proof.',location='review unchecked['+str(i)+']',confirmed=False,diagnostic=raw,contract_id='review-scope',obligation_id=entry['scope'],check_id='material-scope',assessment='MATERIAL_REVIEW_UNCERTAINTY'))
 obj['normalization']=dict(aliases=normalization['aliases'],values_modified=False);obj['material_unchecked']=material;obj['epistemic_status']='GROUNDED_MODEL_REVIEW_NOT_INDEPENDENT_VERIFICATION'
 return obj,out

def review_conflicts(obj,schema,rid):
 _,allowed=schema.allowed_paths(rid);conflicts=[]
 for x in obj.get('issues',[]):
  prop=x.get('property');term=schema.terms.get(prop,{})
  if x.get('proposed_unit') and term.get('unitIri') and x['proposed_unit']!=term['unitIri']:conflicts.append(dict(property=prop,reviewer_issue=x,reason='Proposed unit contradicts declared representation; conversion/interpretation is not an identifier fix'))
  if x.get('proposed_datatype') and term.get('datatype') and x['proposed_datatype']!=term['datatype'].replace('xsd:','http://www.w3.org/2001/XMLSchema#'):conflicts.append(dict(property=prop,reviewer_issue=x,reason='Proposed datatype contradicts explicit schema'))
  if x.get('proposed_path') and allowed.get(prop) and tuple(x['proposed_path']) not in allowed[prop]:conflicts.append(dict(property=prop,reviewer_issue=x,reason='Proposed path contradicts explicit representation mapping'))
 return conflicts
