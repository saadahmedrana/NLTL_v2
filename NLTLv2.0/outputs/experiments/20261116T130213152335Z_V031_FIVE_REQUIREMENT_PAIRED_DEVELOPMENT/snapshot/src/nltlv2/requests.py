from __future__ import annotations
import dataclasses,json
from .core import digest,load,finding,Candidate
CATEGORIES={'RESPONSE_FORMAT_ERROR','PARSE_ERROR','CANONICAL_IDENTIFIER_ERROR','TERM_KIND_ERROR','UNIT_CONSISTENCY_ERROR','PATH_CONTRACT_ERROR','SPARQL_ERROR','SOURCE_BACKED_LOGIC_ERROR','UNRESOLVED_CONTEXT'}
def initial_request(project,context,settings):
 return dict(route='generation',system=project.path('prompts/generator.txt').read_text(),user=json.dumps(dict(context=context,generation_settings=settings),ensure_ascii=False),settings=settings)
def repair_request(project,context,c,findings):
 if not findings:raise ValueError('Repair requires current findings')
 for f in findings:
  if f.version!=c.version or f.candidate_sha256!=c.sha256:raise ValueError('STALE_FEEDBACK')
 payload=dict(requirement_id=context['requirement']['id'],exact_regulatory_text=context['requirement']['text'],source_clause=context['requirement']['clause'],verification_scope=context['scope'],schema_contract_evidence=dict(schema_terms=context['schema_terms'],ontology_evidence=context.get('ontology_evidence',[]),unresolvedSourceContext=context.get('unresolvedSourceContext',[]),contract=context['contract'],termOwners=context['termOwners'],modelPaths=context['modelPaths']),candidate_version=c.version,candidate_sha256=c.sha256,previous_candidate=c.code,previous_raw_response=c.raw,current_findings=[f.asdict() for f in findings],preserve='Preserve all unrelated regulatory obligations, thresholds and applicability.')
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
  for f in fs:
   if f['category'] not in CATEGORIES or not f.get('diagnostic') or not f.get('location') or not f.get('suggestion'):raise ValueError('INCOMPLETE_FINDING')
 elif request['route']=='fresh_regeneration':raise ValueError('FRESH_REGENERATION_DISABLED')
 elif request['route'] not in ['generation','review','review_format_retry']:raise ValueError('UNKNOWN_ROUTE')
 return dict(previous_code_full=True,version=latest.version,sha256=latest.sha256,feedback_same_version=True,route=request['route'])
class ReviewerFormatError(ValueError):pass
def parse_review(response,c,context,max_issues=12):
 raw=response['text'];finish=response.get('finish_reason');status=response.get('status')
 if finish in ['length','max_tokens','max_output_tokens'] or status=='incomplete':raise ReviewerFormatError('TRUNCATED_REVIEW finish_reason='+str(finish)+' status='+str(status))
 try:obj=json.loads(raw)
 except Exception as e:raise ReviewerFormatError('INVALID_JSON '+str(e)) from e
 if not isinstance(obj,dict) or set(obj)-{'decision','issues'} or obj.get('decision') not in ['ACCEPT','REJECT','UNRESOLVED'] or not isinstance(obj.get('issues'),list) or len(obj['issues'])>max_issues:raise ReviewerFormatError('INVALID_REVIEW_STRUCTURE_OR_ISSUE_BOUND')
 if bool(obj['issues'])==(obj['decision']=='ACCEPT'):raise ReviewerFormatError('DECISION_ISSUE_CONTRADICTION')
 out=[];contracts=json.dumps({k:context[k] for k in ['contract','termOwners','modelPaths','schema_terms','ontology_evidence']},ensure_ascii=False)
 for x in obj['issues']:
  fields=['category','source_clause','source_excerpt','candidate_excerpt','reason','expected','suggestion','evidence_excerpt']
  if not isinstance(x,dict) or any(not isinstance(x.get(k),str) or not x[k].strip() for k in fields) or x['category'] not in ['SOURCE_BACKED_LOGIC_ERROR','UNRESOLVED_CONTEXT']:raise ReviewerFormatError('INCOMPLETE_EVIDENCED_ISSUE')
  if x['source_clause']!=context['requirement']['clause'] or x['source_excerpt'] not in context['requirement']['text'] or x['candidate_excerpt'] not in c.code:raise ReviewerFormatError('ISSUE_EVIDENCE_NOT_IN_SOURCE_OR_CANDIDATE')
  if x['evidence_excerpt'] not in contracts and x['evidence_excerpt'] not in context['requirement']['text']:raise ReviewerFormatError('UNSUPPORTED_SCHEMA_EVIDENCE')
  out.append(finding(c,x['category'],x['reason'],x['candidate_excerpt'],x['expected'],json.dumps(dict(source_clause=x['source_clause'],source_excerpt=x['source_excerpt'],schema_excerpt=x['evidence_excerpt'])),x['suggestion'],location='semantic reviewer excerpt',confirmed=x['category']!='UNRESOLVED_CONTEXT',diagnostic=raw))
 return obj,out

def review_conflicts(obj,schema,rid):
 root,allowed=schema.allowed_paths(rid);conflicts=[]
 for x in obj.get('issues',[]):
  prop=x.get('property');proposed=x.get('proposed_path')
  term=schema.terms.get(prop,{})
  if x.get('proposed_unit') and term.get('unitIri') and x['proposed_unit']!=term['unitIri']:conflicts.append(dict(property=prop,proposed_unit=x['proposed_unit'],contract_unit=term['unitIri'],reviewer_issue=x,disposition='STOP_CONTRADICTORY_REPAIR; unit conversion/contract adjudication required'))
  if x.get('proposed_datatype') and term.get('datatype') and x['proposed_datatype']!=term['datatype'].replace('xsd:','http://www.w3.org/2001/XMLSchema#'):conflicts.append(dict(property=prop,reviewer_issue=x,disposition='STOP_CONTRADICTORY_REPAIR; explicit datatype must not be overridden'))
  if prop in allowed and allowed[prop] and proposed and tuple(proposed) not in allowed[prop]:conflicts.append(dict(property=prop,proposed=proposed,explicit_paths=allowed[prop],reviewer_issue=x,disposition='STOP_CONTRADICTORY_REPAIR; contract not overridden'))
 return conflicts
