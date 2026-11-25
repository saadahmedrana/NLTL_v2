"""Bounded source/schema retrieval and audit only. No SHACL edits or compliance oracle."""
import copy,re,json,hashlib
from rdflib import Graph,URIRef,RDF,RDFS,SKOS
from rdflib.namespace import SH
from .source_context import sections,references,digest,scope_heading,contents_entry
DEFAULTS=dict(max_rounds=2,max_requests_per_round=3,max_source_documents=6,max_reference_lookups=24,max_depth=3,max_passages_per_round=6,max_characters_per_round=16000,max_total_characters=32000,max_schema_terms=24,max_schema_triples=300,max_reviews_per_candidate=3,max_reviews_per_run=8)
def limits(config):
 values=dict(DEFAULTS,**config.get('context_resolution',{}))
 for k,v in values.items():
  if k not in DEFAULTS or type(v) is not int or v<0 or v>max(DEFAULTS.get(k,0)*4,4):raise ValueError('INVALID_CONTEXT_RESOLUTION_LIMIT '+k)
 if values['max_reviews_per_candidate']<1 or values['max_reviews_per_run']<1:raise ValueError('REVIEW_LIMIT_MUST_BE_POSITIVE')
 return values
STOP={'the','and','for','this','that','from','with','source','shall','must','supplied','shape','current','node','class','requirements','requirement','context','value','according','into','does','not','are','has','its','was','will','true','false'}
def tokens(text):
 text=re.sub(r'([a-z])([A-Z])',r'\1 \2',text)
 return {re.sub(r'^applic(?:able|ation|ability)$','applic',w) for w in re.findall(r'[a-z][a-z0-9]+',text.casefold()) if len(w)>2 and w not in STOP}
