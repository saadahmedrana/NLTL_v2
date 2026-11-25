"""Bounded field alias normalization and optional provider JSON schema, not evidence repair."""
import json,copy
ALIASES={'exact_source_excerpt':'source_excerpt','exact_candidate_excerpt':'candidate_excerpt','exact_previous_excerpt':'previous_excerpt','exact_evidence_excerpt':'evidence_excerpt'}
class ReviewerFormatError(ValueError):
 def __init__(self,code,path='$',expected='See reviewer schema',observed=None,category='MALFORMED_STRUCTURE'):
  self.details=dict(code=code,path=path,category=category,expected=expected,observed=observed)
  super().__init__(json.dumps(self.details,ensure_ascii=False))
def normalize_response(response):
 raw=response['text'];events=[]
 if response.get('finish_reason') in ['length','max_tokens','max_output_tokens'] or response.get('status')=='incomplete':raise ReviewerFormatError('TRUNCATED_REVIEW','response.finish_reason','Complete provider response',response.get('finish_reason'),'TRUNCATED_RESPONSE')
 def pairs(items):
  d={}
  for k,v in items:
   if k in d and d[k]!=v:raise ReviewerFormatError('CONFLICTING_DUPLICATE_FIELD',k,'One unambiguous value',None,'CONFLICTING_FIELDS')
   d[k]=v
  return d
 try:obj=json.loads(raw,object_pairs_hook=pairs)
 except ReviewerFormatError:raise
 except Exception as e:raise ReviewerFormatError('INVALID_JSON','$','One complete JSON object',str(e)) from e
 def visit(node,path='$'):
  if isinstance(node,dict):
   for alias,canonical in ALIASES.items():
    if alias in node:
     if canonical in node and node[canonical]!=node[alias]:raise ReviewerFormatError('CONFLICTING_ALIAS',path+'.'+alias,'Same value as '+canonical,None,'CONFLICTING_FIELDS')
     node[canonical]=node.pop(alias);events.append(dict(path=path,alias=alias,canonical=canonical))
   for k,v in node.items():visit(v,path+'.'+k)
  elif isinstance(node,list):
   for i,v in enumerate(node):visit(v,path+'['+str(i)+']')
 visit(obj)
 return dict(response,text=json.dumps(obj,ensure_ascii=False),original_text=raw),dict(normalized_response=obj,aliases=events,raw_text=raw,values_modified=False)


# One response contract. Schema, runtime and rendered instructions use these rules.
CONTRACT_VERSION=3
COMMON_ISSUE_TEXT_FIELDS=('issue_id','category','reason','expected','suggestion')
CLAIM_REQUIRED_FIELDS={'REGULATORY':('source_clause','source_evidence_id','source_excerpt','evidence_id','evidence_excerpt'),'TECHNICAL':('evidence_id','evidence_excerpt'),'CONTEXT':('evidence_id','evidence_excerpt')}

ISSUE_BASES={'SOURCE_BACKED_LOGIC_ERROR':'REGULATORY','TECHNICAL_REPRESENTATION_ERROR':'TECHNICAL','UNRESOLVED_CONTEXT':'CONTEXT'}
CLAIM_BASES=('REGULATORY','TECHNICAL','CONTEXT')
REVIEW_DECISIONS=('ACCEPT','REJECT','UNRESOLVED','REQUEST_EVIDENCE')
TECHNICAL_EVIDENCE_KINDS=('SCHEMA_TEXT','RDF_FACT','CALLER_DECLARATION')
def claim_basis(x):
 return ISSUE_BASES.get(x.get('category'),x.get('claim_basis') or ('CONTEXT' if x.get('disposition') in ['MISSING_INFORMATION','UNRESOLVED'] and 'finding_key' in x else 'REGULATORY'))
def context_only(x):return claim_basis(x)=='CONTEXT'
def contract_instructions():
 return ('Response contract v3: source_clause, when supplied, is the exact primary clause identifier, not a display label or supporting-source quotation. '
 'REGULATORY claims require a SOURCE ID and an exact source quotation. TECHNICAL_REPRESENTATION_ERROR issues use technical evidence; change/reconciliation assessments may set claim_basis=TECHNICAL and cite supplied SCHEMA_TEXT, RDF_FACT or CALLER_DECLARATION evidence instead of a regulatory quotation. '
 'Every asserted citation is checked even when optional; evidence supports a claim but does not prove its interpretation. '
 'UNRESOLVED_CONTEXT issues and material unchecked entries describe missing information, not invented code defects: no offending code location is required for context-only issues. '
 'For ACCEPT, explicitly assess EVERY supplied retrieval gap in unchecked with scope=gap_id, material=true/false and reason; other decisions may report the relevant gaps. Material uncertainty prevents ACCEPT. '
 'UNRESOLVED needs a context issue, material unchecked entry, evidence request or unresolved change. REJECT needs an actionable regulatory or technical code issue. '
 'REGRESSION changes require a linked actionable issue; UNRESOLVED changes require UNRESOLVED or REQUEST_EVIDENCE, not an invented defect. '
 'Evidence-request reference is optional; without it the bounded resolver searches supplied approved documents, retaining ambiguity and missing context explicitly. '
 'Source quotations and any supplied code locations remain exact; failed responses never become accepted prior issues or repair permission.')
