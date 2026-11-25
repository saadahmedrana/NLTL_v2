"""Exact rendered byte totals; component payload sizes, never provider token claims."""
import json,hashlib,collections

def measure(request):
 totals={k:0 for k in ['source','schema','code','diagnostics','metadata_and_json_overhead','system']}
 source_blocks=[]
 user=request.get('user','');system=request.get('system','');totals['system']=len(system.encode())
 def bucket(path):
  if any(x in path for x in ['raw_previous_response','current_findings','static_warnings','persistent_failure_summary','format_error']):return 'diagnostics'
  if any(x in path for x in ['full_candidate','full_code','previous_candidate','previous_raw_response','change_manifest']):return 'code'
  if any(x in path for x in ['source_documents','exact_regulatory_text']) or path[-2:]==['requirement','text']:return 'source'
  if any(x in path for x in ['schema_terms','ontology_evidence','contract','termOwners','modelPaths','quantityEncoding','schema_contract_evidence']):return 'schema'
  return 'metadata_and_json_overhead'
 def visit(value,path):
  if isinstance(value,dict):
   for k,v in value.items():
    label=['source_documents'] if k=='text' and value.get('kind')=='SOURCE' else ['schema_terms'] if k=='text' and value.get('kind') in ['SCHEMA_TEXT','RDF_FACT','CALLER_DECLARATION','CONTEXT_STATUS'] else []
    visit(v,path+label+[k])
  elif isinstance(value,list):
   for v in value:visit(v,path)
  else:
   totals[bucket(path)]+=len(json.dumps(value,ensure_ascii=False).encode())
   if bucket(path)=='source' and isinstance(value,str) and path and path[-1] in ['text','exact_regulatory_text']:
    source_blocks.append(dict(sha256=hashlib.sha256(value.encode()).hexdigest(),plain_utf8_bytes=len(value.encode())))
 try:visit(json.loads(user),[])
 except Exception:totals['metadata_and_json_overhead']=len(user.encode())
 totals['metadata_and_json_overhead']+=len(user.encode())-sum(v for k,v in totals.items() if k!='system')
 counts=collections.Counter(b['sha256'] for b in source_blocks);sizes={b['sha256']:b['plain_utf8_bytes'] for b in source_blocks}
 return dict(exact_source_blocks=source_blocks,within_request_exact_source_repeat_plain_bytes=sum((n-1)*sizes[h] for h,n in counts.items()),rendered_bytes=len(user.encode())+len(system.encode()),rendered_characters=len(user)+len(system),components_bytes=totals,component_method='JSON primitive payloads by key path; keys/separators and additional JSON escaping in overhead',token_count=None,token_note='No tokenizer dependency or provider call; byte/character sizes are exact, not token estimates.')
