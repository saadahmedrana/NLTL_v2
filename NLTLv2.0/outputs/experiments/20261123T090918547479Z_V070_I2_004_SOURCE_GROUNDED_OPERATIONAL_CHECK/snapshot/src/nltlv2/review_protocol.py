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

def reviewer_schema(max_issues=12):
 def obj(props):return dict(type='object',properties=props,required=list(props),additionalProperties=False)
 text={'type':'string'};nullable={'type':['string','null']}
 issue=obj(dict(issue_id=text,category={'type':'string','enum':['SOURCE_BACKED_LOGIC_ERROR','UNRESOLVED_CONTEXT']},source_clause=text,source_excerpt=text,candidate_excerpt=text,insertion_context=nullable,reason=text,expected=text,suggestion=text,evidence_excerpt=text,change_id=nullable,property=nullable,proposed_unit=nullable,proposed_datatype=nullable,proposed_path={'anyOf':[{'type':'array','items':text},{'type':'null'}]}))
 removal=obj(dict(alert_id=text,disposition={'type':'string','enum':['SUPPORTED_REMOVAL','REPLACED','REGRESSION','UNRESOLVED']},source_excerpt=text,previous_excerpt=text,candidate_excerpt=text,insertion_context=nullable,reason=text))
 change=obj(dict(change_id=text,disposition={'type':'string','enum':['SUPPORTED','REGRESSION','UNRESOLVED']},source_excerpt=text,previous_excerpt=text,candidate_excerpt=text,insertion_context=nullable,reason=text,removal_assessments={'type':'array','items':removal}))
 reconciliation=obj(dict(issue_id=text,state={'type':'string','enum':['RESOLVED','PERSISTENT','REGRESSED','UNASSESSABLE']},source_excerpt=text,candidate_excerpt=text,insertion_context=nullable,reason=text))
 return obj(dict(decision={'type':'string','enum':['ACCEPT','REJECT','UNRESOLVED']},issues={'type':'array','items':issue,'maxItems':max_issues},change_assessments={'type':'array','items':change},reconciliations={'type':'array','items':reconciliation},unchecked={'type':'array','items':obj(dict(scope=text,material={'type':'boolean'},reason=text))}))

def response_format(config):
 mode=config.get('review_output_mode','bounded_json')
 if mode=='bounded_json':return None
 cap=config.get('provider_capabilities',{})
 if mode!='json_schema' or cap.get('responses_text_json_schema') is not True or not cap.get('documentation_url'):raise ValueError('STRUCTURED_REVIEW_CAPABILITY_NOT_VERIFIED')
 return dict(type='json_schema',name='source_grounded_review',strict=True,schema=reviewer_schema(config.get('review_max_issues',12)))
