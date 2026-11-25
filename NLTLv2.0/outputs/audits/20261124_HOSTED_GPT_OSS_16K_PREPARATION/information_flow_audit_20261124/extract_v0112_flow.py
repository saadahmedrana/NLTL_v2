from pathlib import Path
import json,hashlib,re,collections,ast,socket
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2');R=ROOT/'NLTLv2.0';M=ROOT/'MVP/SHACL_GENERATION_PIPELINE';B=R/'outputs/experiments/20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01';A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION';O=A/'information_flow_audit_20261124';O.mkdir(exist_ok=False)
def deny(*a,**kw):raise RuntimeError('NETWORK_DISABLED_READ_ONLY_AUDIT')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
inputs={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 p=Path(p);inputs[str(p)]=sha(p);return p.read_text()
def load(p):return json.loads(read(p))
def write(name,x):(O/name).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
# Existing R files are protected; the only writes in this audit are new O artifacts.
write('protected_before.json',{str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.is_relative_to(O)})
manifest=load(B/'manifest.frozen.json');closure=load(B/'dispatch_closed.json');inventory=load(B/'candidate_inventory.json')
assert sha(B/'selected_outputs.json')==closure['selection_manifest_sha256']
for name,h in closure['all_candidate_sha256'].items():assert sha(R/name)==h
frozen=load(B/'freeze_lock.json');source_identity={name:dict(expected=h,current=sha(R/name),matches=sha(R/name)==h) for name,h in frozen['files'].items()};assert all(v['matches'] for v in source_identity.values());write('frozen_source_identity.json',source_identity)
source=A/'runtime/src/nltlv2';functions={}
for p in list(source.glob('*.py'))+[M/'orchestration/no_semantic_validator.py']:
 if not p.exists():continue
 s=read(p)
 for node in ast.walk(ast.parse(s)):
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)):functions[str(p)+':'+node.name]=node.lineno
write('function_references.json',functions)
calls=[];byrid=collections.defaultdict(list)
for p in sorted((B/'provider').glob('call_*_request.json')):
 n=int(p.stem.split('_')[1]);req=load(p);payload=req['payload'];body=json.loads(payload['input'][1]['content'][0]['text']);rid=body.get('context',{}).get('requirement',{}).get('id') or body.get('requirement_id');resp=load(B/'provider'/f'call_{n:03d}_response.json');actual=(B/'provider'/f'call_{n:03d}_request.body').read_bytes();assert json.loads(actual)==payload
 row=dict(call=n,requirement=rid,route=req['route'],request_file=str(p),request_body_file=str(B/'provider'/f'call_{n:03d}_request.body'),response_file=str(B/'provider'/f'call_{n:03d}_response.json'),payload_bytes=len(actual),model=payload['model'],max_output_tokens=payload['max_output_tokens'],payload_sha256=hashlib.sha256(actual).hexdigest(),response_status=resp['status'],finish_reason=resp['finish_reason'],usage=resp['usage'],candidate_version=body.get('candidate_version'),candidate_sha256=body.get('candidate_sha256'))
 calls.append(row);byrid[rid].append((row,body,resp,payload))
