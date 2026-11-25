"""Collect independent reviewer protocol failures. No partial review becomes repair state."""
from .review_protocol import normalize_response,ReviewerFormatError,reviewer_schema
from .evidence import evidence_catalog,citation_error,review_binding

def validate_review(response,c,context,max_issues=12,*,previous=None,changes=None,prior_issues=(),request_body=None):
 errors=[]
 def error(code,path,expected,observed=None,category='MALFORMED_STRUCTURE'):errors.append(dict(code=code,path=path,category=category,expected=expected,observed=observed))
 try:normalized,audit=normalize_response(response)
 except ReviewerFormatError as e:return None,None,[e.details]
 obj=audit['normalized_response']
 from .evidence import resolve_locations
 if isinstance(obj,dict):
  errors.extend(resolve_locations(obj,c,previous,required=bool(request_body and request_body.get('protocol_version')==2)))
  for assessment in obj.get('change_assessments',[]) if isinstance(obj.get('change_assessments'),list) else []:
   if not isinstance(assessment,dict) or 'removal_disposition' not in assessment:continue
   if 'removal_assessments' in assessment:error('DUPLICATE_CHANGE_ASSESSMENT','$.change_assessments','Use one removal_disposition on the change group, not a second assessment list')
   if assessment['removal_disposition'] not in [None,'SUPPORTED_REMOVAL','REPLACED','REGRESSION','UNRESOLVED']:error('INVALID_REMOVAL_DISPOSITION','$.change_assessments','Supported removal disposition')
   group=next((g for g in (changes or {}).get('changes',[]) if g['change_id']==assessment.get('change_id')),None)
   if group and group.get('removal_alerts') and assessment['removal_disposition'] is None:error('UNASSESSED_OBLIGATION_LOSS','$.change_assessments','Explicit removal disposition required')
   assessment['removal_assessments']=[dict(alert_id=a['alert_id'],disposition=assessment['removal_disposition'],**{k:assessment[k] for k in ['source_evidence_id','source_excerpt','candidate_excerpt','previous_excerpt','reason'] if k in assessment}) for a in (group or {}).get('removal_alerts',[])]
 allowed={'decision','issues','change_assessments','reconciliations','unchecked','evidence_requests','context_assessments','candidate_version','candidate_sha256','review_request_id'}
 required={'decision','issues','change_assessments','reconciliations','unchecked'}
 if not isinstance(obj,dict):error('INVALID_REVIEW_STRUCTURE_OR_ISSUE_BOUND','$','One review object');return obj,audit,errors
 if set(obj)-allowed or not required<=set(obj):error('INVALID_REVIEW_STRUCTURE_OR_ISSUE_BOUND','$','Required response fields and no unknown root fields',dict(missing=sorted(required-set(obj)),unknown=sorted(set(obj)-allowed)))
 for field in ['issues','change_assessments','reconciliations','unchecked']:
  if not isinstance(obj.get(field),list):error('INVALID_ARRAY','$.'+field,'Array')
 if not required<=set(obj) or any(not isinstance(obj.get(f),list) for f in ['issues','change_assessments','reconciliations','unchecked']):return obj,audit,errors
 execution=request_body.get('execution_probe') if request_body else None
 catalog=evidence_catalog(context,execution)
 expected=review_binding(c,context,prior_issues,previous,changes,execution)
 for k,v in expected.items():
  if obj.get(k)!=v or (k=='candidate_version' and type(obj.get(k)) is not int):error('STALE_OR_ABSENT_REVIEW_BINDING','$.'+k,'Echo exactly '+str(v),obj.get(k),'REQUEST_VERSION_BINDING')
 if request_body is not None:
  # The runtime dispatch guard already verifies this; parser remains safe if called directly.
  if request_body.get('evidence_catalog')!=catalog:error('UNSUPPLIED_REVIEW_EVIDENCE','$request.evidence_catalog','Catalog generated from the context actually supplied','', 'REQUEST_VERSION_BINDING')
  if any(request_body.get(k)!=v for k,v in expected.items()):error('STALE_REVIEW_REQUEST','$request','Original candidate/evidence/prior-state binding',None,'REQUEST_VERSION_BINDING')
 decision=obj.get('decision')
 if decision not in ['ACCEPT','REJECT','UNRESOLVED','REQUEST_EVIDENCE']:error('INVALID_DECISION','$.decision','ACCEPT | REJECT | UNRESOLVED | REQUEST_EVIDENCE',decision)
 if len(obj['issues'])>max_issues:error('ISSUE_BOUND','$.issues','At most '+str(max_issues)+' issues',len(obj['issues']))
 if decision!='REQUEST_EVIDENCE' and bool(obj['issues'])==(decision=='ACCEPT'):error('DECISION_ISSUE_CONTRADICTION','$.decision','ACCEPT has no issues; REJECT/UNRESOLVED need issues')
 def cite(x,path,source=False):
  key='source_evidence_id' if source else 'evidence_id';quote='source_excerpt' if source else 'evidence_excerpt';problem=citation_error(catalog,x.get(key),x.get(quote),source=source)
  if problem:
   code,expected=problem;error(code,path+'.'+(key if code=='MISSING_OR_UNSUPPLIED_EVIDENCE_ID' or code=='SOURCE_ID_KIND_MISMATCH' else quote),expected,x.get(key) if code=='MISSING_OR_UNSUPPLIED_EVIDENCE_ID' else x.get(quote),'INVALID_SOURCE_QUOTATION' if source else 'UNSUPPORTED_SCHEMA_ASSERTION')
 def grounded(x,path,previous_required=False):
  cite(x,path,True)
  excerpt=x.get('candidate_excerpt');anchor=x.get('insertion_context')
  if not (isinstance(excerpt,str) and excerpt.strip() and excerpt in c.code or not excerpt and isinstance(anchor,str) and anchor.strip() and anchor in c.code):error('ISSUE_EVIDENCE_NOT_IN_SOURCE_OR_CANDIDATE',path+'.candidate_excerpt','Verbatim current code excerpt or exact insertion_context',excerpt,'INVALID_CANDIDATE_QUOTATION')
  if previous_required and (previous is None or not isinstance(x.get('previous_excerpt'),str) or not x['previous_excerpt'].strip() or x['previous_excerpt'] not in previous.code):error('CHANGE_NOT_TIED_TO_PREVIOUS_CODE',path+'.previous_excerpt','Verbatim immediately preceding candidate',x.get('previous_excerpt'),'INVALID_PREVIOUS_QUOTATION')
  if not isinstance(x.get('reason'),str) or not x['reason'].strip():error('MISSING_REASON',path+'.reason','Specific source/code-based reason')
 schemas=reviewer_schema(max_issues)['properties']
 def fields(x,path,name):
  props=({k:{} for k in ['alert_id','disposition','source_evidence_id','source_excerpt','previous_excerpt','candidate_excerpt','insertion_context','reason']} if name=='removal' else dict(schemas[name]['items']['properties']))
  props.update({k:{} for k in ['candidate_excerpt','previous_excerpt','insertion_context']})
  if name=='change_assessments':props['removal_assessments']={}
  for key in set(x)-set(props):error('UNKNOWN_REVIEW_FIELD',path+'.'+key,'Only documented fields for '+name)
 ids=[]
 for i,x in enumerate(obj['issues']):
  path=f'$.issues[{i}]'
  if not isinstance(x,dict):error('INCOMPLETE_EVIDENCED_ISSUE',path,'Issue object');continue
  fields(x,path,'issues')
  for key in ['issue_id','category','source_clause','source_excerpt','reason','expected','suggestion','evidence_excerpt']:
   if not isinstance(x.get(key),str) or not x[key].strip():error('INCOMPLETE_EVIDENCED_ISSUE',path+'.'+key,'Nonempty '+key)
  if x.get('category') not in ['SOURCE_BACKED_LOGIC_ERROR','UNRESOLVED_CONTEXT']:error('INVALID_ISSUE_CATEGORY',path+'.category','Source-backed logic or unresolved context')
  if x.get('source_clause')!=context['requirement']['clause']:error('WRONG_SOURCE_CLAUSE',path+'.source_clause',context['requirement']['clause'],x.get('source_clause'),'INVALID_SOURCE_QUOTATION')
  for key in ['property','proposed_unit','proposed_datatype','change_id']:
   if x.get(key) is not None and not isinstance(x[key],str):error('INVALID_OPTIONAL_ISSUE_FIELD',path+'.'+key,'String or null')
  if x.get('proposed_path') is not None and (not isinstance(x['proposed_path'],list) or any(not isinstance(t,str) for t in x['proposed_path'])):error('INVALID_PROPOSED_PATH',path+'.proposed_path','IRI string array or null')
  if x.get('proposed_path_role') not in [None,'PROPERTY','NUMERIC_OPERAND']:error('INVALID_PATH_ROLE',path+'.proposed_path_role','PROPERTY or NUMERIC_OPERAND')
  if x.get('representation_disposition') not in [None,'USE_DECLARED_REPRESENTATION','UNRESOLVED_CONTRADICTION']:error('INVALID_REPRESENTATION_DISPOSITION',path+'.representation_disposition','USE_DECLARED_REPRESENTATION or UNRESOLVED_CONTRADICTION')
  operands=x.get('operands')
  if operands is not None:
   if not isinstance(operands,list) or not 1<=len(operands)<=8:error('INVALID_OPERANDS',path+'.operands','One to eight explicitly paired operands')
   else:
    operand_ids=[]
    for j,operand in enumerate(operands):
     at=path+'.operands['+str(j)+']'
     if not isinstance(operand,dict):error('INVALID_OPERAND',at,'Explicit operand object');continue
     if set(operand)-{'operand_id','property','proposed_path','proposed_path_role','proposed_unit','proposed_datatype'}:error('UNKNOWN_OPERAND_FIELD',at,'Only documented operand fields')
     for key in ['operand_id','property']:
      if not isinstance(operand.get(key),str) or not operand[key].strip():error('INVALID_OPERAND',at+'.'+key,'Nonempty '+key)
     operand_ids.append(operand.get('operand_id'))
     if not isinstance(operand.get('proposed_path'),list) or not operand['proposed_path'] or any(not isinstance(t,str) or not t for t in operand['proposed_path']):error('INVALID_PROPOSED_PATH',at+'.proposed_path','Nonempty IRI string array')
     if operand.get('proposed_path_role') not in ['PROPERTY','NUMERIC_OPERAND']:error('INVALID_PATH_ROLE',at+'.proposed_path_role','Explicit PROPERTY or NUMERIC_OPERAND')
     for key in ['proposed_unit','proposed_datatype']:
      if operand.get(key) is not None and (not isinstance(operand[key],str) or not operand[key]):error('INVALID_OPERAND',at+'.'+key,'String or null')
    if len(operand_ids)!=len(set(map(str,operand_ids))):error('DUPLICATE_OPERAND_ID',path+'.operands','Unique operand IDs within the issue')
  grounded(x,path);cite(x,path);ids.append(x.get('issue_id'))
 if len(ids)!=len(set(map(str,ids))):error('DUPLICATE_ISSUE_ID','$.issues','Unique stable issue IDs')
 if decision=='UNRESOLVED' and not any(isinstance(x,dict) and x.get('category')=='UNRESOLVED_CONTEXT' for x in obj['issues']):error('UNRESOLVED_DECISION_NEEDS_CONTEXT_ISSUE','$.issues','An explicit unresolved context issue')
 expected_changes={x['change_id']:x for x in (changes or {}).get('changes',[])};seen=[]
 for i,x in enumerate(obj['change_assessments']):
  path=f'$.change_assessments[{i}]'
  if not isinstance(x,dict):error('UNGROUNDED_CHANGE_ASSESSMENT',path,'Change object');continue
  fields(x,path,'change_assessments')
  valid=isinstance(x.get('change_id'),str) and x.get('change_id') in expected_changes
  if not valid or x.get('disposition') not in ['SUPPORTED','REGRESSION','UNRESOLVED']:error('UNGROUNDED_CHANGE_ASSESSMENT',path,'Known change ID/disposition')
  grounded(x,path,True);seen.append(x.get('change_id'))
  if decision=='ACCEPT' and x.get('disposition')!='SUPPORTED':error('ACCEPT_WITH_UNRESOLVED_OR_REGRESSIVE_CHANGE',path+'.disposition','All accepted changes source-supported')
  if x.get('disposition')!='SUPPORTED' and not any(isinstance(y,dict) and y.get('change_id')==x.get('change_id') for y in obj['issues']):error('CHANGE_FAILURE_NEEDS_ACTIONABLE_ISSUE',path,'Corresponding issue/change_id')
  if x.get('disposition')=='UNRESOLVED' and decision!='UNRESOLVED':error('UNRESOLVED_CHANGE_NEEDS_UNRESOLVED_DECISION',path,'UNRESOLVED decision')
  alerts={a['alert_id']:a for a in expected_changes[x['change_id']].get('removal_alerts',[])} if valid else {};assessed=[]
  removals=x.get('removal_assessments',[])
  if not isinstance(removals,list):error('INVALID_REMOVAL_ASSESSMENT',path+'.removal_assessments','Array');removals=[]
  for j,a in enumerate(removals):
   apath=path+f'.removal_assessments[{j}]'
   if not isinstance(a,dict):error('INVALID_REMOVAL_ASSESSMENT',apath,'Removal assessment');continue
   fields(a,apath,'removal')
   if not isinstance(a.get('alert_id'),str) or a.get('alert_id') not in alerts or a.get('disposition') not in ['SUPPORTED_REMOVAL','REPLACED','REGRESSION','UNRESOLVED']:error('INVALID_REMOVAL_ASSESSMENT',apath,'Known alert ID/disposition')
   grounded(a,apath,True);assessed.append(a.get('alert_id'))
   if decision=='ACCEPT' and a.get('disposition') not in ['SUPPORTED_REMOVAL','REPLACED']:error('ACCEPT_WITH_UNRESOLVED_OBLIGATION_LOSS',apath,'Supported removal/replacement')
  if valid and (set(map(str,assessed))!=set(alerts) or len(assessed)!=len(set(map(str,assessed)))):error('UNASSESSED_OBLIGATION_LOSS',path+'.removal_assessments','Each removal alert assessed exactly once',sorted(set(alerts)-set(map(str,assessed))),'UNASSESSED_CHANGE')
 if set(map(str,seen))!=set(expected_changes) or len(seen)!=len(set(map(str,seen))):error('INCOMPLETE_CHANGE_REVIEW','$.change_assessments','Each change ID exactly once')
 expected_prior={x['issue_id'] for x in prior_issues};reconciled=[]
 for i,x in enumerate(obj['reconciliations']):
  path=f'$.reconciliations[{i}]'
  if not isinstance(x,dict):error('UNGROUNDED_ISSUE_RECONCILIATION',path,'Known prior stable issue/state');continue
  fields(x,path,'reconciliations')
  if not isinstance(x.get('issue_id'),str) or x.get('issue_id') not in expected_prior or x.get('state') not in ['RESOLVED','PERSISTENT','REGRESSED','UNASSESSABLE']:error('UNGROUNDED_ISSUE_RECONCILIATION',path+'.issue_id','Only original prior issue IDs: '+str(sorted(expected_prior)),x.get('issue_id'))
  grounded(x,path);reconciled.append(x.get('issue_id'))
  if x.get('state')=='RESOLVED' and x.get('issue_id') in ids:error('RECONCILIATION_CONTRADICTION',path,'Resolved issue absent from current issues')
  if decision=='ACCEPT' and x.get('state')!='RESOLVED':error('ACCEPT_WITH_UNRESOLVED_PRIOR_ISSUE',path,'Every prior issue resolved')
 if set(map(str,reconciled))!=expected_prior or len(reconciled)!=len(set(map(str,reconciled))):error('INCOMPLETE_PRIOR_ISSUE_RECONCILIATION','$.reconciliations','Each original prior issue exactly once; no invented IDs')
 material=[]
 for i,x in enumerate(obj['unchecked']):
  if isinstance(x,str) and x.strip():entry=dict(scope=x,material=True,reason='Legacy untyped uncertainty is conservatively material')
  elif isinstance(x,dict) and isinstance(x.get('scope'),str) and x['scope'].strip() and type(x.get('material')) is bool and isinstance(x.get('reason'),str) and x['reason'].strip():entry=x
  else:error('INVALID_UNCHECKED_SCOPE',f'$.unchecked[{i}]','scope, boolean material, reason');continue
  if entry['material']:material.append(entry)
 if decision=='ACCEPT':
  assessed={x.get('scope') for x in obj['unchecked'] if isinstance(x,dict)}
  for gap in context.get('retrieval_gaps',[]):
   if gap['gap_id'] not in assessed:error('UNASSESSED_RETRIEVAL_GAP','$.unchecked','Explicit materiality assessment with scope='+gap['gap_id'],gap['evidence'],'UNASSESSED_CONTEXT')
 requests=obj.get('evidence_requests',[]);assessments=obj.get('context_assessments',[])
 if not isinstance(requests,list) or len(requests)>3:error('INVALID_EVIDENCE_REQUESTS','$.evidence_requests','At most three source/schema requests');requests=[]
 for i,x in enumerate(requests):
  path=f'$.evidence_requests[{i}]'
  if not isinstance(x,dict):error('INVALID_EVIDENCE_REQUEST',path,'Source/schema request');continue
  fields(x,path,'evidence_requests')
  if x.get('kind') not in ['source','schema'] or not isinstance(x.get('query'),str) or len(x['query'])>2000 or not isinstance(x.get('reason'),str) or not x['reason'].strip():error('INVALID_EVIDENCE_REQUEST',path,'kind, bounded query and reason')
  if x.get('kind')=='source' and (not isinstance(x.get('reference'),str) or not x['reference'].strip() or len(x['reference'])>100):error('INVALID_SOURCE_REFERENCE',path+'.reference','Registered source identifier')
  if x.get('revision') is not None and type(x['revision']) is not int:error('INVALID_REFERENCE_REVISION',path+'.revision','Integer or null')
 if decision=='REQUEST_EVIDENCE' and not requests:error('EMPTY_EVIDENCE_REQUEST','$.evidence_requests','Nonempty requests')
 if not isinstance(assessments,list):error('INVALID_CONTEXT_ASSESSMENTS','$.context_assessments','Array');assessments=[]
 assessed=set()
 for i,x in enumerate(assessments):
  path=f'$.context_assessments[{i}]'
  if not isinstance(x,dict):error('INVALID_CONTEXT_ASSESSMENT',path,'Context assessment object');continue
  fields(x,path,'context_assessments')
  if not isinstance(x.get('finding_key'),str) or x.get('finding_key') in assessed or x.get('disposition') not in ['REPAIRABLE_CODE','MISSING_INFORMATION','UNRESOLVED']:error('INVALID_CONTEXT_ASSESSMENT',path,'Distinct finding key and explicit disposition')
  grounded(x,path);cite(x,path);assessed.add(str(x.get('finding_key')))
 obj['evidence_requests']=requests;obj['context_assessments']=assessments;obj['material_unchecked']=material
 return obj,audit,errors
