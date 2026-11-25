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

def legacy_reviewer_schema(max_issues=12,strict=False,primary_clause=None):
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

def response_format(config,schema=None):
 mode=config.get('review_output_mode','bounded_json')
 if mode=='bounded_json':return None
 cap=config.get('provider_capabilities',{})
 if mode!='json_schema' or cap.get('responses_text_json_schema') is not True or not cap.get('documentation_url'):raise ValueError('STRUCTURED_REVIEW_CAPABILITY_NOT_VERIFIED')
 return dict(type='json_schema',name='source_grounded_review',strict=True,schema=schema or reviewer_schema(config.get('review_max_issues',12),strict=True))

# Current production contract. Legacy schema above exists only for explicitly
# offline regression controls, and is rejected by Runner for live transports.
def reviewer_schema(max_issues=12,strict=False,primary_clause=None,*,changes=(),gaps=(),findings=(),version=4):
 if version==3:return legacy_reviewer_schema(max_issues,strict,primary_clause)
 def obj(properties,required=None):return dict(type='object',properties=properties,required=list(properties) if required is None else required,additionalProperties=False)
 text=dict(type='string',minLength=1)
 ref={'anyOf':[text,obj(dict(id=text,start={'type':'integer'},end={'type':'integer'},quote=text),['id'])]}
 refs=dict(type='array',items=ref,minItems=1,maxItems=8)
 location=obj(dict(start={'type':'integer'},end={'type':'integer'},unit={'type':'string','enum':['lines','characters']}),['start','end'])
 operand=obj(dict(property=text,path={'type':'array','items':text,'minItems':1},role={'type':'string','enum':['PROPERTY','NUMERIC_OPERAND']},unit=text,datatype=text),['property','path','role'])
 issue=obj(dict(description=text,evidence=refs,location=location,suggestion=text,operands={'type':'array','items':operand,'minItems':1,'maxItems':8}),['description','evidence','location','suggestion'])
 if findings:issue['properties']['addresses']={'type':'array','items':{'enum':list(findings)},'uniqueItems':True}
 question=obj(dict(missing=text,why=text,kind={'type':'string','enum':['source','schema']},reference={'type':'string','minLength':1,'maxLength':100},section=text,evidence={'type':'array','items':ref,'maxItems':8}),['missing','why','kind'])
 properties=dict(assessment={'type':'string','enum':['APPROVE','HUMAN_REVIEW_REQUIRED','REJECT']},issues={'type':'array','items':issue,'maxItems':max_issues},questions={'type':'array','items':question,'maxItems':3})
 if changes:
  change=obj(dict(id={'enum':list(changes)},disposition={'type':'string','enum':['SUPPORTED','REGRESSION','UNRESOLVED']},reason=text,evidence=refs,issue={'type':'integer','minimum':0}),['id','disposition','reason','evidence'])
  properties['change_review']={'type':'array','items':change,'minItems':len(changes),'maxItems':len(changes)}
 if gaps:
  properties['gap_review']={'type':'array','items':obj(dict(id={'enum':list(gaps)},material={'type':'boolean'},why=text)),'maxItems':len(gaps)}
 schema=obj(properties);schema['description']=compact_contract_instructions();return schema

def compact_contract_instructions():
 return ('Return the complete assessment, issues and questions arrays. APPROVE requires no issues/questions and every change supported and every retrieval gap explicitly nonmaterial. REJECT requires an actionable code issue; material questions remain blocking even with REJECT. HUMAN_REVIEW_REQUIRED needs an explicit question or unresolved change/gap. '
 'Code issue: description, supplied evidence references, current code location and actionable suggestion. Context question: exactly what is missing, why it matters and source/schema retrieval kind; no invented code defect/location. '
 'Cite E IDs, optionally with character start/end for text entries; RDF_FACT references cite the whole atomic fact. Software extracts exact text. Never reproduce quotations unless deliberately asserting one (optional quote is checked exactly). Locations contain start/end, optional unit (default lines); software binds current hashes and extracts code. '
 'Regulation establishes obligations. Schema/declared representation establishes RDF identifiers, paths, datatypes and units. Approved research scope establishes the external population assumption. A regulation need not literally contain an RDF IRI. Mappings do not establish regulatory formulas or compliance answers. Genuine missing/contradictory mappings stay questions. Citations do not prove interpretation. '
 'When supplied, assess every change ID once, including removed/replaced constraints and their reachable enforcement. REGRESSION must link the zero-based issue index; UNRESOLVED stays blocking. For APPROVE assess every gap ID with material=false and why; material gaps require questions. '
 'Software maintains stable issue IDs, prior reconciliation and candidate bindings. Review all supplied prior issues; APPROVE asserts none remains. Do not return hashes, issue IDs, reconciliation states, source-clause echoes or duplicate removal assessments. Never request evaluation fixtures/labels/solutions.')

def contract_shape_errors(value,schema,path='$'):
 """Validate the emitted small JSON-schema subset; definitions are authoritative."""
 errors=[]
 def error(code,expected):errors.append(dict(code=code,path=path,expected=expected,observed=value,category='MALFORMED_STRUCTURE'))
 if 'anyOf' in schema:
  variants=[contract_shape_errors(value,s,path) for s in schema['anyOf']]
  if all(variants):error('INVALID_FIELD_TYPE','One documented reference form')
  return errors
 kind=schema.get('type');valid={'object':lambda:isinstance(value,dict),'array':lambda:isinstance(value,list),'string':lambda:isinstance(value,str),'integer':lambda:type(value) is int,'boolean':lambda:type(value) is bool}
 if kind and not valid[kind]():error('INVALID_FIELD_TYPE',kind);return errors
 if 'enum' in schema and value not in schema['enum']:error('INVALID_FIELD_VALUE','One of '+str(schema['enum']))
 if kind=='object':
  for key in schema['required']:
   if key not in value:errors.append(dict(code='MISSING_REVIEW_FIELD',path=path+'.'+key,expected='Required complete-response field',observed=None,category='MALFORMED_STRUCTURE'))
  for key,v in value.items():
   if key not in schema['properties']:errors.append(dict(code='UNKNOWN_REVIEW_FIELD',path=path+'.'+key,expected='Only documented fields',observed=v,category='MALFORMED_STRUCTURE'))
   else:errors+=contract_shape_errors(v,schema['properties'][key],path+'.'+key)
 if kind in ['array','string']:
  lo=schema.get('minItems' if kind=='array' else 'minLength',0);hi=schema.get('maxItems' if kind=='array' else 'maxLength')
  if len(value)<lo or hi is not None and len(value)>hi:error('REVIEW_FIELD_BOUND','Declared length bounds')
 if kind=='array':
  if schema.get('uniqueItems') and len({json.dumps(v,sort_keys=True) for v in value})!=len(value):error('DUPLICATE_REVIEW_ITEM','Unique items')
  for i,v in enumerate(value):errors+=contract_shape_errors(v,schema['items'],path+'['+str(i)+']')
 if kind=='integer' and value<schema.get('minimum',value):error('REVIEW_FIELD_BOUND','Declared numeric bounds')
 return errors