class Resolver:
 def __init__(self,schema,config):
  self.schema=schema;self.p=schema.project;self.policy=limits(config);self.rounds=0;self.total_characters=0;self.cache={};self.input_hashes={};self.seen=set();self.attempted_requests=set();self.events=[];self.added_spans=set()
 def default_requests(self,context,candidate):
  refs=[]
  for doc in context['source_documents']:
   for r in references(doc['text']):
    if not any((x['reference'],x.get('section'),x.get('revision'))==(r['document_id'],r.get('section'),r.get('revision')) for x in refs):refs.append(dict(kind='source',reference=r['document_id'],section=r.get('section'),revision=r.get('revision'),query=context['requirement']['text'],reason='Explicit citation in supplied source'))
  questions=[]
  try:
   graph=Graph().parse(data=candidate.code,format='turtle')
   for p in [SH.description,RDFS.comment,SH.message]:
    for value in graph.objects(None,p):
     questions.extend(sentence for sentence in re.split(r'(?<=[.!?])\s+',str(value)) if re.search(r'(?i)applic|target|binding|unresolved|missing.*context',sentence))
  except Exception:pass
  query=(' '.join(questions) if questions else context['requirement']['text'])[:2000]
  return (refs[:max(self.policy['max_requests_per_round']-1,0)]+[dict(kind='schema',query=query,reason='Retrieve declarations and explicit mappings relevant to material source/activation questions')])[:self.policy['max_requests_per_round']]
 def _load(self,entry):
  file=entry['file']
  if file in self.cache:return self.cache[file]
  if len(self.cache)>=self.policy['max_source_documents']:raise ValueError('DOCUMENT_LIMIT')
  if not entry.get('sha256') or not entry.get('authority') or not entry.get('edition') or not entry.get('provenance'):raise ValueError('PROVENANCE_UNVERIFIED')
  cached=getattr(self.schema,'document_cache',{}).get(file)
  raw=cached['text'].encode('utf-8') if cached else self.p.path(file).read_bytes();actual=hashlib.sha256(raw).hexdigest()
  if actual!=entry['sha256']:raise ValueError('SOURCE_HASH_MISMATCH')
  provenance=entry['provenance']
  if isinstance(provenance,dict) and provenance.get('file'):
   source=self.p.path(provenance['file']);h=hashlib.sha256(source.read_bytes()).hexdigest()
   if h!=provenance.get('sha256'):raise ValueError('PROVENANCE_HASH_MISMATCH')
   self.input_hashes[provenance['file']]=h
  text=raw.decode('utf-8');self.input_hashes[file]=actual;self.cache[file]=text;return text
 def _source(self,request,context,batch,ancestry=(),depth=0,parent=None):
  ref=request['reference'];revision=request.get('revision');key=(ref,request.get('section'),revision)
  if key in ancestry:batch.append(dict(kind='source',reference=ref,status='CYCLE_SKIPPED',ancestry=[list(x) for x in ancestry]));return
  if key in self.seen:batch.append(dict(kind='source',reference=ref,status='ALREADY_REQUESTED'));return
  if len(self.seen)>=self.policy['max_reference_lookups']:batch.append(dict(kind='source',reference=ref,status='REFERENCE_LIMIT_EXHAUSTED'));return
  self.seen.add(key)
  if depth>self.policy['max_depth']:batch.append(dict(kind='source',reference=ref,status='DEPTH_LIMIT'));return
  matched=[dict(v,catalog_title=k) for k,v in self.schema.catalog.items() if ref.casefold() in {str(x).casefold() for x in [v.get('document_id',''),k]+v.get('aliases',[])}]
  if not matched:batch.append(dict(kind='source',reference=ref,status='MISSING_DOCUMENT'));return
  caller_selection=None
  selected=context.get('admission',{}).get('declaration',{}).get('source_editions',[])
  pinned=[x for x in matched if any(e['file']==x['file'] and e['edition']==x.get('edition') and e['sha256']==x.get('sha256') for e in selected)]
  if pinned:
   if revision is not None and not any(x.get('revision')==revision for x in pinned):
    batch.append(dict(kind='source',reference=ref,status='CALLER_EDITION_REFERENCE_CONFLICT',requested_revision=revision,caller_selected_editions=[x.get('edition') for x in pinned]));return
   matched=pinned
   if revision is None:caller_selection='Explicit caller edition selection, not a finding that the unversioned citation legally prescribes this edition'
  if revision is not None:
   compatible=[x for x in matched if x.get('revision')==revision]
   if not compatible:batch.append(dict(kind='source',reference=ref,status='INCOMPATIBLE_EDITION',requested_revision=revision,available_editions=[x.get('edition') for x in matched]));return
   matched=compatible
  if parent and parent.get('authority'):
   same=[x for x in matched if x.get('authority')==parent['authority']]
   if not same:batch.append(dict(kind='source',reference=ref,status='INCOMPATIBLE_AUTHORITY'));return
   matched=same
  if len(matched)!=1:batch.append(dict(kind='source',reference=ref,status='AMBIGUOUS_DOCUMENT',candidates=[dict(file=x['file'],edition=x.get('edition')) for x in matched]));return
  entry=matched[0]
  try:text=self._load(entry)
  except (ValueError,FileNotFoundError,UnicodeDecodeError) as e:batch.append(dict(kind='source',reference=ref,status=str(e),file=entry.get('file')));return
  parts=sections(text);selected=set();section=request.get('section');query=tokens(request.get('query',''))
  if section:
   for i,p in enumerate(parts):
    if p['id']==section or p['id'].startswith(section+'.') or p['title'].casefold().startswith(section.casefold()+' '):
     if not contents_entry(p):selected.add(i)
   if not selected:batch.append(dict(kind='source',reference=ref,status='MISSING_SECTION',section=section,file=entry['file']));return
  else:
   for i,p in enumerate(parts):
    if scope_heading(p):
     selected.add(i)
     for j in range(i+1,len(parts)):
      if parts[j]['id'].startswith(p['id']+'.'):selected.add(j)
      else:break
   ranked=sorted(((len(tokens(text[p['start']:p['end']])&query),i) for i,p in enumerate(parts)),reverse=True)
   for score,i in ranked[:3]:
    if score>=2:selected.add(i)
   if not selected:batch.append(dict(kind='source',reference=ref,status='NO_BOUNDED_RELEVANT_PASSAGE',file=entry['file']));return
  selected.add(0)
  for i in list(selected):
   key0=parts[i]['id']
   for n in range(1,len(key0.split('.'))):
    prefix='.'.join(key0.split('.')[:n]);parents=[j for j in range(i) if parts[j]['id']==prefix]
    if parents:selected.add(parents[-1])
  spans=[]
  for i in sorted(selected):
   p=parts[i]
   if spans and spans[-1][1]==p['start']:spans[-1]=(spans[-1][0],p['end'])
   else:spans.append((p['start'],p['end']))
  added=[];skipped=[]
  for start,end in spans:
   identity=(entry['file'],start,end);size=end-start
   if identity in self.added_spans or any(d['file']==entry['file'] and d.get('selection',{}).get('start',-1)<=start and d.get('selection',{}).get('end',-1)>=end for d in context['source_documents']):continue
   used=sum(x.get('characters',0) for x in batch);passages=sum(len(x.get('passages',[])) for x in batch)
   if passages+len(added)>=self.policy['max_passages_per_round'] or used+sum(x['end']-x['start'] for x in added)+size>self.policy['max_characters_per_round'] or self.total_characters+size>self.policy['max_total_characters']:
    skipped.append(dict(start=start,end=end,reason='WHOLE_PASSAGE_BUDGET_LIMIT'));continue
   snippet=text[start:end];self.total_characters+=size;self.added_spans.add(identity)
   item=dict(file=entry['file'],sha256=entry['sha256'],authority=entry['authority'],edition=entry['edition'],text=snippet,selection=dict(start=start,end=end,line_start=text.count('\n',0,start)+1,line_end=text.count('\n',0,end)+1,page_start=text.count('\f',0,start)+1,page_end=text.count('\f',0,end)+1,sha256=digest(snippet)),retrieved_reference=ref)
   context['source_documents'].append(item);added.append(dict(start=start,end=end,sha256=digest(snippet)))
  status='RETRIEVED' if revision is not None else 'RETRIEVED_CALLER_SELECTED_EDITION' if caller_selection else 'RETRIEVED_EDITION_UNSPECIFIED'
  record=dict(kind='source',reference=ref,status=('PARTIAL_RETRIEVAL_LIMIT' if added and skipped else status) if added else ('PASSAGE_LIMIT_EXHAUSTED' if skipped else 'NO_NEW_PASSAGE'),file=entry['file'],document_sha256=entry['sha256'],authority=entry['authority'],edition=entry['edition'],edition_compatibility='Explicit requested revision matched' if revision is not None else caller_selection or 'Citation does not pin an edition; available retained edition is evidence, not a ruling on legal applicability',passages=added,skipped=skipped,characters=sum(x['end']-x['start'] for x in added));batch.append(record)
  for span in added:
   for r in references(text[span['start']:span['end']]):self._source(dict(kind='source',reference=r['document_id'],section=r['section'],revision=r['revision'],query=request.get('query',''),reason='Dependency of retrieved passage'),context,batch,ancestry+(key,),depth+1,entry)
   snippet=text[span['start']:span['end']]
   for kind,number in re.findall(r'(?i)\b(section|paragraph|clause|table|annex|appendix)\s+((?:[A-Z]\d+\.)?\d+(?:\.\d+)*)',snippet):
    if re.search(r'(?i)'+re.escape(kind)+r'\s+'+re.escape(number)+r'\s+of\s+(?:the\s+)?(?:Act|Convention|Code|Regulation)',snippet):continue
    code=entry.get('document_id','').removeprefix('UR ');aliases={number,code+'.'+number,(kind+' '+number).upper()}
    targets=[p['id'] for p in parts if p['id'] in aliases or p['title'].upper().startswith((kind+' '+number).upper()+' ') or p['title'].upper()==(kind+' '+number).upper()]
    if not targets:batch.append(dict(kind='source',reference=ref,section=number,status='MISSING_SECTION_REFERENCE'));continue
    for target in targets:self._source(dict(kind='source',reference=ref,section=target,revision=entry.get('revision'),query=request.get('query',''),reason='Internal reference in retrieved source'),context,batch,ancestry+(key,),depth+1,entry)

 def _schema(self,request,context,rid,batch):
  query=request['query'];words=tokens(query);plain=re.sub(r'([a-z])([A-Z])',r'\1 \2',query).casefold();rank=[]
  for iri,row in self.schema.terms.items():
   label=row.get('label','')+' '+row.get('localName','');labelwords=tokens(label);overlap=len(words&labelwords)
   rawwords=re.findall(r'[a-z][a-z0-9]+',re.sub(r'([a-z])([A-Z])',r'\1 \2',label).casefold());phrase=any(a not in STOP and (a+' '+b) in plain for a,b in zip(rawwords,rawwords[1:]))
   if iri in query:score=100
   elif phrase:score=20+overlap
   elif overlap>=2:score=overlap+overlap/max(len(labelwords),1)
   elif len(labelwords)==1 and labelwords==words:score=1
   else:continue
   rank.append((score,iri))
  rank.sort(reverse=True);seeds=[x[1] for x in rank[:self.policy['max_schema_terms']]];closure=self.schema.closure(seeds);ordered=seeds+sorted(str(x) for x in closure if str(x) not in seeds);known={x['iri'] for x in context['schema_terms']};terms=[];triples=[]
  for iri in ordered:
   if iri in known or iri not in self.schema.terms:continue
   facts=sorted([[URIRef(iri).n3(),p.n3(),o.n3()] for p,o in self.schema.graph.predicate_objects(URIRef(iri))])
   if len(terms)>=self.policy['max_schema_terms'] or len(triples)+len(facts)>self.policy['max_schema_triples']:continue
   terms.append(copy.deepcopy(self.schema.terms[iri]));triples+=facts;known.add(iri)
  context['schema_terms']+=terms;seen={tuple(x) for x in context['ontology_evidence']};context['ontology_evidence'] += [x for x in triples if tuple(x) not in seen]
  properties={x['localName'] for x in terms};bindings=[]
  for key,b in self.schema.bindings.items():
   owners={p:o for p,o in b.get('owners',{}).items() if p in properties}
   if owners:bindings.append(dict(requirement_id=key,scope='CURRENT_REQUIREMENT' if key==rid else 'OTHER_REQUIREMENT_NOT_TRANSFERABLE',owners=owners,model_paths=b.get('model_paths',[]),target_owner=b.get('target_owner')))
  event=dict(kind='schema',status='RETRIEVED' if terms else 'NO_NEW_EVIDENCE',query_sha256=digest(query),term_iris=[x['iri'] for x in terms],ontology_triples=triples,representation_mappings=bindings[:12],binding_search_truncated=len(bindings)>12,meaning='Vocabulary/type/domain/range existence is not evidence of legal eligibility or of an applicability binding. Other-requirement mappings cannot be transferred automatically.')
  context.setdefault('retrieved_schema_evidence',[]).append(event);batch.append(event)
 def resolve(self,context,requests,rid):
  if self.rounds>=self.policy['max_rounds']:return context,dict(status='CONTEXT_LIMIT_EXHAUSTED',novel=False,entries=[])
  signature=digest(json.dumps(requests,sort_keys=True))
  if signature in self.attempted_requests:return context,dict(status='REPEATED_EVIDENCE_REQUEST',novel=False,entries=[])
  self.attempted_requests.add(signature);self.rounds+=1;updated=copy.deepcopy(context);batch=[];old=len(context['source_documents']);old_terms=len(context['schema_terms'])
  for deferred in requests[self.policy['max_requests_per_round']:]:batch.append(dict(kind=deferred['kind'],reference=deferred.get('reference'),status='REQUEST_LIMIT_DEFERRED'))
  for request in requests[:self.policy['max_requests_per_round']]:
   if request['kind']=='source' and not request.get('reference'):
    supplied={d['file'] for d in context.get('source_documents',[])}|{d['file'] for d in context.get('admission',{}).get('declaration',{}).get('source_editions',[])}
    allowed=[(k,v) for k,v in self.schema.catalog.items() if v['file'] in supplied]
    if len(allowed)>self.policy['max_source_documents']:
     batch.append(dict(kind='source',status='AMBIGUOUS_DOCUMENT',reason='Reference omitted and supplied document set exceeds bounded search'));continue
    if not allowed:batch.append(dict(kind='source',status='MISSING_DOCUMENT',reason='No supplied approved catalog documents for optional-reference search'))
    for k,v in allowed:self._source(dict(request,reference=v.get('document_id',k)),updated,batch)
   elif request['kind']=='source':self._source(request,updated,batch)
   elif request['kind']=='schema':self._schema(request,updated,rid,batch)
  novel=len(updated['source_documents'])>old or len(updated['schema_terms'])>old_terms
  updated.setdefault('retrieval_evidence',[]).extend(batch)
  attempted={x.get('reference') for x in batch if x.get('kind')=='source' and x['status']!='REQUEST_LIMIT_DEFERRED'}
  def crossid(entry):
   ref=entry if entry.get('kind')=='CROSS_DOCUMENT_REFERENCE' else entry.get('reference')
   return ref.get('reference',{}).get('document_id') if isinstance(ref,dict) and ref.get('kind')=='CROSS_DOCUMENT_REFERENCE' else None
  updated['unresolvedSourceContext']=[x for x in updated.get('unresolvedSourceContext',[]) if not crossid(x) or crossid(x) not in attempted]
  updated['unresolvedSourceContext'] += [x for x in batch if x['status'] not in ['RETRIEVED','RETRIEVED_CALLER_SELECTED_EDITION','NO_NEW_PASSAGE','ALREADY_REQUESTED','CYCLE_SKIPPED','NO_NEW_EVIDENCE']]
  updated['retrieval_gaps']=[dict(gap_id=digest(json.dumps(x,sort_keys=True)),evidence=x,policy='Reviewer must explicitly assess materiality; missing information is not a code defect') for x in updated['unresolvedSourceContext']]
  event=dict(round=self.rounds,status='EVIDENCE_ADDED' if novel else 'NO_NEW_EVIDENCE',novel=novel,requests=requests,entries=batch,total_characters=self.total_characters,limits=self.policy)
  self.events.append(event);return updated,event