def decision_contract_errors(obj):
 decision=obj.get('decision');issues=obj.get('issues',[]);unchecked=obj.get('unchecked',[])
 material=any(isinstance(x,str) and x.strip() or isinstance(x,dict) and x.get('material') is True for x in unchecked)
 context=any(isinstance(x,dict) and context_only(x) for x in issues)
 pending=bool(obj.get('evidence_requests')) or any(isinstance(x,dict) and x.get('disposition')=='UNRESOLVED' for x in obj.get('change_assessments',[]))
 errors=[]
 if decision=='ACCEPT' and (issues or material or pending):errors.append(('DECISION_ISSUE_CONTRADICTION','ACCEPT requires no issues, material uncertainty, pending requests or unresolved changes'))
 if decision=='REJECT' and not any(isinstance(x,dict) and x.get('category') in ['SOURCE_BACKED_LOGIC_ERROR','TECHNICAL_REPRESENTATION_ERROR'] for x in issues):errors.append(('DECISION_ISSUE_CONTRADICTION','REJECT requires an actionable regulatory or technical code issue'))
 if decision=='UNRESOLVED' and not (context or material or pending):errors.append(('UNRESOLVED_DECISION_NEEDS_CONTEXT_ISSUE','UNRESOLVED requires explicit missing context in issues, unchecked, requests or unresolved changes'))
 return errors

