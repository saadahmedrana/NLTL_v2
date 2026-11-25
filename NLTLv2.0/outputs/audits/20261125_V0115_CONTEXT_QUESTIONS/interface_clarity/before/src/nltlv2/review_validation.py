"""Collect independent reviewer protocol failures. No partial review becomes repair state."""
from .review_protocol import normalize_response,ReviewerFormatError,reviewer_schema,claim_basis,context_only,ISSUE_BASES,CLAIM_BASES,REVIEW_DECISIONS,TECHNICAL_EVIDENCE_KINDS,decision_contract_errors,COMMON_ISSUE_TEXT_FIELDS,CLAIM_REQUIRED_FIELDS,legacy_reviewer_schema
from .evidence import evidence_catalog,citation_error,review_binding

def validate_legacy_review(response,c,context,max_issues=12,*,previous=None,changes=None,prior_issues=(),request_body=None):
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
   assessment['removal_assessments']=[dict(alert_id=a['alert_id'],disposition=assessment['removal_disposition'],**{k:assessment[k] for k in ['source_evidence_id','source_excerpt','candidate_excerpt','previous_excerpt','reason','claim_basis','evidence_id','evidence_excerpt'] if k in assessment}) for a in (group or {}).get('removal_alerts',[])]
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
 if decision not in REVIEW_DECISIONS:error('INVALID_DECISION','$.decision','ACCEPT | REJECT | UNRESOLVED | REQUEST_EVIDENCE',decision)
 if len(obj['issues'])>max_issues:error('ISSUE_BOUND','$.issues','At most '+str(max_issues)+' issues',len(obj['issues']))
 for code,expected in decision_contract_errors(obj):error(code,'$.decision',expected,decision)
 def cite(x,path,source=False):
  key='source_evidence_id' if source else 'evidence_id';quote='source_excerpt' if source else 'evidence_excerpt';problem=citation_error(catalog,x.get(key),x.get(quote),source=source)
  if problem:
   code,expected=problem;error(code,path+'.'+(key if code=='MISSING_OR_UNSUPPLIED_EVIDENCE_ID' or code=='SOURCE_ID_KIND_MISMATCH' else quote),expected,x.get(key) if code in ['MISSING_OR_UNSUPPLIED_EVIDENCE_ID','SOURCE_ID_KIND_MISMATCH'] else x.get(quote),'INVALID_SOURCE_QUOTATION' if source else 'UNSUPPORTED_SCHEMA_ASSERTION')
 def grounded(x,path,previous_required=False):
  basis=claim_basis(x)
  if x.get('claim_basis') not in [None,*CLAIM_BASES] or x.get('category') in ISSUE_BASES and x.get('claim_basis') not in [None,ISSUE_BASES[x['category']]]:error('INVALID_CLAIM_BASIS',path+'.claim_basis','Claim authority consistent with issue category',x.get('claim_basis'))
  if basis=='REGULATORY' or x.get('source_evidence_id') is not None or x.get('source_excerpt') is not None:cite(x,path,True)
  if x.get('category') in ISSUE_BASES or 'finding_key' in x or basis!='REGULATORY' or x.get('evidence_id') is not None or x.get('evidence_excerpt') is not None:
   cite(x,path)
   entry=next((e for e in catalog['entries'] if e['evidence_id']==x.get('evidence_id')),None)
   if basis=='TECHNICAL' and entry and entry['kind'] not in TECHNICAL_EVIDENCE_KINDS:error('TECHNICAL_EVIDENCE_KIND',path+'.evidence_id','Supplied schema fact/representation or approved scope evidence',entry['kind'])
  excerpt=x.get('candidate_excerpt');anchor=x.get('insertion_context')
  if (previous_required or not context_only(x)) and not (isinstance(excerpt,str) and excerpt.strip() and excerpt in c.code or not excerpt and isinstance(anchor,str) and anchor.strip() and anchor in c.code):error('ISSUE_EVIDENCE_NOT_IN_SOURCE_OR_CANDIDATE',path+'.candidate_excerpt','Verbatim current code excerpt or exact insertion_context',excerpt,'INVALID_CANDIDATE_QUOTATION')
  if previous_required and (previous is None or not isinstance(x.get('previous_excerpt'),str) or not x['previous_excerpt'].strip() or x['previous_excerpt'] not in previous.code):error('CHANGE_NOT_TIED_TO_PREVIOUS_CODE',path+'.previous_excerpt','Verbatim immediately preceding candidate',x.get('previous_excerpt'),'INVALID_PREVIOUS_QUOTATION')
  if not isinstance(x.get('reason'),str) or not x['reason'].strip():error('MISSING_REASON',path+'.reason','Specific source/code-based reason')
 schemas=legacy_reviewer_schema(max_issues)['properties']
 def fields(x,path,name):
  props=({k:{} for k in ['alert_id','disposition','source_evidence_id','source_excerpt','previous_excerpt','candidate_excerpt','insertion_context','reason','claim_basis','evidence_id','evidence_excerpt']} if name=='removal' else dict(schemas[name]['items']['properties']))
  props.update({k:{} for k in ['candidate_excerpt','previous_excerpt','insertion_context']})
  if name=='change_assessments':props['removal_assessments']={}
  for key in set(x)-set(props):error('UNKNOWN_REVIEW_FIELD',path+'.'+key,'Only documented fields for '+name)
 ids=[]
 for i,x in enumerate(obj['issues']):
  path=f'$.issues[{i}]'
  if not isinstance(x,dict):error('INCOMPLETE_EVIDENCED_ISSUE',path,'Issue object');continue
  fields(x,path,'issues')
  for key in [*COMMON_ISSUE_TEXT_FIELDS,*[k for k in CLAIM_REQUIRED_FIELDS.get(claim_basis(x),()) if k not in ['evidence_id','source_evidence_id']]]:
   if not isinstance(x.get(key),str) or not x[key].strip():error('INCOMPLETE_EVIDENCED_ISSUE',path+'.'+key,'Nonempty '+key,x.get(key))
  if x.get('category') not in ISSUE_BASES:error('INVALID_ISSUE_CATEGORY',path+'.category','Source-backed logic or unresolved context')
  if (claim_basis(x)=='REGULATORY' or x.get('source_clause') is not None) and x.get('source_clause')!=context['requirement']['clause']:error('WRONG_SOURCE_CLAUSE',path+'.source_clause',context['requirement']['clause'],x.get('source_clause'),'INVALID_SOURCE_QUOTATION')
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
  grounded(x,path)
  ids.append(x.get('issue_id'))
 if len(ids)!=len(set(map(str,ids))):error('DUPLICATE_ISSUE_ID','$.issues','Unique stable issue IDs')
 expected_changes={x['change_id']:x for x in (changes or {}).get('changes',[])};seen=[]
 for i,x in enumerate(obj['change_assessments']):
  path=f'$.change_assessments[{i}]'
  if not isinstance(x,dict):error('UNGROUNDED_CHANGE_ASSESSMENT',path,'Change object');continue
  fields(x,path,'change_assessments')
  valid=isinstance(x.get('change_id'),str) and x.get('change_id') in expected_changes
  if not valid or x.get('disposition') not in ['SUPPORTED','REGRESSION','UNRESOLVED']:error('UNGROUNDED_CHANGE_ASSESSMENT',path,'Known change ID/disposition')
  if claim_basis(x)=='CONTEXT' and x.get('disposition')!='UNRESOLVED':error('CONTEXT_CANNOT_SUPPORT_CHANGE',path+'.claim_basis','Context-only assessment cannot establish support or regression')
  grounded(x,path,True);seen.append(x.get('change_id'))
  if decision=='ACCEPT' and x.get('disposition')!='SUPPORTED':error('ACCEPT_WITH_UNRESOLVED_OR_REGRESSIVE_CHANGE',path+'.disposition','All accepted changes source-supported')
  if x.get('disposition')=='REGRESSION' and not any(isinstance(y,dict) and y.get('change_id')==x.get('change_id') and y.get('category') in ['SOURCE_BACKED_LOGIC_ERROR','TECHNICAL_REPRESENTATION_ERROR'] for y in obj['issues']):error('CHANGE_FAILURE_NEEDS_ACTIONABLE_ISSUE',path,'Corresponding issue/change_id')
  if x.get('disposition')=='UNRESOLVED' and decision not in ['UNRESOLVED','REQUEST_EVIDENCE']:error('UNRESOLVED_CHANGE_NEEDS_UNRESOLVED_DECISION',path,'UNRESOLVED decision')
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
  if x.get('reference') is not None and (not isinstance(x['reference'],str) or not x['reference'].strip() or len(x['reference'])>100):error('INVALID_SOURCE_REFERENCE',path+'.reference','Registered source identifier')
  if x.get('revision') is not None and type(x['revision']) is not int:error('INVALID_REFERENCE_REVISION',path+'.revision','Integer or null')
 if decision=='REQUEST_EVIDENCE' and not requests:error('EMPTY_EVIDENCE_REQUEST','$.evidence_requests','Nonempty requests')
 if not isinstance(assessments,list):error('INVALID_CONTEXT_ASSESSMENTS','$.context_assessments','Array');assessments=[]
 assessed=set()
 for i,x in enumerate(assessments):
  path=f'$.context_assessments[{i}]'
  if not isinstance(x,dict):error('INVALID_CONTEXT_ASSESSMENT',path,'Context assessment object');continue
  fields(x,path,'context_assessments')
  if not isinstance(x.get('finding_key'),str) or x.get('finding_key') in assessed or x.get('disposition') not in ['REPAIRABLE_CODE','MISSING_INFORMATION','UNRESOLVED']:error('INVALID_CONTEXT_ASSESSMENT',path,'Distinct finding key and explicit disposition')
  if context_only(x) and x.get('disposition')=='REPAIRABLE_CODE':error('CONTEXT_CANNOT_AUTHORIZE_REPAIR',path+'.claim_basis','Repairable code assessment requires a code claim and code location')
  grounded(x,path)
  assessed.add(str(x.get('finding_key')))
 obj['evidence_requests']=requests;obj['context_assessments']=assessments;obj['material_unchecked']=material
 return obj,audit,errors

