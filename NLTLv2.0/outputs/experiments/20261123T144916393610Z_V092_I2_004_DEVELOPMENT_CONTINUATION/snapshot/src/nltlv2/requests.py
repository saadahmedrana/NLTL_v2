from __future__ import annotations
import json
from .core import digest,finding
CATEGORIES={'RESPONSE_FORMAT_ERROR','PARSE_ERROR','CANONICAL_IDENTIFIER_ERROR','TERM_KIND_ERROR','UNIT_CONSISTENCY_ERROR','PATH_CONTRACT_ERROR','SPARQL_ERROR','SOURCE_BACKED_LOGIC_ERROR','UNRESOLVED_CONTEXT','SPARQL_STATIC_WARNING','INFRASTRUCTURE_ERROR','RESOURCE_UNCERTAIN','NUMERIC_TERM_REVIEW','PRESERVATION_CONFLICT','ACTIVATION_ERROR','ADMISSION_SCOPE_ERROR'}
def initial_request(project,context,settings):
 return dict(route='generation',system=project.path('prompts/generator.txt').read_text(),user=json.dumps(dict(context=context,generation_settings=settings),ensure_ascii=False),settings=settings)
def repair_request(project,context,c,findings,persistent_summary=None):
 if not findings:raise ValueError('Repair requires current findings')
 if any(f.version!=c.version or f.candidate_sha256!=c.sha256 for f in findings):raise ValueError('STALE_FEEDBACK')
 payload=dict(admission=context.get('admission'),requirement_id=context['requirement']['id'],exact_regulatory_text=context['requirement']['text'],source_clause=context['requirement']['clause'],source_documents=context['source_documents'],source_selection=context.get('source_selection'),unresolved_source_context=context.get('unresolvedSourceContext',[]),retrieval_evidence=context.get('retrieval_evidence',[]),retrieved_schema_evidence=context.get('retrieved_schema_evidence',[]),verification_scope=context['scope'],schema_contract_evidence={k:context[k] for k in ['schema_terms','ontology_evidence','contract','termOwners','modelPaths','unresolvedOwnership','quantityEncoding']},candidate_version=c.version,candidate_sha256=c.sha256,previous_candidate=c.code,current_findings=[f.asdict() for f in findings],interpretation_policy='Model review findings are grounded interpretations, not independently validated facts. Resolve uncertain source/schema context explicitly. No handwritten solution or change permissions.',preserve='Preserve source obligations, not every accidental restriction in old code. Explain removals/replacements against source/schema; do not invent obligations, conversions or applicability.')
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

def parse_review(response,c,context,max_issues=12,*,previous=None,changes=None,prior_issues=(),request_body=None):
 from .review_validation import validate_review
 obj,normalization,errors=validate_review(response,c,context,max_issues,previous=previous,changes=changes,prior_issues=prior_issues,request_body=request_body)
 if errors:
  first=errors[0];exception=ReviewerFormatError(first['code'],first['path'],first['expected'],first.get('observed'),first['category']);exception.errors=errors;exception.details=dict(first,validation_errors=errors);exception.args=(json.dumps(exception.details,ensure_ascii=False),);raise exception
 out=[];raw=response['text']
 for x in obj['issues']:
  out.append(finding(c,x['category'],x['reason'],x.get('candidate_excerpt',''),x['expected'],json.dumps(dict(source_clause=x['source_clause'],source_evidence_id=x['source_evidence_id'],source_excerpt=x['source_excerpt'],evidence_id=x['evidence_id'],schema_excerpt=x['evidence_excerpt'],epistemic_status='MODEL_INTERPRETATION_NOT_INDEPENDENTLY_VERIFIED')),x['suggestion'],location='semantic reviewer excerpt' if x.get('candidate_excerpt') else 'semantic reviewer insertion context: '+x['insertion_context'],confirmed=False,diagnostic=raw,contract_id='source-review:'+context['requirement']['id'],obligation_id=x['issue_id'],check_id='semantic-issue',assessment='UNRESOLVED_CONTEXT' if x['category']=='UNRESOLVED_CONTEXT' else 'MODEL_INTERPRETATION'))
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
  if x.get('proposed_path') and allowed.get(prop) and tuple(x['proposed_path']) not in allowed[prop]:conflicts.append(dict(property=prop,reviewer_issue=x,reason='Proposed path contradicts explicit representation mapping'))
 return conflicts