def reviewer_schema(max_issues=12,strict=False,primary_clause=None):
 def obj(props):
  optional={'insertion_context','property','proposed_unit','proposed_datatype','proposed_path','change_id','removal_assessments','evidence_requests','context_assessments','reference','section','revision','candidate_excerpt','previous_excerpt','proposed_path_role','operands','representation_disposition','claim_basis','source_clause','source_evidence_id','source_excerpt','candidate_location','previous_location'}
  if 'disposition' in props:optional.discard('change_id')
  return dict(type='object',properties=props,required=[k for k in props if strict or k not in optional],additionalProperties=False)
 text={'type':'string'};nullable={'type':['string','null']}
 location=obj(dict(candidate_version={'type':'integer'},candidate_sha256=text,unit={'type':'string','enum':['characters','lines']},start={'type':'integer'},end={'type':'integer'}))
 issue=obj(dict(issue_id=text,category={'type':'string','enum':list(ISSUE_BASES)},source_clause=text,source_evidence_id=text,source_excerpt=text,candidate_excerpt=text,insertion_context=nullable,reason=text,expected=text,suggestion=text,evidence_id=text,evidence_excerpt=text,change_id=nullable,property=nullable,proposed_unit=nullable,proposed_datatype=nullable,proposed_path={'anyOf':[{'type':'array','items':text},{'type':'null'}]}))

 change=obj(dict(change_id=text,disposition={'type':'string','enum':['SUPPORTED','REGRESSION','UNRESOLVED']},source_evidence_id=text,source_excerpt=text,previous_excerpt=text,candidate_excerpt=text,insertion_context=nullable,reason=text))
 reconciliation=obj(dict(issue_id=text,state={'type':'string','enum':['RESOLVED','PERSISTENT','REGRESSED','UNASSESSABLE']},source_evidence_id=text,source_excerpt=text,candidate_excerpt=text,insertion_context=nullable,reason=text))
 result=obj(dict(candidate_version={'type':'integer'},candidate_sha256=text,review_request_id=text,decision={'type':'string','enum':list(REVIEW_DECISIONS)},issues={'type':'array','items':issue,'maxItems':max_issues},change_assessments={'type':'array','items':change},reconciliations={'type':'array','items':reconciliation},unchecked={'type':'array','items':obj(dict(scope=text,material={'type':'boolean'},reason=text))},evidence_requests={'type':'array','maxItems':3,'items':obj(dict(kind={'type':'string','enum':['source','schema']},reference=nullable,section=nullable,revision={'type':['integer','null']},query=text,reason=text))},context_assessments={'type':'array','items':obj(dict(finding_key=text,disposition={'type':'string','enum':['REPAIRABLE_CODE','MISSING_INFORMATION','UNRESOLVED']},source_evidence_id=text,source_excerpt=text,candidate_excerpt=text,insertion_context=nullable,evidence_id=text,evidence_excerpt=text,reason=text))}))
 for name in ['issues','change_assessments','reconciliations','context_assessments']:
  item=result['properties'][name]['items'];item['properties']['candidate_location']={'anyOf':[location,{'type':'null'}]}
  if name=='issues':
   item['properties']['proposed_path_role']={'type':['string','null'],'enum':['PROPERTY','NUMERIC_OPERAND',None]}
   operand=obj(dict(operand_id=text,property=text,proposed_path={'type':'array','minItems':1,'items':text},proposed_path_role={'type':'string','enum':['PROPERTY','NUMERIC_OPERAND']},proposed_unit=nullable,proposed_datatype=nullable))
   operand['required']=['operand_id','property','proposed_path','proposed_path_role']
   item['properties']['operands']={'anyOf':[{'type':'array','minItems':1,'maxItems':8,'items':operand},{'type':'null'}]}
   item['properties']['representation_disposition']={'type':['string','null'],'enum':['USE_DECLARED_REPRESENTATION','UNRESOLVED_CONTRADICTION',None]}

  if name=='change_assessments':
   item['properties']['previous_location']=location;item['required'].append('previous_location');item['properties']['removal_disposition']={'type':['string','null'],'enum':['SUPPORTED_REMOVAL','REPLACED','REGRESSION','UNRESOLVED',None]};item['required'].append('removal_disposition');item['properties'].pop('removal_assessments',None)
  item['properties']['claim_basis']={'type':['string','null'],'enum':list(CLAIM_BASES)+[None]}
  item['properties']['evidence_id']=nullable;item['properties']['evidence_excerpt']=nullable
  for key in ['source_clause','source_evidence_id','source_excerpt']:
   if key in item['properties']:item['properties'][key]=({'anyOf':[{'const':primary_clause},{'type':'null'}]} if key=='source_clause' and primary_clause is not None else dict(nullable))
  if name=='issues':
   item['allOf']=[]
   for category,basis in ISSUE_BASES.items():
    required=list(CLAIM_REQUIRED_FIELDS[basis])+(['candidate_location'] if basis!='CONTEXT' else [])
    item['allOf'].append({'if':{'properties':{'category':{'const':category}},'required':['category']},'then':{'required':required,'properties':dict({'claim_basis':{'enum':[basis,None]}},**{k:({'type':'string','minLength':1} if k!='candidate_location' else location) for k in required})}})
  if name=='change_assessments':
   item['required'].append('candidate_location');item['properties']['candidate_location']=location
  if name!='issues':
   explicit={'properties':{'claim_basis':{'enum':['TECHNICAL','CONTEXT']}},'required':['claim_basis']}
   inferred={'properties':{'disposition':{'enum':['MISSING_INFORMATION','UNRESOLVED']},'claim_basis':{'enum':['CONTEXT',None]}},'required':['disposition']} if name=='context_assessments' else {'not':{}}
   nonregulatory={'anyOf':[explicit,inferred]}
   item['allOf']=[{'if':nonregulatory,'then':{'required':['evidence_id','evidence_excerpt'],'properties':{k:{'type':'string','minLength':1} for k in ['evidence_id','evidence_excerpt']}}}, {'if':{'not':nonregulatory},'then':{'required':['source_evidence_id','source_excerpt'],'properties':{k:{'type':'string','minLength':1} for k in ['source_evidence_id','source_excerpt']}}}]
   context_authority={'anyOf':[{'properties':{'claim_basis':{'const':'CONTEXT'}},'required':['claim_basis']},inferred]}
   item['allOf'].append({'if':{'not':context_authority},'then':{'required':['candidate_location'],'properties':{'candidate_location':location}}})
   if name=='context_assessments':item['allOf'].append({'if':{'properties':{'disposition':{'const':'REPAIRABLE_CODE'}},'required':['disposition']},'then':{'required':['candidate_location'],'properties':{'candidate_location':location,'claim_basis':{'enum':['REGULATORY','TECHNICAL',None]}}}})
   if name=='change_assessments':item['allOf'].append({'if':{'properties':{'claim_basis':{'const':'CONTEXT'}},'required':['claim_basis']},'then':{'properties':{'disposition':{'const':'UNRESOLVED'}}}})

  # Advertise locations, not exact-code quotation fields. Legacy fields stay parser-only.
  for field in ['candidate_excerpt','previous_excerpt','insertion_context']:
   item['properties'].pop(field,None)
   if field in item['required']:item['required'].remove(field)
 result['properties']['evidence_requests']['items']['properties']['reference']={'anyOf':[{'type':'string','minLength':1,'maxLength':100},{'type':'null'}]}
 result['description']=contract_instructions()
 if strict:
  def require_all(node):
   if isinstance(node,dict):
    if node.get('type')=='object':node['required']=list(node['properties'])
    for value in node.values():require_all(value)
   elif isinstance(node,list):
    for value in node:require_all(value)
  require_all(result)
 return result

def response_format(config):
 mode=config.get('review_output_mode','bounded_json')
 if mode=='bounded_json':return None
 cap=config.get('provider_capabilities',{})
 if mode!='json_schema' or cap.get('responses_text_json_schema') is not True or not cap.get('documentation_url'):raise ValueError('STRUCTURED_REVIEW_CAPABILITY_NOT_VERIFIED')
 return dict(type='json_schema',name='source_grounded_review',strict=True,schema=reviewer_schema(config.get('review_max_issues',12),strict=True))