def validate_compact_review(response,c,context,max_issues=12,*,previous=None,changes=None,prior_issues=(),request_body=None):
 """Small production response -> server-owned, candidate-bound internal findings."""
 import copy,json
 from .core import digest
 from .review_protocol import contract_shape_errors,reviewer_schema
 from .evidence import canonical,extract_location,code_location
 errors=[]
 def error(code,path,expected,observed=None,category='MALFORMED_STRUCTURE'):errors.append(dict(code=code,path=path,expected=expected,observed=observed,category=category))
 try:_,audit=normalize_response(response)
 except ReviewerFormatError as e:return None,None,[e.details]
 raw=audit['normalized_response'];groups=(changes or {}).get('changes',[]);change_map={'C'+str(i+1):g for i,g in enumerate(groups)};gap_map={'G'+str(i+1):g for i,g in enumerate(context.get('retrieval_gaps',[]))}
 prior_questions=(request_body or {}).get('prior_context_questions',[])
 prior_question_map={q['id']:q for q in prior_questions}
 finding_map=(request_body or {}).get('finding_aliases',{})
 schema=reviewer_schema(max_issues,changes=change_map,gaps=gap_map,findings=finding_map,questions=prior_question_map)
 errors+=contract_shape_errors(raw,schema)
 if errors:return None,audit,errors
 catalog=evidence_catalog(context,(request_body or {}).get('execution_probe'));entries={e['evidence_id']:e for e in catalog['entries']}
 if request_body is not None:
  expected=review_binding(c,context,prior_issues,previous,changes,request_body.get('execution_probe'),questions=prior_questions)
  if request_body.get('question_snapshot_sha256')!=digest(canonical(prior_questions)):error('STALE_CONTEXT_QUESTION_STATE','$request.prior_context_questions','Original immutable question snapshot',category='REQUEST_VERSION_BINDING')
  if any(request_body.get(k)!=v for k,v in expected.items()) or request_body.get('full_candidate')!=c.code or request_body.get('evidence_catalog')!=catalog:error('STALE_REVIEW_REQUEST','$request','Original immutable candidate/evidence/prior binding',category='REQUEST_VERSION_BINDING')
 def references(refs,path):
  resolved=[]
  for i,r in enumerate(refs):
   at=path+'['+str(i)+']';r={'id':r} if isinstance(r,str) else r;e=entries.get(r['id'])
   if e is None:error('MISSING_OR_UNSUPPLIED_EVIDENCE_ID',at,'E ID in this exact packet',r['id']);continue
   a,b=r.get('start',0),r.get('end',len(e['text']))
   if ('start' in r)!=('end' in r) or type(a) is not int or type(b) is not int or not 0<=a<b<=len(e['text']):error('INVALID_EVIDENCE_SPAN',at,'Valid character range in supplied evidence',r);continue
   if e['kind']=='RDF_FACT' and (a!=0 or b!=len(e['text'])):error('RDF_FACT_REFERENCE_MUST_BE_WHOLE_FACT',at,'Cite the complete explicit RDF fact, not a fragment',r);continue
   text=e['text'][a:b]
   if 'quote' in r:
    problem=citation_error(catalog,r['id'],r['quote'],source=e['kind']=='SOURCE')
    if problem:error(problem[0],at+'.quote',problem[1],r['quote']);continue
    if r['quote'] not in text and e['kind']!='RDF_FACT':error('ASSERTED_QUOTE_OUTSIDE_SPAN',at+'.quote','Asserted quotation inside cited span',r['quote']);continue
   resolved.append(dict(evidence_id=e['evidence_id'],kind=e['kind'],role='OBLIGATION' if e['kind']=='SOURCE' else 'POPULATION_ASSUMPTION' if e['kind']=='CALLER_DECLARATION' else 'REPRESENTATION' if e['kind'] in ['SCHEMA_TEXT','RDF_FACT'] else 'CONTEXT_STATUS',start=a,end=b,text=text,text_sha256=digest(text),evidence_sha256=e['evidence_sha256'],provenance_sha256=e['provenance_sha256']))
  return resolved
 def location(x,path):
  loc=code_location(c,x['start'],x['end'],unit=x.get('unit','lines'))
  try:exact=extract_location(loc,c)
  except ValueError as e:error(str(e),path,'Current candidate range',x);return loc,''
  return loc,exact
 issues=[]
 for i,item in enumerate(raw['issues']):
  path='$.issues['+str(i)+']';refs=references(item['evidence'],path+'.evidence');loc,exact=location(item['location'],path+'.location')
  support=[r for r in refs if r['role'] in ['OBLIGATION','REPRESENTATION','POPULATION_ASSUMPTION']]
  if not support:error('UNSUPPORTED_CODE_ASSERTION',path+'.evidence','Code issue needs obligation, schema/representation or approved scope evidence')
  law=next((r for r in refs if r['kind']=='SOURCE'),None);first=next(iter(support),None)
  stable='issue:'+digest(canonical([' '.join(item['description'].split()).casefold(),sorted(r['evidence_sha256'] for r in refs)]))
  operands=[dict(operand_id='operand'+str(j+1),property=o['property'],proposed_path=o['path'],proposed_path_role=o['role'],proposed_unit=o.get('unit'),proposed_datatype=o.get('datatype')) for j,o in enumerate(item.get('operands',[]))]
  issues.append(dict(issue_id=stable,category='SOURCE_BACKED_LOGIC_ERROR' if law else 'TECHNICAL_REPRESENTATION_ERROR',source_clause=context['requirement']['clause'] if law else None,source_evidence_id=law['evidence_id'] if law else None,source_excerpt=law['text'] if law else None,evidence_id=first['evidence_id'] if first else None,evidence_excerpt=first['text'] if first else None,reason=item['description'],expected=item['suggestion'],suggestion=item['suggestion'],candidate_excerpt=exact,candidate_location=loc,resolved_evidence=refs,operands=operands,addresses=item.get('addresses',[])))
 questions=[];requests=[]
 for i,q in enumerate(raw['questions']):
  refs=references(q.get('evidence',[]),'$.questions['+str(i)+'].evidence');questions.append(dict(missing=q['missing'],why=q['why'],kind=q['kind'],reference=q.get('reference'),section=q.get('section'),resolved_evidence=refs));requests.append(dict(kind=q['kind'],reference=q.get('reference'),section=q.get('section'),query=q['missing'][:2000],reason=q['why']))
 question_dispositions=[];question_ids=[];pending_questions=[]
 from .context_resolution import question_key
 new_question_keys={question_key(q['missing'],q['kind']) for q in questions}
 for i,d in enumerate(raw.get('question_review',[])):
  path='$.question_review['+str(i)+']';prior_q=prior_question_map[d['id']];question_ids.append(d['id']);refs=references(d.get('evidence',[]),path+'.evidence')
  if d['disposition'] in ['RESOLVED','WITHDRAWN']:
   if not refs or not any(r['role'] in ['OBLIGATION','REPRESENTATION','POPULATION_ASSUMPTION'] for r in refs):error('QUESTION_CLOSURE_NEEDS_EVIDENCE',path+'.evidence','Current supplied evidence supporting the explanation')
   if question_key(prior_q['missing'],prior_q['kind']) in new_question_keys:error('CONTRADICTORY_QUESTION_DISPOSITION',path,'Cannot close a concern and simultaneously ask it as missing information',d['id'])
  else:
   pending_questions.append(prior_q)
   requests.append(dict(kind=prior_q['kind'],reference=prior_q.get('reference'),section=prior_q.get('section'),query=prior_q['missing'][:2000],reason=prior_q['why']))
  question_dispositions.append(dict(id=d['id'],disposition=d['disposition'],why=d['why'],resolved_evidence=refs))
 if set(question_ids)!=set(prior_question_map) or len(question_ids)!=len(set(question_ids)):error('INCOMPLETE_QUESTION_REVIEW','$.question_review','Every prior material question exactly once')
 if raw['assessment']=='APPROVE' and pending_questions:error('UNRESOLVED_QUESTION_APPROVAL','$.assessment','STILL_UNRESOLVED prior questions block APPROVE')
 assessed=[];assessments=[]
 for i,x in enumerate(raw.get('change_review',[])):
  path='$.change_review['+str(i)+']';g=change_map[x['id']];refs=references(x['evidence'],path+'.evidence');assessed.append(x['id'])
  if not any(r['role'] in ['OBLIGATION','REPRESENTATION','POPULATION_ASSUMPTION'] for r in refs):error('UNSUPPORTED_CHANGE_ASSESSMENT',path+'.evidence','Source/schema/scope evidence, not checker silence alone')
  if x['disposition']=='REGRESSION':
   idx=x.get('issue');valid=type(idx) is int and 0<=idx<len(issues)
   if not valid:error('CHANGE_FAILURE_NEEDS_ACTIONABLE_ISSUE',path+'.issue','Zero-based index of actionable issue',idx)
   else:issues[idx]['change_id']=g['change_id']
  assessments.append(dict(change_id=g['change_id'],disposition=x['disposition'],reason=x['reason'],resolved_evidence=refs,removal_disposition='SUPPORTED_REMOVAL' if x['disposition']=='SUPPORTED' else x['disposition'],previous_excerpt=previous.code if previous else '',candidate_excerpt=c.code))
 if set(assessed)!=set(change_map) or len(assessed)!=len(set(assessed)):error('INCOMPLETE_CHANGE_REVIEW','$.change_review','Every supplied C ID exactly once')
 gap_seen=[];unchecked=[]
 for i,g in enumerate(raw.get('gap_review',[])):
  gap_seen.append(g['id']);unchecked.append(dict(scope=gap_map[g['id']]['gap_id'],material=g['material'],reason=g['why']))
 if len(gap_seen)!=len(set(gap_seen)):error('DUPLICATE_GAP_ASSESSMENT','$.gap_review','Each gap at most once')
 if any(g['material'] for g in raw.get('gap_review',[])) and not questions:error('MATERIAL_GAP_NEEDS_QUESTION','$.questions','Describe missing information and why it matters')
 unresolved=any(x['disposition']=='UNRESOLVED' for x in assessments)
 for q in pending_questions:unchecked.append(dict(scope=q['id'],material=True,reason=q['why']))
 assessment=raw['assessment']
 if assessment=='APPROVE':
  if issues or questions or unresolved or any(x['disposition']!='SUPPORTED' for x in assessments):error('DECISION_ISSUE_CONTRADICTION','$.assessment','APPROVE requires no code issues, questions or unsupported changes')
  if set(gap_seen)!=set(gap_map):error('UNASSESSED_RETRIEVAL_GAP','$.gap_review','Every supplied G ID explicitly assessed')
  if any(x['material'] for x in unchecked):error('DECISION_ISSUE_CONTRADICTION','$.assessment','Material uncertainty prevents APPROVE')
 if assessment=='REJECT' and not issues:error('DECISION_ISSUE_CONTRADICTION','$.assessment','REJECT requires an actionable code issue')
 if assessment=='HUMAN_REVIEW_REQUIRED' and not (questions or unresolved or any(x['material'] for x in unchecked)):error('DECISION_ISSUE_CONTRADICTION','$.assessment','Describe a context question or unresolved change/gap; code-only issues use REJECT')
 # Software-owned prior reconciliation. Stable IDs use description + immutable
 # evidence identity, never mutable E aliases or model-supplied bookkeeping.
 current={x['issue_id'] for x in issues};reconciliations=[dict(issue_id=x['issue_id'],state='PERSISTENT' if x['issue_id'] in current else 'RESOLVED' if assessment=='APPROVE' else 'UNASSESSABLE',reason='Derived from complete current review, not independent proof') for x in prior_issues]
 context_assessments=[dict(finding_key=finding_map[a],disposition='REPAIRABLE_CODE',reason=x['reason']) for x in issues for a in x['addresses']]
 for q in questions:unchecked.append(dict(scope=q['missing'],material=True,reason=q['why']))
 if unresolved:unchecked.append(dict(scope='Unresolved change assessment',material=True,reason='Uncertainty is not code-repair permission'))
 obj=dict(assessment=assessment,decision={'APPROVE':'ACCEPT','HUMAN_REVIEW_REQUIRED':'UNRESOLVED','REJECT':'REJECT'}[assessment],issues=issues,questions=questions,question_dispositions=question_dispositions,prior_context_questions=copy.deepcopy(prior_questions),change_assessments=assessments,reconciliations=reconciliations,unchecked=unchecked,material_unchecked=[x for x in unchecked if x['material']],evidence_requests=requests,context_assessments=context_assessments,candidate_version=c.version,candidate_sha256=c.sha256,review_request_id=(request_body or {}).get('review_request_id'),model_response=copy.deepcopy(raw),software_owned_metadata=True)
 return obj,audit,errors

# Legacy parsing is retained only to replay explicitly offline regression controls.
# A production request identifies contract 4; old replies then fail the small schema.
def validate_review(response,c,context,max_issues=12,*,previous=None,changes=None,prior_issues=(),request_body=None):
 if (request_body or {}).get('review_contract_version')==4 or request_body is None and '"assessment"' in response.get('text',''):
  return validate_compact_review(response,c,context,max_issues,previous=previous,changes=changes,prior_issues=prior_issues,request_body=request_body)
 return validate_legacy_review(response,c,context,max_issues,previous=previous,changes=changes,prior_issues=prior_issues,request_body=request_body)