write('actual_provider_call_index.json',calls)
contexts=[];reviews=[];repairs=[];deterministic=[];budgets=[]
catalog=load(R/'data/requirements/source_catalog.json')['sources']
for rid in manifest['requirements']:
 d=B/rid/'NLTL';gen=next(x for x in byrid[rid] if x[0]['route']=='generation');ctx=gen[1]['context'];scope=ctx['admission'];docs=ctx['source_documents'];selections=[]
 for doc in docs:selections.append({k:doc[k] for k in doc if k!='text'}|dict(characters=len(doc['text']),text_sha256=hashlib.sha256(doc['text'].encode()).hexdigest(),direct_requirement_verbatim_inside=ctx['requirement']['text'] in doc['text']))
 overlap=0
 for file in {v['file'] for v in docs}:
  intervals=sorted((v['selection']['start'],v['selection']['end']) for v in docs if v['file']==file);last=-1
  for start,end in intervals:overlap+=max(0,min(last,end)-start);last=max(last,end)
 records=load(R/'data/requirements/requirements.json');record=records[rid]
 initial=dict(requirement=rid,provider_call=gen[0],regulation=ctx['requirement'],supporting_descriptors=record.get('supporting_sources',[]),source_documents=selections,source_characters=sum(len(x['text']) for x in docs),overlap_character_count=overlap,all_schema_terms=ctx['schema_terms'],all_supplied_ontology_facts=ctx['ontology_evidence'],quantity_encoding=ctx['quantityEncoding'],delivered_representation_contract=ctx['contract'],delivered_termOwners=ctx['termOwners'],delivered_modelPaths=ctx['modelPaths'],approved_scope=scope,unresolvedOwnership=ctx.get('unresolvedOwnership'),initial_unresolved_source=ctx.get('unresolvedSourceContext'),source_selection=ctx['source_selection'],source_manifest_file=str(d/'source_selection_manifest.json'),examples=ctx.get('examples'),direct_text_also_in_source=any(ctx['requirement']['text'] in x['text'] for x in docs),direct_text_also_in_RDF_facts=any(ctx['requirement']['text'] in str(x) for x in ctx['ontology_evidence']),term_and_fact_counts=dict(terms=len(ctx['schema_terms']),facts=len(ctx['ontology_evidence'])))
 contexts.append(initial)
 run=load(d/'run.json');budget=dict(requirement=rid,terminal=run['status'],delivery=run['delivery']['status'],final_handoff=run['delivery']['final_review'],physical_calls=sum(1 for x in byrid[rid]),generation_calls=sum(x[0]['route']=='generation' for x in byrid[rid]),technical_repairs=sum(x[0]['route'].endswith('repair') for x in byrid[rid]),semantic_repairs=0,primary_reviews=sum(x[0]['route']=='review' for x in byrid[rid]),corrections=sum(x[0]['route']=='review_format_retry' for x in byrid[rid]),retrieval_rounds=len(load(d/'retrieval_ledger.json')) if (d/'retrieval_ledger.json').exists() else 0,maximum_candidates=2,maximum_repairs=1,max_primary_reviews=4,max_reviews_per_candidate=3,max_corrections_per_review=1,max_retrieval_rounds=2,repair_capacity_remaining=1-run['repair_calls'],accepted_issues=0,repair_cap_vs_invalid_review='Review never validated; technical cap additionally spent' if run['repair_calls'] else 'Repair remained available but review never validated')
 budgets.append(budget)
 for t in sorted(d.glob('technical_*.json')):
  x=load(t);v=x['candidate_version'];candidate=d/f'candidate_{v:02d}.ttl';assert sha(candidate)==x['candidate_sha256'];probe=d/f'runtime_probe_{v:02d}.json'
  deterministic.append(dict(requirement=rid,artifact=str(t),candidate_file=str(candidate),candidate_version=v,candidate_sha256=x['candidate_sha256'],technical_qualifies=x['qualifies'],runtime_complete=x['runtime_complete'],full_findings=x['findings'],probe=load(probe) if probe.exists() else None,check_seconds=x['check_seconds']))
 localreqs={}
 for local in sorted(d.glob('request_*.json')):
  x=load(local)
  if x.get('user') and x.get('route'):localreqs[(x['route'],x['user'])]=(local,x)
 for row,body,resp,payload in byrid[rid]:
  if row['route']=='generation':continue
  local,original=localreqs[(row['route'],payload['input'][1]['content'][0]['text'])]
  n=int(local.stem.split('_')[1]);localresp=load(d/f'response_{n:03d}.json');assert localresp['text']==resp['text']
  if row['route'].endswith('repair'):
   v=body['candidate_version'];full=(d/f'candidate_{v:02d}.ttl').read_text();findings=load(d/f'findings_{v:02d}.json');checks=[]
   for f in body['current_findings']:
    checks.append(dict(category=f['category'],diagnostic_exact_from_original=any(f.get('diagnostic')==z.get('diagnostic') for z in findings if z['category']==f['category']),guidance=f.get('suggestion'),location=f.get('location'),candidate_location=f.get('candidate_location'),identifier_excerpt=f.get('identifier_excerpt')))
   entries=body['evidence_catalog']['entries'];repairs.append(dict(requirement=rid,call=row,local_request=str(local),system=payload['input'][0]['content'][0]['text'],full_packet=body,complete_latest_candidate=body['previous_candidate']==full,latest_hash_correct=hashlib.sha256(full.encode()).hexdigest()==body['candidate_sha256'],original_diagnostic_checks=checks,catalog_counts=dict(collections.Counter(e['kind'] for e in entries)),after_candidate_sha256=sha(d/f'candidate_{v+1:02d}.ttl'),diff_file=str(d/f'diff_{v:02d}_{v+1:02d}.patch'),code_diff=read(d/f'diff_{v:02d}_{v+1:02d}.patch'),semantic_findings_delivered=[f for f in body['current_findings'] if f['category']=='SOURCE_BACKED_LOGIC_ERROR']))
  elif row['route'].startswith('review'):
   fail=load(d/f'reviewer_format_failure_{n:03d}.json');obj=json.loads(resp['text']);entries=body['evidence_catalog']['entries'];lookup={e['evidence_id']:e for e in entries};refs=[]
   def walk(value,path='$'):
    if isinstance(value,dict):
     for idfield,quotefield in [('source_evidence_id','source_excerpt'),('evidence_id','evidence_excerpt')]:
      if idfield in value:
       e=lookup.get(value.get(idfield));quote=value.get(quotefield);refs.append(dict(path=path,field=idfield,id=value.get(idfield),quoted_value=quote,supplied_entry=e,exact_substring_in_cited_text=bool(e and isinstance(quote,str) and quote in e['text']),quote_in_any_supplied_SOURCE=[z['evidence_id'] for z in entries if z['kind']=='SOURCE' and isinstance(quote,str) and quote and quote in z['text']]))
     for k,v in value.items():walk(v,path+'.'+k)
    elif isinstance(value,list):
     for i,v in enumerate(value):walk(v,path+'['+str(i)+']')
   walk(obj)
   statusfields=[];retrieval_fact_duplicates=0;fact_texts=[e['text'] for e in entries if e['kind']=='RDF_FACT']
   for e in entries:
    if e['kind']=='CONTEXT_STATUS':
     value=json.loads(e['text']);statusfields.append(dict(evidence_id=e['evidence_id'],context_field=e.get('origin',{}).get('context_field'),characters=len(e['text']),value=value))
     if isinstance(value,list):
      for rec in value:
       if isinstance(rec,dict):retrieval_fact_duplicates+=sum((' '.join(triple)+' .') in fact_texts for triple in rec.get('ontology_triples',[]) if isinstance(triple,list))
   gapitems=next((e['value'] for e in statusfields if e['context_field']=='retrieval_gaps'),[]);sourceentries=[dict(evidence_id=e['evidence_id'],origin=e.get('origin'),characters=len(e['text']),text_sha256=hashlib.sha256(e['text'].encode()).hexdigest(),contains_primary_regulation=ctx['requirement']['text'] in e['text']) for e in entries if e['kind']=='SOURCE']
   reviews.append(dict(requirement=rid,call=row,local_request=str(local),failure_file=str(d/f'reviewer_format_failure_{n:03d}.json'),candidate_sha256=body['candidate_sha256'],full_candidate_matches_saved_code=body['full_candidate']==(d/f"candidate_{body['candidate_version']:02d}.ttl").read_text(),previous_candidate=body.get('previous_candidate'),actual_system=payload['input'][0]['content'][0]['text'],full_model_response=obj,all_validation_errors=fail['validation_errors'],response_evidence_crosswalk=refs,source_entry_index=sourceentries,context_status_entries=statusfields,provided_gap_ids=[g['gap_id'] for g in gapitems],gap_count=len(gapitems),response_gap_ids=[g.get('scope') for g in obj.get('unchecked',[]) if isinstance(g,dict)],execution_probe=body['execution_probe'],prior_issues=body['prior_issues'],findings=body['findings'],format_feedback_dispatched=body.get('format_feedback'),catalog_kind_counts=dict(collections.Counter(e['kind'] for e in entries)),retrieval_RDF_fact_duplicates=retrieval_fact_duplicates,all_errors_forwarded_to_correction=None))
 for first in [x for x in reviews if x['requirement']==rid and x['call']['route']=='review']:
  correction=next(x for x in reviews if x['requirement']==rid and x['call']['route']=='review_format_retry');first['all_errors_forwarded_to_correction']=correction['format_feedback_dispatched']['validation_errors']==first['all_validation_errors']
  pbody=json.loads(load(Path(first['call']['request_file']))['payload']['input'][1]['content'][0]['text']);cbody=json.loads(load(Path(correction['call']['request_file']))['payload']['input'][1]['content'][0]['text']);assert {k:v for k,v in pbody.items() if k!='format_feedback'}=={k:v for k,v in cbody.items() if k!='format_feedback'}
write('initial_context_inventory.json',contexts);write('deterministic_trace.json',deterministic);write('all_ten_review_error_crosswalks.json',reviews);write('actual_repair_packets_and_diffs.json',repairs);write('budgets_and_routing.json',budgets)
write('source_catalog_and_available_files.json',dict(registered_sources=catalog,source_files=[str(p.relative_to(R)) for p in (R/'data/requirements').rglob('*') if p.is_file()],absence_scope='Unregistered UR I3,PR29,UR P0 are missing from this current source-only corpus, not proof of absence from every historical archive in NLTL_v2. Actual direct clauses and several ambiguous internally referenced sections are present.'))
write('input_hashes.json',inputs)
print(json.dumps(dict(output=str(O),requirements=len(contexts),review_responses=len(reviews),validation_errors=sum(len(r['all_validation_errors']) for r in reviews),dispatched_repairs=len(repairs),all_diagnostics_exact=all(z['diagnostic_exact_from_original'] for r in repairs for z in r['original_diagnostic_checks']),all_feedback_errors_forwarded=all(r['all_errors_forwarded_to_correction'] for r in reviews if r['call']['route']=='review'),no_model_calls=True,no_evaluation_reruns=True),indent=2))
